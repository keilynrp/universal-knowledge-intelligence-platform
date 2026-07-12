"""Phase 3.3 — authority decisions emit retrospective events.

Unit coverage of ``emit_authority_decision`` plus end-to-end coverage through the
confirm/reject review endpoints (the governed human decisions the spec names).
"""
import json
from datetime import datetime

from backend import models
from backend.retrospective import emit

_NOW = datetime(2026, 7, 11, 11, 0, 0)


def _events(db):
    return db.query(models.RetrospectiveEvent).all()


def _decide(db, **over):
    kwargs = dict(
        org_id=None, record_id=1, decision="accepted", occurred_at=_NOW,
        actor_id="7", field_name="author", authority_source="orcid",
        authority_id="0000-0001", canonical_label="Jane Roe", confidence=0.97,
    )
    kwargs.update(over)
    emit.emit_authority_decision(db, **kwargs)
    db.flush()


# ── Unit ────────────────────────────────────────────────────────────────────

def test_flag_off_emits_nothing(db_session, monkeypatch):
    monkeypatch.delenv("UKIP_RETRO_EVENTS", raising=False)
    _decide(db_session)
    assert _events(db_session) == []


def test_accepted_event(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _decide(db_session)
    e = _events(db_session)[0]
    assert e.event_type == "authority.accepted"
    assert e.actor_type == "user" and e.actor_id == "7"
    assert e.source == "authority_review"
    payload = json.loads(e.payload)
    assert payload["authority_id"] == "0000-0001"
    assert payload["confidence"] == 0.97


def test_rejected_event(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _decide(db_session, decision="rejected")
    e = _events(db_session)[0]
    assert e.event_type == "authority.rejected"


def test_unmapped_decision_ignored(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _decide(db_session, decision="deferred")
    assert _events(db_session) == []


def test_non_fatal_on_writer_error(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")

    def _boom(*_a, **_k):
        raise RuntimeError("down")

    monkeypatch.setattr(emit.writer, "record_event", _boom)
    _decide(db_session)  # must not raise
    assert _events(db_session) == []


def test_idempotent_within_run(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _decide(db_session)
    _decide(db_session)  # replay, same occurred_at
    assert len(_events(db_session)) == 1


# ── End-to-end via the review endpoints ─────────────────────────────────────

def _make_record(db, status="pending"):
    rec = models.AuthorityRecord(
        org_id=None, field_name="author", original_value="J Roe",
        authority_source="orcid", authority_id="0000-0001",
        canonical_label="Jane Roe", confidence=0.97, status=status,
    )
    db.add(rec)
    db.commit()
    return rec


def test_confirm_endpoint_emits_accepted(client, auth_headers, db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    rec = _make_record(db_session)
    resp = client.post(f"/authority/records/{rec.id}/confirm", headers=auth_headers)
    assert resp.status_code == 200
    accepted = [e for e in _events(db_session) if e.event_type == "authority.accepted"]
    assert len(accepted) == 1
    assert accepted[0].domain_object_id == str(rec.id)


def test_reject_endpoint_emits_rejected(client, auth_headers, db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    rec = _make_record(db_session)
    resp = client.post(f"/authority/records/{rec.id}/reject", headers=auth_headers)
    assert resp.status_code == 200
    rejected = [e for e in _events(db_session) if e.event_type == "authority.rejected"]
    assert len(rejected) == 1
