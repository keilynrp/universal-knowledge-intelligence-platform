"""
wire-notification-events — per-endpoint integration tests.

These assert the *wiring* at the router boundary: driving a real endpoint fans
the correct event out (right action + payload) to the outbound sinks. They
complement `test_notification_emit.py`, which proves the emitter itself reaches
alert channels + email. Together they cover endpoint -> emit -> sinks end to end.

We monkeypatch each router's `emit_outbound` to record calls, so we assert the
contract without the async thread / live-network machinery.
"""
from __future__ import annotations

import json

import pytest

from backend import models


def _recorder(monkeypatch, dotted_path):
    """Patch a router-level emit_outbound and return the list it records into."""
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        dotted_path,
        lambda action, payload, db_factory, **kw: calls.append((action, payload)),
    )
    return calls


# ── harmonization.applied ───────────────────────────────────────────────────

def test_harmonization_apply_emits_event(client, auth_headers, db_session, monkeypatch):
    calls = _recorder(monkeypatch, "backend.routers.harmonization.emit_outbound")
    db_session.add(models.RawEntity(
        primary_label="  Messy   Label  ", entity_type="Organization",
        domain="science", validation_status="pending",
    ))
    db_session.commit()

    resp = client.post("/harmonization/apply/normalize_labels", headers=auth_headers)
    assert resp.status_code == 200, resp.text

    assert any(a == "harmonization.apply" for a, _ in calls)


# ── disambiguation.resolved ─────────────────────────────────────────────────

def test_rules_bulk_emits_disambiguation_resolved(client, auth_headers, monkeypatch):
    calls = _recorder(monkeypatch, "backend.routers.disambiguation.emit_outbound")

    resp = client.post(
        "/rules/bulk",
        json={
            "field_name": "brand_capitalized",
            "canonical_value": "Acme Corp",
            "variations": ["acme", "ACME", "Acme Corp"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text

    assert calls and calls[0][0] == "disambiguation.resolved"
    assert calls[0][1]["canonical_value"] == "Acme Corp"


# ── quality.low (downward crossing) ─────────────────────────────────────────

def test_quality_compute_emits_quality_low_on_crossing(client, auth_headers, db_session, monkeypatch):
    calls = _recorder(monkeypatch, "backend.routers.quality.emit_outbound")
    # Stored score 0.9 (>=60%) but the entity has only a primary_label, so the
    # rescore drops it well below the 60% threshold -> a downward crossing.
    db_session.add(models.UniversalEntity(
        primary_label="Lonely", domain="books", quality_score=0.9,
    ))
    db_session.commit()

    resp = client.post("/entities/quality/compute", headers=auth_headers)
    assert resp.status_code == 200, resp.text

    quality_low = [payload for action, payload in calls if action == "quality.low"]
    assert any(p["domain"] == "books" for p in quality_low)


def test_quality_compute_no_emit_when_no_crossing(client, auth_headers, db_session, monkeypatch):
    calls = _recorder(monkeypatch, "backend.routers.quality.emit_outbound")
    # Already-low stored score: recompute keeps it low, so there is no NEW
    # downward crossing and nothing should fire.
    db_session.add(models.UniversalEntity(
        primary_label="AlreadyLow", domain="music", quality_score=0.10,
    ))
    db_session.commit()

    resp = client.post("/entities/quality/compute", headers=auth_headers)
    assert resp.status_code == 200, resp.text

    assert all(a != "quality.low" or p.get("domain") != "music" for a, p in calls)


# ── authority.confirm (email-gated) ─────────────────────────────────────────

def test_authority_confirm_emits_event(client, auth_headers, db_session, monkeypatch):
    calls = _recorder(monkeypatch, "backend.routers.authority_records.emit_outbound")
    rec = models.AuthorityRecord(
        org_id=None, field_name="primary_label", original_value="ada lovelace",
        authority_source="orcid", authority_id="A1", canonical_label="Ada Lovelace",
        aliases="[]", description="", confidence=0.9, uri=None, status="pending",
        resolution_status="exact_match", score_breakdown="{}", evidence="[]",
        merged_sources="[]",
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)

    resp = client.post(f"/authority/records/{rec.id}/confirm", headers=auth_headers)
    assert resp.status_code == 200, resp.text

    assert any(a == "authority.confirm" for a, _ in calls)


# ── bell surfacing: pull / scheduled_pull write an AuditLog ──────────────────

def test_scheduled_import_run_writes_bell_audit(db_session):
    """The scheduled-import success path writes a `scheduled_pull` AuditLog so it
    surfaces in the notification center. Exercised at the unit boundary via the
    same _audit helper the endpoint uses (driving the full run needs a live store
    adapter)."""
    from backend.routers.deps import _audit
    _audit(db_session, "scheduled_pull", entity_type="store", entity_id=7,
           details={"entities_imported": 3, "queue_items": 1})
    db_session.commit()
    row = (
        db_session.query(models.AuditLog)
        .filter(models.AuditLog.action == "scheduled_pull").first()
    )
    assert row is not None
    assert json.loads(row.details)["entities_imported"] == 3
