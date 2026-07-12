"""Phase 2 — durable background job contract (ADR-007).

FSM (2.1), tenant-scoped idempotency (2.2), claim/lease/retry/cancel/recovery
(2.3), sanitized audit + retention (2.4), and concurrency (2.5).
"""
from datetime import datetime, timedelta

import pytest

from backend import models
from backend.jobs import service
from backend.jobs.states import InvalidTransition, JobStatus, assert_transition

_T0 = datetime(2026, 7, 12, 12, 0, 0)


def _enqueue(db, key="k1", org_id=None, job_type="enrichment", **kw):
    # Default available_at to the fixed test clock (_T0) so claims with now=_T0 are
    # due regardless of wall-clock time. Tests that need a future job override it.
    kw.setdefault("available_at", _T0)
    job = service.enqueue(db, job_type=job_type, org_id=org_id, idempotency_key=key,
                          payload={"entity_id": 1}, **kw)
    db.commit()
    return job


# ── 2.1 FSM ─────────────────────────────────────────────────────────────────

def test_valid_and_invalid_transitions():
    assert_transition(JobStatus.QUEUED, JobStatus.RUNNING)      # ok
    assert_transition(JobStatus.RUNNING, JobStatus.SUCCEEDED)   # ok
    with pytest.raises(InvalidTransition):
        assert_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
    with pytest.raises(InvalidTransition):
        assert_transition(JobStatus.QUEUED, JobStatus.SUCCEEDED)


# ── 2.2 enqueue + idempotency ───────────────────────────────────────────────

def test_enqueue_persists_queued(db_session):
    job = _enqueue(db_session)
    assert job.status == JobStatus.QUEUED and job.job_id and job.attempt == 0


def test_enqueue_is_idempotent(db_session):
    a = _enqueue(db_session, key="dup")
    b = _enqueue(db_session, key="dup")
    assert a.id == b.id
    assert db_session.query(models.BackgroundJob).filter_by(idempotency_key="dup").count() == 1


def test_idempotency_is_tenant_scoped(db_session):
    a = _enqueue(db_session, key="same", org_id=7)
    b = _enqueue(db_session, key="same", org_id=9)
    assert a.id != b.id


def test_payload_never_stores_none_as_secret(db_session):
    job = _enqueue(db_session)
    assert '"entity_id"' in job.payload  # references only


# ── 2.3 claim + lease ───────────────────────────────────────────────────────

def test_claim_sets_running_and_lease(db_session):
    _enqueue(db_session)
    job = service.claim(db_session, lease_owner="w1", now=_T0, lease_seconds=60)
    assert job is not None
    assert job.status == JobStatus.RUNNING and job.lease_owner == "w1"
    assert job.lease_expires_at == _T0 + timedelta(seconds=60)
    assert job.attempt == 1 and job.started_at == _T0


def test_claim_is_exclusive(db_session):
    _enqueue(db_session)
    first = service.claim(db_session, lease_owner="w1", now=_T0)
    second = service.claim(db_session, lease_owner="w2", now=_T0)
    assert first is not None and second is None  # at most one claim


def test_claim_respects_available_at(db_session):
    _enqueue(db_session, available_at=_T0 + timedelta(hours=1))
    assert service.claim(db_session, lease_owner="w1", now=_T0) is None  # not yet due


def test_claim_priority_and_fifo_order(db_session):
    _enqueue(db_session, key="low", priority=200)
    _enqueue(db_session, key="high", priority=10)
    job = service.claim(db_session, lease_owner="w1", now=_T0)
    assert job.idempotency_key == "high"  # lower priority number first


def test_renew_lease_only_for_owner(db_session):
    _enqueue(db_session)
    job = service.claim(db_session, lease_owner="w1", now=_T0)
    assert service.renew_lease(db_session, job, lease_owner="w1", now=_T0 + timedelta(seconds=30))
    assert not service.renew_lease(db_session, job, lease_owner="intruder", now=_T0)


# ── terminal + retry ────────────────────────────────────────────────────────

def test_complete(db_session):
    _enqueue(db_session)
    job = service.claim(db_session, lease_owner="w1", now=_T0)
    service.complete(db_session, job, now=_T0)
    assert job.status == JobStatus.SUCCEEDED and job.lease_owner is None


