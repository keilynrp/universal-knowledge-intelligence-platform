"""Phase 4 — read-only retrospective query service.

Covers point-in-time lookup (4.1), current-vs-prior comparison (4.2), time-series
& cohorts (4.3), and value provenance / null semantics (4.5).
"""
from datetime import datetime

from backend import models
from backend.retrospective import query, writer

_MAY = datetime(2026, 5, 15, 12, 0, 0)
_JUN = datetime(2026, 6, 15, 12, 0, 0)
_JUL = datetime(2026, 7, 15, 12, 0, 0)


def _snap(db, subject, valid_at, payload, org_id=None, stype="journal_metric"):
    writer.record_snapshot(
        db, snapshot_type=stype, org_id=org_id, subject_type="journal",
        subject_id=subject, valid_at=valid_at,
        idempotency_key=f"{subject}:{valid_at.isoformat()}", payload=payload,
    )
    db.flush()


# ── 4.1 point-in-time lookup ────────────────────────────────────────────────

def test_point_in_time_returns_latest_at_or_before(db_session):
    _snap(db_session, "J1", _MAY, {"nif": 1.0})
    _snap(db_session, "J1", _JUN, {"nif": 1.5})
    res = query.point_in_time_snapshot(
        db_session, org_id=None, snapshot_type="journal_metric",
        subject_id="J1", as_of=_JUL)
    assert res.found and res.payload["nif"] == 1.5 and res.valid_at == _JUN


def test_point_in_time_missing_history_is_typed(db_session):
    _snap(db_session, "J1", _JUN, {"nif": 1.5})
    res = query.point_in_time_snapshot(
        db_session, org_id=None, snapshot_type="journal_metric",
        subject_id="J1", as_of=_MAY)  # before any snapshot
    assert res.found is False
    assert res.missing_reason == "no_history"
    assert res.payload is None  # never falls back to current state


# ── 4.2 current-vs-prior comparison ─────────────────────────────────────────

def test_comparison_reports_changed_fields(db_session):
    _snap(db_session, "J1", _MAY, {"nif": 1.0, "nif_field": "Medicine"})
    res = query.compare_to_snapshot(
        db_session, org_id=None, snapshot_type="journal_metric",
        subject_id="J1", as_of=_JUN, current={"nif": 1.8, "nif_field": "Medicine"})
    assert res.found_prior
    assert set(res.changed_fields) == {"nif"}
    assert res.changed_fields["nif"] == {
        "prior": 1.0, "current": 1.8, "prior_provenance": "present"}


def test_comparison_missing_prior_is_typed(db_session):
    res = query.compare_to_snapshot(
        db_session, org_id=None, snapshot_type="journal_metric",
        subject_id="J1", as_of=_JUN, current={"nif": 1.8})
    assert res.found_prior is False and res.missing_reason == "no_history"


# ── 4.5 provenance / null semantics ─────────────────────────────────────────

def test_unknown_differs_from_unavailable(db_session):
    # nif explicitly null (unknown); h_index absent (unavailable).
    _snap(db_session, "J1", _MAY, {"nif": None})
    res = query.compare_to_snapshot(
        db_session, org_id=None, snapshot_type="journal_metric",
        subject_id="J1", as_of=_JUN, current={"nif": 1.2, "h_index": 5})
    assert res.changed_fields["nif"]["prior_provenance"] == "unknown"
    assert res.changed_fields["h_index"]["prior_provenance"] == "unavailable"


def test_explain_value_classifies(db_session):
    payload = {"a": 1, "b": None}
    assert query.explain_value(payload, "a") == "present"
    assert query.explain_value(payload, "b") == "unknown"
    assert query.explain_value(payload, "c") == "unavailable"


# ── 4.3 time-series & cohorts ───────────────────────────────────────────────

def test_time_series_is_ordered_and_bounded(db_session):
    _snap(db_session, "J1", _MAY, {"nif": 1.0})
    _snap(db_session, "J1", _JUN, {"nif": 1.5})
    _snap(db_session, "J1", _JUL, {"nif": 2.0})
    series = query.snapshot_time_series(
        db_session, org_id=None, snapshot_type="journal_metric",
        subject_id="J1", since=_MAY, until=_JUN)
    assert [p["payload"]["nif"] for p in series] == [1.0, 1.5]  # ordered, JUL excluded


def test_cohort_by_first_event_uses_event_timestamps(db_session):
    # J1 first computed in May; J2 first in July.
    for subj, occ in (("issn:J1", _MAY), ("issn:J1", _JUN), ("issn:J2", _JUL)):
        writer.record_event(
            db_session, event_type="journal_metric.computed", org_id=None,
            domain_object_type="journal", domain_object_id=subj, occurred_at=occ,
            source="test", idempotency_key=f"{subj}:{occ.isoformat()}",
            payload={"nif": 1.0})
    db_session.flush()
    may_cohort = query.cohort_by_first_event(
        db_session, org_id=None, event_type="journal_metric.computed",
        since=datetime(2026, 5, 1), until=datetime(2026, 5, 31))
    assert may_cohort == ["issn:J1"]  # J2's first event is July, excluded


def test_query_is_tenant_scoped(db_session):
    _snap(db_session, "J1", _MAY, {"nif": 9.9}, org_id=7)
    # Different org sees no history.
    res = query.point_in_time_snapshot(
        db_session, org_id=1, snapshot_type="journal_metric",
        subject_id="J1", as_of=_JUL)
    assert res.found is False
