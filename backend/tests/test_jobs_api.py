"""Phase 3 — job operability API (list, status, cancel, replay, metrics, health)."""
from datetime import timedelta

from backend import models
from backend.jobs import service
from backend.jobs.states import JobStatus
from backend.models import utc_now_naive


def _enqueue(db, key="k", **kw):
    job = service.enqueue(db, job_type="enrichment", org_id=None, idempotency_key=key,
                          payload={"entity_id": 1}, **kw)
    db.commit()
    return job


def test_list_and_get_job(client, auth_headers, db_session):
    job = _enqueue(db_session)
    r = client.get("/jobs", headers=auth_headers)
    assert r.status_code == 200 and r.json()["count"] >= 1
    r2 = client.get(f"/jobs/{job.job_id}", headers=auth_headers)
    assert r2.status_code == 200 and r2.json()["job_id"] == job.job_id


def test_get_missing_job_404(client, auth_headers):
    assert client.get("/jobs/nope", headers=auth_headers).status_code == 404


def test_cancel_job(client, auth_headers, db_session):
    job = _enqueue(db_session)
    r = client.post(f"/jobs/{job.job_id}/cancel", headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == JobStatus.CANCELLED
    assert db_session.query(models.AuditLog).filter_by(action="job.cancel").count() == 1


def test_cancel_running_conflict(client, auth_headers, db_session):
    _enqueue(db_session)
    job = service.claim(db_session, lease_owner="w1")
    r = client.post(f"/jobs/{job.job_id}/cancel", headers=auth_headers)
    assert r.status_code == 409  # cannot cancel running


def test_replay_failed_job(client, auth_headers, db_session):
    now = utc_now_naive()
    job = models.BackgroundJob(
        job_id="failed-1", job_type="enrichment", idempotency_key="f1",
        status=JobStatus.FAILED, available_at=now, created_at=now,
        attempt=3, max_attempts=3, finished_at=now, error_code="boom")
    db_session.add(job); db_session.commit()
    r = client.post(f"/jobs/{job.job_id}/replay", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["new_job"]["status"] == JobStatus.QUEUED
    assert body["new_job"]["replay_of"] == "failed-1"


def test_metrics_and_health_endpoints(client, auth_headers, db_session):
    _enqueue(db_session)
    m = client.get("/jobs/metrics", headers=auth_headers)
    assert m.status_code == 200 and m.json()["depth"]["queued"] >= 1
    h = client.get("/jobs/health", headers=auth_headers)
    assert h.status_code == 200 and h.json()["status"] in ("ok", "degraded")


def test_endpoints_require_auth(client):
    assert client.get("/jobs").status_code in (401, 403)
    assert client.post("/jobs/x/cancel").status_code in (401, 403)