def test_fail_retries_with_backoff(db_session):
    _enqueue(db_session, max_attempts=3)
    job = service.claim(db_session, lease_owner="w1", now=_T0)  # attempt=1
    status = service.fail(db_session, job, error_code="api_error", now=_T0)
    assert status == JobStatus.RETRY_WAIT
    assert job.available_at > _T0  # backoff applied
    assert job.error_code == "api_error"


def test_fail_terminal_when_attempts_exhausted(db_session):
    job = _enqueue(db_session, max_attempts=1)
    claimed = service.claim(db_session, lease_owner="w1", now=_T0)  # attempt=1 == max
    status = service.fail(db_session, claimed, error_code="boom", now=_T0)
    assert status == JobStatus.FAILED and claimed.finished_at is not None


def test_promote_retry_ready(db_session):
    _enqueue(db_session, max_attempts=3)
    job = service.claim(db_session, lease_owner="w1", now=_T0)
    service.fail(db_session, job, error_code="x", now=_T0)
    later = job.available_at + timedelta(seconds=1)
    assert service.promote_retry_ready(db_session, now=later) == 1
    db_session.refresh(job)
    assert job.status == JobStatus.QUEUED


# ── 2.3 recovery supervisor ─────────────────────────────────────────────────

def test_recover_abandoned_lease(db_session):
    _enqueue(db_session, max_attempts=3)
    job = service.claim(db_session, lease_owner="dead", now=_T0, lease_seconds=30)
    after_expiry = _T0 + timedelta(seconds=31)
    assert service.recover_abandoned_leases(db_session, now=after_expiry) == 1
    db_session.refresh(job)
    assert job.status == JobStatus.RETRY_WAIT and job.error_code == "lease_expired"


# ── 2.4 cancel / replay (audited) ───────────────────────────────────────────

def test_cancel_emits_audit(db_session):
    job = _enqueue(db_session)
    service.cancel(db_session, job, actor_id=42)
    assert job.status == JobStatus.CANCELLED
    audit = db_session.query(models.AuditLog).filter_by(action="job.cancel").one()
    assert audit.entity_id == job.id and audit.user_id == 42


def test_cannot_cancel_running(db_session):
    _enqueue(db_session)
    job = service.claim(db_session, lease_owner="w1", now=_T0)
    with pytest.raises(InvalidTransition):
        service.cancel(db_session, job)


def test_replay_creates_new_job_and_preserves_original(db_session):
    job = _enqueue(db_session, max_attempts=1)
    claimed = service.claim(db_session, lease_owner="w1", now=_T0)
    service.fail(db_session, claimed, error_code="boom", now=_T0)  # FAILED
    new = service.replay(db_session, claimed, actor_id=7)
    assert new.status == JobStatus.QUEUED and new.replay_of == claimed.job_id
    assert claimed.status == JobStatus.FAILED  # original untouched
    assert db_session.query(models.AuditLog).filter_by(action="job.replay").count() == 1


def test_replay_only_failed(db_session):
    job = _enqueue(db_session)
    with pytest.raises(service.JobError):
        service.replay(db_session, job)


# ── 2.4 retention ───────────────────────────────────────────────────────────

def test_purge_terminal_jobs(db_session):
    job = _enqueue(db_session)
    service.cancel(db_session, job)
    job.finished_at = _T0 - timedelta(days=40)
    db_session.add(job); db_session.commit()
    purged = service.purge_terminal_jobs(db_session, older_than=_T0 - timedelta(days=30))
    assert purged == 1
    assert db_session.query(models.BackgroundJob).count() == 0


# ── 2.5 concurrency (claim exclusivity across many jobs) ─────────────────────

def test_each_job_claimed_at_most_once(db_session):
    for i in range(5):
        _enqueue(db_session, key=f"j{i}")
    claimed_ids = []
    while True:
        job = service.claim(db_session, lease_owner="w", now=_T0)
        if job is None:
            break
        claimed_ids.append(job.id)
    assert len(claimed_ids) == len(set(claimed_ids)) == 5  # each exactly once
