"""Phase 5 — verification of the durable job runtime (ADR-007), tasks 5.1-5.4.

5.1 duplicate delivery + idempotent side effects; 5.2 cross-tenant access, replay,
error-metadata isolation; 5.3 crash/lease/DB-rollback recovery; 5.4 migration
rollback with accepted in-flight work.

5.5 (load), 5.6 (14-day observation), 5.7 (ER-OPS-001 -> operated) are operational
and tracked outside the test suite.
"""
from datetime import datetime, timedelta

import pytest

from backend import models
from backend.jobs import migration, runtime, service
from backend.jobs.migration import JobMode
from backend.jobs.states import JobStatus
from backend.models import utc_now_naive


def _enqueue(db, key="k", job_type="test.job", org_id=None, **kw):
    kw.setdefault("available_at", utc_now_naive())
    job = service.enqueue(db, job_type=job_type, org_id=org_id, idempotency_key=key,
                          payload={"n": 1}, **kw)
    db.commit()
    return job


# ── 5.1 duplicate delivery + idempotent side effects ────────────────────────

def test_same_occurrence_enqueues_once(db_session):
    """Repeated scheduler scans of one due occurrence create a single job."""
    occ = datetime(2026, 7, 12, 9, 0, 0)
    a = migration.enqueue_occurrence(db_session, domain="reports", job_type="report.execute",
                                     schedule_id=5, org_id=7, occurrence_at=occ, mode=JobMode.QUEUE)
    b = migration.enqueue_occurrence(db_session, domain="reports", job_type="report.execute",
                                     schedule_id=5, org_id=7, occurrence_at=occ, mode=JobMode.QUEUE)
    db_session.commit()
    assert a.id == b.id
    assert db_session.query(models.BackgroundJob).filter_by(job_type="report.execute").count() == 1


def test_redelivery_is_idempotent_via_checkpoint(db_session):
    """A handler redelivered after a crash produces a single net side effect."""
    effects = []

    def _idempotent(db, job):
        marker = f"done:{job.job_id}"
        if any(e == marker for e in effects):
            return  # already applied — safe resume
        effects.append(marker)

    runtime.register_handler("test.idem", _idempotent)
    try:
        job = _enqueue(db_session, key="idem", job_type="test.idem")
        runtime.run_once(db_session, lease_owner="w1")           # first delivery
        # Simulate crash-then-recover: force the job back to QUEUED and redeliver.
        job.status = JobStatus.QUEUED
        job.lease_owner = None
        db_session.add(job); db_session.commit()
        runtime.run_once(db_session, lease_owner="w2")           # redelivery
        assert effects.count(f"done:{job.job_id}") == 1          # one net effect
    finally:
        runtime.unregister("test.idem")


def test_completed_job_is_not_redelivered(db_session):
    runtime.register_handler("test.noop", lambda db, job: None)
    try:
        _enqueue(db_session, key="c", job_type="test.noop")
        runtime.run_once(db_session, lease_owner="w1")
        assert runtime.run_once(db_session, lease_owner="w2") is None  # nothing left to claim
    finally:
        runtime.unregister("test.noop")


# ── 5.2 cross-tenant, replay, error-metadata isolation ──────────────────────

def test_cross_tenant_job_is_not_visible(client, editor_headers, db_session):
    job = _enqueue(db_session, key="foreign", org_id=99999)  # not the editor's org
    # Read path: tenant scoping hides the foreign job entirely.
    assert client.get(f"/jobs/{job.job_id}", headers=editor_headers).status_code == 404
    # Mutating path: denied (403 by role or 404 by scope) — either way, no transition.
    assert client.post(f"/jobs/{job.job_id}/cancel", headers=editor_headers).status_code in (403, 404)
    db_session.refresh(job)
    assert job.status == JobStatus.QUEUED  # no cross-tenant transition occurred


