"""Phase 5 — warehouse export: schemas, manifests, idempotent jobs, validation."""
import json
from datetime import datetime

from backend import models
from backend.retrospective import export, writer

_MAY = datetime(2026, 5, 15, 12, 0, 0)
_JUN = datetime(2026, 6, 15, 12, 0, 0)


def _event(db, subj, occ, org_id=None, etype="journal_metric.computed"):
    writer.record_event(
        db, event_type=etype, org_id=org_id, domain_object_type="journal",
        domain_object_id=subj, occurred_at=occ, source="test",
        idempotency_key=f"{subj}:{occ.isoformat()}:{org_id}", payload={"nif": 1.0})
    db.flush()


def _raw_event(db, subj, recorded_at, org_id=None):
    """Insert an event with an explicit recorded_at (controls recorded_date partition)."""
    db.add(models.RetrospectiveEvent(
        event_id=f"e-{subj}-{recorded_at.isoformat()}", event_type="journal_metric.computed",
        schema_version=1, org_id=org_id, domain_object_type="journal",
        domain_object_id=subj, occurred_at=recorded_at, recorded_at=recorded_at,
        source="test", actor_type="job",
        idempotency_key=f"{subj}:{recorded_at.isoformat()}:{org_id}", payload='{"nif":1.0}'))
    db.flush()


def _snapshot(db, subj, valid_at, org_id=None):
    writer.record_snapshot(
        db, snapshot_type="journal_metric", org_id=org_id, subject_type="journal",
        subject_id=subj, valid_at=valid_at,
        idempotency_key=f"{subj}:{valid_at.isoformat()}:{org_id}", payload={"nif": 1.0})
    db.flush()


# ── 5.1 schemas ─────────────────────────────────────────────────────────────

def test_event_schema_has_partition_and_clustering():
    names = {c.name for c in export.EVENT_EXPORT_SCHEMA}
    assert export.EVENT_PARTITION_FIELD == "recorded_date"
    assert "recorded_date" in names
    assert set(export.EVENT_CLUSTERING_FIELDS) <= names
    # warehouse-safe types only
    assert {c.type for c in export.EVENT_EXPORT_SCHEMA} <= {
        "STRING", "INT64", "FLOAT64", "BOOL", "TIMESTAMP", "DATE", "JSON"}


# ── 5.3 event export + manifest (5.2) ───────────────────────────────────────

def test_export_events_manifest_and_partition(db_session):
    _raw_event(db_session, "issn:A", _MAY)
    _raw_event(db_session, "issn:B", _JUN)
    res = export.export_events(db_session, org_scope=None)
    assert res.manifest.row_counts == 2
    assert res.manifest.status == "completed"
    # partition range is derived from recorded_date (when rows were recorded)
    assert res.manifest.partition_range == ("2026-05-15", "2026-06-15")
    assert res.manifest.checksum
    assert all("recorded_date" in r for r in res.rows)


def test_export_is_idempotent(db_session):
    _event(db_session, "issn:A", _MAY)
    _event(db_session, "issn:B", _JUN)
    a = export.export_events(db_session, org_scope=None)
    b = export.export_events(db_session, org_scope=None)
    assert a.manifest.checksum == b.manifest.checksum
    assert [r["event_id"] for r in a.rows] == [r["event_id"] for r in b.rows]


def test_empty_export_is_bounded(db_session):
    res = export.export_events(db_session, org_scope=None)
    assert res.manifest.status == "empty"
    assert res.manifest.row_counts == 0
    assert res.manifest.partition_range is None


def test_export_is_tenant_scoped(db_session):
    _event(db_session, "issn:A", _MAY, org_id=7)
    _event(db_session, "issn:B", _MAY, org_id=9)
    res = export.export_events(db_session, org_scope=7)
    assert res.manifest.row_counts == 1
    assert all(r["org_id"] == 7 for r in res.rows)


def test_window_filter(db_session):
    # Window filters on recorded_at (warehouse ingest time).
    _raw_event(db_session, "issn:A", _MAY)
    _raw_event(db_session, "issn:B", _JUN)
    res = export.export_events(db_session, org_scope=None, since=_JUN)
    assert res.manifest.row_counts == 1


# ── 5.4 snapshot export ─────────────────────────────────────────────────────

def test_export_snapshots(db_session):
    _snapshot(db_session, "issn:A", _MAY)
    res = export.export_snapshots(db_session, org_scope=None)
    assert res.manifest.dataset_name == "retrospective_snapshots"
    assert res.manifest.row_counts == 1
    assert res.rows[0]["snapshot_type"] == "journal_metric"


# ── 5.5 validation ──────────────────────────────────────────────────────────

def test_validation_passes_for_clean_export(db_session):
    _event(db_session, "issn:A", _MAY, org_id=7)
    res = export.export_events(db_session, org_scope=7)
    report = export.validate_export(res, export.EVENT_EXPORT_SCHEMA, org_scope=7)
    assert report.ok and report.tenant_ok and report.schema_ok and report.row_count_ok


def test_validation_detects_tenant_leak(db_session):
    _event(db_session, "issn:A", _MAY, org_id=7)
    res = export.export_events(db_session, org_scope=7)
    # Tamper: claim org_scope 99 → the org-7 row is now a leak.
    report = export.validate_export(res, export.EVENT_EXPORT_SCHEMA, org_scope=99)
    assert report.ok is False and report.tenant_ok is False


def test_validation_detects_schema_drift(db_session):
    _event(db_session, "issn:A", _MAY)
    res = export.export_events(db_session, org_scope=None)
    res.rows[0]["unexpected_col"] = "x"  # inject drift
    report = export.validate_export(res, export.EVENT_EXPORT_SCHEMA, org_scope=None)
    assert report.ok is False and report.schema_ok is False


def test_validation_detects_row_count_mismatch(db_session):
    _event(db_session, "issn:A", _MAY)
    res = export.export_events(db_session, org_scope=None)
    res.rows.append({"event_id": "extra"})  # manifest still says 1
    report = export.validate_export(res, export.EVENT_EXPORT_SCHEMA, org_scope=None)
    assert report.row_count_ok is False


# ── warehouse optionality ───────────────────────────────────────────────────

def test_warehouse_not_configured_by_default(monkeypatch):
    monkeypatch.delenv("UKIP_WAREHOUSE_DATASET", raising=False)
    assert export.warehouse_configured() is False
    assert export.export_readiness()["status"] == "not_configured"


def test_warehouse_configured_when_env_set(monkeypatch):
    monkeypatch.setenv("UKIP_WAREHOUSE_DATASET", "bq://proj.ukip_retro")
    assert export.warehouse_configured() is True
    assert export.export_readiness()["status"] == "configured"
