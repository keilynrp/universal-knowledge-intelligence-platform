"""Phase 3.4 — point-in-time snapshot materialization.

Covers the three initial snapshot families (journal metric, enrichment coverage,
authority readiness), the flag-gated orchestrator, and per-day idempotency.
"""
import json
from datetime import datetime

from backend import models
from backend.retrospective import snapshots

_DAY = datetime(2026, 7, 11, 8, 0, 0)


def _snaps(db, stype=None):
    q = db.query(models.RetrospectiveSnapshot)
    if stype:
        q = q.filter(models.RetrospectiveSnapshot.snapshot_type == stype)
    return q.all()


def _seed_journals(db):
    db.add(models.JournalMetric(org_id=None, issn_l="1111-1111", source_id="S1",
                                two_yr_mean_citedness=3.0, normalized_impact_factor=1.2,
                                nif_bayes=1.1, works_2yr=200, nif_field="Medicine"))
    db.add(models.JournalMetric(org_id=None, issn_l="2222-2222",
                                two_yr_mean_citedness=None))  # no metric → skipped
    db.commit()


def test_journal_metric_snapshots(db_session):
    _seed_journals(db_session)
    n = snapshots.materialize_journal_metric_snapshots(db_session, None, _DAY)
    db_session.flush()
    assert n == 1
    snap = _snaps(db_session, "journal_metric")[0]
    assert snap.subject_id == "1111-1111"
    payload = json.loads(snap.payload)
    assert payload["nif"] == 1.2 and payload["nif_bayes"] == 1.1


def test_enrichment_coverage_snapshot(db_session):
    for st in ("completed", "completed", "failed", "pending"):
        db_session.add(models.RawEntity(primary_label="x", org_id=None, enrichment_status=st))
    db_session.commit()
    n = snapshots.materialize_enrichment_coverage_snapshot(db_session, None, _DAY)
    db_session.flush()
    assert n == 1
    payload = json.loads(_snaps(db_session, "enrichment_coverage")[0].payload)
    assert payload["total"] == 4 and payload["completed"] == 2
    assert payload["completed_pct"] == 50.0


def test_authority_readiness_snapshot(db_session):
    for st in ("confirmed", "pending", "pending", "rejected"):
        db_session.add(models.AuthorityRecord(org_id=None, field_name="author",
                                              original_value="v", status=st))
    db_session.commit()
    n = snapshots.materialize_authority_readiness_snapshot(db_session, None, _DAY)
    db_session.flush()
    assert n == 1
    payload = json.loads(_snaps(db_session, "authority_readiness")[0].payload)
    assert payload["total"] == 4 and payload["confirmed"] == 1
    assert payload["pending"] == 2


def test_snapshots_are_idempotent_per_day(db_session):
    _seed_journals(db_session)
    snapshots.materialize_journal_metric_snapshots(db_session, None, _DAY)
    db_session.flush()
    snapshots.materialize_journal_metric_snapshots(db_session, None, _DAY)  # same day
    db_session.flush()
    assert len(_snaps(db_session, "journal_metric")) == 1


def test_orchestrator_flag_off_is_noop(db_session, monkeypatch):
    monkeypatch.delenv("UKIP_RETRO_EVENTS", raising=False)
    _seed_journals(db_session)
    assert snapshots.materialize_all(db_session, None, _DAY) == {}
    assert _snaps(db_session) == []


def test_orchestrator_materializes_all_families(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _seed_journals(db_session)
    db_session.add(models.RawEntity(primary_label="x", org_id=None, enrichment_status="completed"))
    db_session.add(models.AuthorityRecord(org_id=None, field_name="a", original_value="v",
                                          status="confirmed"))
    db_session.commit()
    result = snapshots.materialize_all(db_session, None, _DAY)
    assert result == {"journal_metric": 1, "enrichment_coverage": 1, "authority_readiness": 1}
    assert len(_snaps(db_session)) == 3


def test_snapshot_is_tenant_scoped(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    db_session.add(models.RawEntity(primary_label="x", org_id=5, enrichment_status="completed"))
    db_session.commit()
    snapshots.materialize_enrichment_coverage_snapshot(db_session, 5, _DAY)
    db_session.flush()
    snap = _snaps(db_session, "enrichment_coverage")[0]
    assert snap.org_id == 5 and snap.subject_id == "5"
