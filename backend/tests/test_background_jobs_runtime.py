"""Phase 3 — job runtime (worker dispatch, drain) and observability metrics."""
from datetime import timedelta

import pytest

from backend import models
from backend.jobs import metrics, runtime, service
from backend.jobs.states import JobStatus
from backend.models import utc_now_naive


def _enqueue(db, key="k", job_type="test.echo", **kw):
    job = service.enqueue(db, job_type=job_type, org_id=None, idempotency_key=key,
                          payload={"n": 1}, **kw)
    db.commit()
    return job


@pytest.fixture
def echo_handler():
    calls = []
    runtime.register_handler("test.echo", lambda db, job: calls.append(job.job_id))
    yield calls
    runtime.unregister("test.echo")


# ── run_once dispatch ───────────────────────────────────────────────────────

def test_run_once_success_completes(db_session, echo_handler):
    job = _enqueue(db_session)
    done = runtime.run_once(db_session, lease_owner="w1")
    assert done.job_id == job.job_id
    db_session.refresh(job)
    assert job.status == JobStatus.SUCCEEDED
    assert echo_handler == [job.job_id]


def test_run_once_idle_returns_none(db_session):
    assert runtime.run_once(db_session, lease_owner="w1") is None


def test_run_once_handler_error_retries(db_session):
    def _boom(db, job):
        raise ValueError("kaboom")
    runtime.register_handler("test.boom", _boom)
    try:
        job = _enqueue(db_session, job_type="test.boom", max_attempts=3)
        runtime.run_once(db_session, lease_owner="w1")
        db_session.refresh(job)
        assert job.status == JobStatus.RETRY_WAIT
        assert job.error_code == "ValueError"
    finally:
        runtime.unregister("test.boom")


def test_run_once_no_handler_fails_terminally(db_session):
    job = _enqueue(db_session, job_type="test.unregistered", max_attempts=5)
    runtime.run_once(db_session, lease_owner="w1")
    db_session.refresh(job)
    assert job.status == JobStatus.FAILED       # terminal despite attempts remaining
    assert job.error_code == "no_handler"


# ── worker drain ────────────────────────────────────────────────────────────

def test_worker_drains_immediately_when_stopped(db_session):
    worker = runtime.JobWorker("w1")
    worker.request_stop()
    worker.run()  # returns at once because stop is set
    assert worker.stop.is_set()


# ── scheduler tick ──────────────────────────────────────────────────────────

def test_scheduler_tick_promotes_and_recovers(db_session):
    now = utc_now_naive()
    # A retry_wait job already due → should be promoted to queued.
    db_session.add(models.BackgroundJob(
        job_id="r1", job_type="t", idempotency_key="r1", status=JobStatus.RETRY_WAIT,
        available_at=now - timedelta(seconds=5), created_at=now, attempt=1))
    # A running job with an expired lease → should be recovered.
    db_session.add(models.BackgroundJob(
        job_id="s1", job_type="t", idempotency_key="s1", status=JobStatus.RUNNING,
        available_at=now, created_at=now, attempt=1, max_attempts=3,
        lease_owner="dead", lease_expires_at=now - timedelta(seconds=1)))
    db_session.commit()
    result = runtime.scheduler_tick(db_session)
    assert result["promoted_retries"] == 1
    assert result["recovered_leases"] == 1


# ── metrics ─────────────────────────────────────────────────────────────────

def test_job_metrics_depth_and_counts(db_session, echo_handler):
    _enqueue(db_session, key="a")
    _enqueue(db_session, key="b")
    m = metrics.job_metrics(db_session)
    assert m["depth"]["queued"] == 2
    assert m["by_type"]["test.echo"]["queued"] == 2
    assert m["oldest_queued_age_seconds"] >= 0


def test_metrics_expired_leases(db_session):
    now = utc_now_naive()
    db_session.add(models.BackgroundJob(
        job_id="x", job_type="t", idempotency_key="x", status=JobStatus.RUNNING,
        available_at=now, created_at=now, lease_owner="w",
        lease_expires_at=now - timedelta(seconds=1)))
    db_session.commit()
    assert metrics.job_metrics(db_session)["expired_leases"] == 1


def test_health_ok_and_degraded(db_session):
    metrics.reset_heartbeats()
    assert metrics.health(db_session)["status"] == "ok"  # empty queue
    now = utc_now_naive()
    db_session.add(models.BackgroundJob(
        job_id="old", job_type="t", idempotency_key="old", status=JobStatus.QUEUED,
        available_at=now - timedelta(hours=1), created_at=now))
    db_session.commit()
    h = metrics.health(db_session, now=now)
    assert h["status"] == "degraded"
    assert "queue_age_slo_breached" in h["reasons"]
    assert "no_live_workers_with_backlog" in h["reasons"]


def test_heartbeat_liveness(db_session):
    metrics.reset_heartbeats()
    now = utc_now_naive()
    metrics.heartbeat("w1", now=now)
    assert "w1" in metrics.live_workers(now=now)
    assert "w1" not in metrics.live_workers(now=now + timedelta(seconds=300))
