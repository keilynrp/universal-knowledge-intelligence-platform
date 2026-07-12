"""Phase 7 — verification & observability for the retrospective layer.

7.1 point-in-time reconstruction vs a workflow fixture, 7.2 current-vs-historical
comparison, 7.3 export manifest integrity, 7.4 retention/deletion behaviour,
7.5 observability metrics.
"""
from datetime import datetime

import pytest
from sqlalchemy import text

from backend import models
from backend.retrospective import export, metrics, query, writer

_MAR = datetime(2026, 3, 1, 0, 0, 0)
_APR = datetime(2026, 4, 1, 0, 0, 0)
_MAY = datetime(2026, 5, 1, 0, 0, 0)


def _snap(db, subj, valid_at, payload, org_id=None):
    writer.record_snapshot(
        db, snapshot_type="journal_metric", org_id=org_id, subject_type="journal",
        subject_id=subj, valid_at=valid_at,
        idempotency_key=f"{subj}:{valid_at.isoformat()}:{org_id}", payload=payload)
    db.flush()


def _workflow_fixture(db):
    """A journal whose NIF was snapshotted across three months."""
    _snap(db, "issn:W", _MAR, {"nif": 1.0, "nif_field": "Medicine"})
    _snap(db, "issn:W", _APR, {"nif": 1.4, "nif_field": "Medicine"})
    _snap(db, "issn:W", _MAY, {"nif": 1.9, "nif_field": "Medicine"})
    db.commit()


# ── 7.1 point-in-time reconstruction ────────────────────────────────────────

def test_reconstruction_returns_state_known_at_each_time(db_session):
    _workflow_fixture(db_session)
    mid_apr = datetime(2026, 4, 15)
    res = query.point_in_time_snapshot(
        db_session, org_id=None, snapshot_type="journal_metric",
        subject_id="issn:W", as_of=mid_apr)
    assert res.found and res.payload["nif"] == 1.4  # April state, not May


def test_reconstruction_before_history_is_missing(db_session):
    _workflow_fixture(db_session)
    res = query.point_in_time_snapshot(
        db_session, org_id=None, snapshot_type="journal_metric",
        subject_id="issn:W", as_of=datetime(2026, 1, 1))
    assert res.found is False and res.missing_reason == "no_history"


# ── 7.2 current-vs-historical comparison ────────────────────────────────────

def test_comparison_current_vs_march(db_session):
    _workflow_fixture(db_session)
    res = query.compare_to_snapshot(
        db_session, org_id=None, snapshot_type="journal_metric",
        subject_id="issn:W", as_of=datetime(2026, 3, 15),
        current={"nif": 2.5, "nif_field": "Medicine"})
    assert res.found_prior
    assert res.changed_fields["nif"] == {
        "prior": 1.0, "current": 2.5, "prior_provenance": "present"}
    assert "nif_field" not in res.changed_fields  # unchanged


# ── 7.3 export manifest integrity ───────────────────────────────────────────

def test_export_manifest_checksum_and_counts(db_session):
    _workflow_fixture(db_session)
    res = export.export_snapshots(db_session, org_scope=None)
    assert res.manifest.row_counts == len(res.rows) == 3
    # Checksum is deterministic: recomputing over the same rows matches.
    assert export._checksum(res.rows, "snapshot_id") == res.manifest.checksum
    # Idempotent re-run yields an identical checksum.
    again = export.export_snapshots(db_session, org_scope=None)
    assert again.manifest.checksum == res.manifest.checksum


def test_export_manifest_validates_clean(db_session):
    _workflow_fixture(db_session)
    res = export.export_snapshots(db_session, org_scope=None)
    report = export.validate_export(res, export.SNAPSHOT_EXPORT_SCHEMA, org_scope=None)
    assert report.ok is True


# ── 7.4 retention / deletion behaviour ──────────────────────────────────────

def test_append_only_blocks_orm_delete_but_allows_governed_purge(db_session):
    _snap(db_session, "issn:P", _MAR, {"nif": 1.0})
    db_session.commit()
    row = db_session.query(models.RetrospectiveSnapshot).filter_by(subject_id="issn:P").one()

    # Ordinary ORM delete is rejected (append-only).
    db_session.delete(row)
    with pytest.raises(RuntimeError, match="append-only"):
        db_session.flush()
    db_session.rollback()

    # Governed retention purge (raw SQL, as the EPIC-016 purger would) succeeds.
    db_session.execute(text("DELETE FROM retrospective_snapshots WHERE subject_id = 'issn:P'"))
    db_session.commit()
    assert db_session.query(models.RetrospectiveSnapshot).filter_by(subject_id="issn:P").count() == 0


# ── 7.5 observability metrics ───────────────────────────────────────────────

def test_metrics_report_volume_and_freshness(db_session):
    _workflow_fixture(db_session)
    writer.record_event(
        db_session, event_type="journal_metric.computed", org_id=None,
        domain_object_type="journal", domain_object_id="issn:W", occurred_at=_MAR,
        source="test", idempotency_key="W:mar", payload={"nif": 1.0})
    db_session.commit()

    m = metrics.retrospective_metrics(db_session, None)
    assert m["events"]["total"] == 1
    assert m["events"]["by_type"]["journal_metric.computed"] == 1
    assert m["snapshots"]["total"] == 3
    jm = m["snapshots"]["by_type"]["journal_metric"]
    assert jm["count"] == 3 and jm["freshness_age_seconds"] is not None


def test_metrics_failed_emission_counter(db_session, monkeypatch):
    metrics.reset_failed_emissions()
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    from backend.retrospective import emit

    monkeypatch.setattr(emit.writer, "record_event", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    emit.emit_journal_metric_normalized(
        db_session, org_id=None, issn_l="X", new_nif=1.0, prior_nif=None,
        nif_field="Medicine", field_median=1.0, occurred_at=_MAR, source_id="S1")
    assert metrics.failed_emission_count() == 1


def test_metrics_endpoint(client, auth_headers, db_session):
    _snap(db_session, "issn:W", _MAR, {"nif": 1.0})
    db_session.commit()
    r = client.get("/retrospective/metrics", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["snapshots"]["total"] == 1
    assert "failed_emissions" in body
