"""Phase 4 — retrospective query API endpoints (read-only, tenant-scoped)."""
from datetime import datetime

from backend import models
from backend.retrospective import writer

_MAY = datetime(2026, 5, 15, 12, 0, 0)
_JUN = datetime(2026, 6, 15, 12, 0, 0)
_JUL = datetime(2026, 7, 15, 12, 0, 0)


def _snap(db, issn, valid_at, payload):
    writer.record_snapshot(
        db, snapshot_type="journal_metric", org_id=None, subject_type="journal",
        subject_id=issn, valid_at=valid_at,
        idempotency_key=f"{issn}:{valid_at.isoformat()}", payload=payload)
    db.commit()


def test_snapshot_endpoint_missing_history(client, auth_headers):
    r = client.get("/retrospective/snapshot", headers=auth_headers, params={
        "snapshot_type": "journal_metric", "subject_id": "NONE",
        "as_of": _JUL.isoformat()})
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is False and body["missing_reason"] == "no_history"


def test_journal_timeseries_endpoint(client, auth_headers, db_session):
    _snap(db_session, "0028-0836", _MAY, {"nif": 1.0})
    _snap(db_session, "0028-0836", _JUN, {"nif": 1.5})
    r = client.get("/retrospective/journals/0028-0836/timeseries", headers=auth_headers)
    assert r.status_code == 200
    series = r.json()["series"]
    assert [p["payload"]["nif"] for p in series] == [1.0, 1.5]


def test_journal_compare_endpoint(client, auth_headers, db_session):
    db_session.add(models.JournalMetric(
        org_id=None, issn_l="0028-0836", two_yr_mean_citedness=4.0,
        normalized_impact_factor=1.8, nif_field="Medicine"))
    _snap(db_session, "0028-0836", _MAY, {"nif": 1.0, "nif_bayes": None,
          "two_yr_mean_citedness": 3.0, "works_2yr": None, "nif_field": "Medicine"})
    r = client.get("/retrospective/journals/0028-0836/compare", headers=auth_headers,
                   params={"as_of": _JUN.isoformat()})
    assert r.status_code == 200
    body = r.json()
    assert body["found_prior"] is True
    assert body["changed_fields"]["nif"]["prior"] == 1.0
    assert body["changed_fields"]["nif"]["current"] == 1.8


def test_journal_compare_404_when_journal_absent(client, auth_headers):
    r = client.get("/retrospective/journals/9999-9999/compare", headers=auth_headers,
                   params={"as_of": _JUN.isoformat()})
    assert r.status_code == 404


def test_cohort_endpoint(client, auth_headers, db_session):
    for occ in (_MAY, _JUN):
        writer.record_event(
            db_session, event_type="journal_metric.computed", org_id=None,
            domain_object_type="journal", domain_object_id="issn:A", occurred_at=occ,
            source="test", idempotency_key=f"A:{occ.isoformat()}", payload={"nif": 1.0})
    db_session.commit()
    r = client.get("/retrospective/cohort", headers=auth_headers, params={
        "event_type": "journal_metric.computed",
        "since": datetime(2026, 5, 1).isoformat(), "until": datetime(2026, 5, 31).isoformat()})
    assert r.status_code == 200
    assert r.json()["members"] == ["issn:A"]


def test_endpoints_require_auth(client):
    r = client.get("/retrospective/snapshot", params={
        "snapshot_type": "journal_metric", "subject_id": "X", "as_of": _JUL.isoformat()})
    assert r.status_code in (401, 403)


# ── Phase 5 export endpoints ────────────────────────────────────────────────

def test_export_readiness_not_configured(client, auth_headers, monkeypatch):
    monkeypatch.delenv("UKIP_WAREHOUSE_DATASET", raising=False)
    r = client.get("/retrospective/export/readiness", headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == "not_configured"


def test_export_events_endpoint_returns_manifest_and_validation(client, auth_headers, db_session):
    writer.record_event(
        db_session, event_type="journal_metric.computed", org_id=None,
        domain_object_type="journal", domain_object_id="issn:A", occurred_at=_MAY,
        source="test", idempotency_key="A", payload={"nif": 1.0})
    db_session.commit()
    r = client.post("/retrospective/export/events", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["manifest"]["row_counts"] == 1
    assert body["manifest"]["dataset_name"] == "retrospective_events"
    assert body["validation"]["ok"] is True
    assert body["readiness"]["status"] == "not_configured"


def test_export_snapshots_endpoint(client, auth_headers, db_session):
    _snap(db_session, "0028-0836", _MAY, {"nif": 1.0})
    r = client.post("/retrospective/export/snapshots", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["manifest"]["dataset_name"] == "retrospective_snapshots"


def test_export_requires_auth(client):
    r = client.post("/retrospective/export/events")
    assert r.status_code in (401, 403)