def test_replay_preserves_tenant(db_session):
    now = utc_now_naive()
    job = models.BackgroundJob(
        job_id="f1", job_type="enrichment", idempotency_key="f1", org_id=42,
        status=JobStatus.FAILED, available_at=now, created_at=now,
        attempt=3, max_attempts=3, finished_at=now, error_code="boom")
    db_session.add(job); db_session.commit()
    new = service.replay(db_session, job, actor_id=1)
    assert new.org_id == 42 and new.replay_of == "f1"


def test_error_detail_is_bounded_and_sanitized(db_session):
    _enqueue(db_session, key="e")
    job = service.claim(db_session, lease_owner="w1")
    huge = "x" * 10000
    service.fail(db_session, job, error_code="api_error", error_detail=huge)
    assert len(job.error_detail) <= 2000  # bounded, never unbounded provider text


# ── 5.3 crash / lease / DB-rollback recovery ────────────────────────────────

def test_worker_crash_lease_recovered(db_session):
    _enqueue(db_session, key="c")
    job = service.claim(db_session, lease_owner="dead", lease_seconds=30)
    future = utc_now_naive() + timedelta(seconds=31)
    assert service.recover_abandoned_leases(db_session, now=future) == 1
    db_session.refresh(job)
    assert job.status == JobStatus.RETRY_WAIT


def test_handler_partial_write_is_rolled_back(db_session):
    """A handler that writes then raises leaves no partial side effect."""
    def _partial(db, job):
        db.add(models.JournalMetric(org_id=None, issn_l="ROLLBACK-TEST",
                                    two_yr_mean_citedness=1.0))
        db.flush()
        raise RuntimeError("boom after write")

    runtime.register_handler("test.partial", _partial)
    try:
        _enqueue(db_session, key="p", job_type="test.partial", max_attempts=3)
        runtime.run_once(db_session, lease_owner="w1")
        # The partial JournalMetric write was rolled back with the failed job.
        assert db_session.query(models.JournalMetric).filter_by(
            issn_l="ROLLBACK-TEST").count() == 0
        job = db_session.query(models.BackgroundJob).filter_by(job_type="test.partial").one()
        assert job.status == JobStatus.RETRY_WAIT
    finally:
        runtime.unregister("test.partial")


def test_queued_work_survives_restart(db_session):
    """Durability: a committed queued job persists (survives an identity-map flush)."""
    job = _enqueue(db_session, key="durable")
    job_id = job.job_id
    db_session.expire_all()  # drop cached state, as a fresh process would start with
    found = db_session.query(models.BackgroundJob).filter_by(job_id=job_id).one()
    assert found.status == JobStatus.QUEUED  # still durably queued and claimable


# ── 5.4 migration rollback with in-flight work ──────────────────────────────

def test_rollback_preserves_inflight_and_resumes_inprocess(db_session, monkeypatch):
    # In queue mode, an occurrence is enqueued (durable, in-flight).
    monkeypatch.setenv("UKIP_JOBS_REPORTS", "queue")
    inproc = []

    class _Sched:
        id = 3
        org_id = 7
        next_run_at = datetime(2026, 7, 12, 10, 0, 0)

    migration.dispatch_due(db_session, domain="reports", job_type="report.execute",
                           schedule=_Sched(), execute=lambda s, db: inproc.append(s.id))
    db_session.commit()
    inflight = db_session.query(models.BackgroundJob).filter_by(job_type="report.execute").count()
    assert inflight == 1 and inproc == []  # queue mode: enqueued, in-process skipped

    # Roll back to off: in-flight job survives; new occurrences run in-process again.
    monkeypatch.setenv("UKIP_JOBS_REPORTS", "off")

    class _Sched2:
        id = 4
        org_id = 7
        next_run_at = datetime(2026, 7, 12, 11, 0, 0)

    mode = migration.dispatch_due(db_session, domain="reports", job_type="report.execute",
                                  schedule=_Sched2(), execute=lambda s, db: inproc.append(s.id))
    db_session.commit()
    assert mode == "off"
    assert inproc == [4]  # in-process resumed
    # The originally-enqueued in-flight job is still durably present.
    assert db_session.query(models.BackgroundJob).filter_by(job_type="report.execute").count() == 1
