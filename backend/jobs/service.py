"""Durable job services: enqueue, claim, lease, retry, cancel, replay, recovery.

Broker-free PostgreSQL lease queue (ADR-007, tasks 2.2–2.4). Claims are atomic:
``FOR UPDATE SKIP LOCKED`` on PostgreSQL, compare-and-set ``UPDATE … WHERE`` on
SQLite — both guarantee at most one worker claims a job. Every lifecycle-changing
operator action (cancel, replay) and every invalid transition emit a sanitized
audit event. Payloads never carry reusable credentials.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..models import utc_now_naive
from .states import JobStatus, assert_transition, is_terminal

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_LEASE_SECONDS = 60
_BACKOFF_BASE_SECONDS = 10
_BACKOFF_CAP_SECONDS = 3600


class JobError(Exception):
    """Base error for job service operations."""


def _sanitize(detail: Optional[str], limit: int = 2000) -> Optional[str]:
    """Bound error detail; payloads/secrets are never routed here by callers."""
    if detail is None:
        return None
    return detail[:limit]


def _audit(db: Session, action: str, job: models.BackgroundJob,
           actor_id: Optional[int] = None, extra: Optional[dict] = None) -> None:
    """Write a sanitized audit row for a job lifecycle action."""
    details = {"job_id": job.job_id, "job_type": job.job_type,
               "org_id": job.org_id, "status": job.status}
    if job.error_code:
        details["error_code"] = job.error_code
    if extra:
        details.update(extra)
    db.add(models.AuditLog(
        action=action, entity_type="background_job", entity_id=job.id,
        user_id=actor_id, details=json.dumps(details)))


def _backoff(attempt: int) -> int:
    return min(_BACKOFF_BASE_SECONDS * (2 ** max(attempt - 1, 0)), _BACKOFF_CAP_SECONDS)


# ── 2.2 Producer: enqueue with tenant-scoped idempotency ────────────────────

def enqueue(
    db: Session,
    *,
    job_type: str,
    org_id: Optional[int],
    idempotency_key: str,
    payload: Any = None,
    requested_by: Optional[int] = None,
    priority: int = 100,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    available_at: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
    payload_version: int = 1,
) -> models.BackgroundJob:
    """Persist a durable job (transactional). Idempotent per (org_id, job_type, key).

    Returns the existing job if one with the same idempotency key already exists —
    a duplicate producer never creates a second job.
    """
    if not idempotency_key:
        raise JobError("idempotency_key is required")
    existing = _find_by_key(db, org_id, job_type, idempotency_key)
    if existing is not None:
        return existing
    job = models.BackgroundJob(
        job_id=uuid.uuid4().hex,
        job_type=job_type,
        org_id=org_id,
        requested_by=requested_by,
        idempotency_key=idempotency_key,
        payload_version=payload_version,
        payload=json.dumps(payload) if payload is not None else None,
        status=JobStatus.QUEUED,
        priority=priority,
        attempt=0,
        max_attempts=max_attempts,
        available_at=available_at or utc_now_naive(),
        correlation_id=correlation_id,
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        dup = _find_by_key(db, org_id, job_type, idempotency_key)
        if dup is not None:
            return dup
        raise
    return job


def _find_by_key(db, org_id, job_type, idempotency_key):
    return (
        db.query(models.BackgroundJob)
        .filter(
            models.BackgroundJob.org_id.is_(org_id) if org_id is None
            else models.BackgroundJob.org_id == org_id,
            models.BackgroundJob.job_type == job_type,
            models.BackgroundJob.idempotency_key == idempotency_key,
        )
        .first()
    )


# ── 2.3 Claim (atomic) + lease ──────────────────────────────────────────────

def claim(
    db: Session,
    *,
    lease_owner: str,
    job_type: Optional[str] = None,
    lease_seconds: int = _DEFAULT_LEASE_SECONDS,
    now: Optional[datetime] = None,
) -> Optional[models.BackgroundJob]:
    """Atomically claim the next due job → RUNNING with a lease. Returns None if idle."""
    now = now or utc_now_naive()
    is_pg = db.bind.dialect.name == "postgresql"
    candidate_id = _select_candidate_id(db, job_type, now, is_pg)
    if candidate_id is None:
        return None
    lease_expires = now + timedelta(seconds=lease_seconds)
    # Compare-and-set: only the worker that flips QUEUED→RUNNING wins.
    res = db.execute(
        update(models.BackgroundJob)
        .where(
            models.BackgroundJob.id == candidate_id,
            models.BackgroundJob.status == JobStatus.QUEUED,
        )
        .values(
            status=JobStatus.RUNNING,
            lease_owner=lease_owner,
            lease_expires_at=lease_expires,
            started_at=now,
            attempt=models.BackgroundJob.attempt + 1,
        )
    )
    if res.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    return db.get(models.BackgroundJob, candidate_id)


def _select_candidate_id(db, job_type, now, is_pg) -> Optional[int]:
    conds = ["status = :queued", "available_at <= :now"]
    params: dict = {"queued": JobStatus.QUEUED, "now": now}
    if job_type is not None:
        conds.append("job_type = :jt")
        params["jt"] = job_type
    where = " AND ".join(conds)
    suffix = "FOR UPDATE SKIP LOCKED" if is_pg else ""
    sql = text(
        f"SELECT id FROM background_jobs WHERE {where} "
        f"ORDER BY priority ASC, available_at ASC, id ASC LIMIT 1 {suffix}"
    )
    row = db.execute(sql, params).first()
    return row[0] if row else None


def renew_lease(db: Session, job: models.BackgroundJob, *, lease_owner: str,
                lease_seconds: int = _DEFAULT_LEASE_SECONDS,
                now: Optional[datetime] = None) -> bool:
    """Extend the lease iff the job is still RUNNING and owned by ``lease_owner``."""
    now = now or utc_now_naive()
    res = db.execute(
        update(models.BackgroundJob)
        .where(
            models.BackgroundJob.id == job.id,
            models.BackgroundJob.status == JobStatus.RUNNING,
            models.BackgroundJob.lease_owner == lease_owner,
        )
        .values(lease_expires_at=now + timedelta(seconds=lease_seconds))
    )
    db.commit()
    return res.rowcount == 1


# ── Terminal / retry transitions ────────────────────────────────────────────

def complete(db: Session, job: models.BackgroundJob, now: Optional[datetime] = None) -> None:
    assert_transition(job.status, JobStatus.SUCCEEDED)
    job.status = JobStatus.SUCCEEDED
    job.finished_at = now or utc_now_naive()
    job.lease_owner = None
    job.lease_expires_at = None
    db.add(job)
    db.commit()


def fail(db: Session, job: models.BackgroundJob, *, error_code: str,
         error_detail: Optional[str] = None, now: Optional[datetime] = None) -> str:
    """Fail a running job: RETRY_WAIT with backoff if attempts remain, else FAILED.

    Returns the resulting status.
    """
    now = now or utc_now_naive()
    job.error_code = error_code[:60]
    job.error_detail = _sanitize(error_detail)
    job.lease_owner = None
    job.lease_expires_at = None
    if job.attempt < job.max_attempts:
        assert_transition(job.status, JobStatus.RETRY_WAIT)
        job.status = JobStatus.RETRY_WAIT
        job.available_at = now + timedelta(seconds=_backoff(job.attempt))
    else:
        assert_transition(job.status, JobStatus.FAILED)
        job.status = JobStatus.FAILED
        job.finished_at = now
    db.add(job)
    db.commit()
    return job.status


def promote_retry_ready(db: Session, now: Optional[datetime] = None) -> int:
    """Move due RETRY_WAIT jobs back to QUEUED. Returns count promoted."""
    now = now or utc_now_naive()
    res = db.execute(
        update(models.BackgroundJob)
        .where(
            models.BackgroundJob.status == JobStatus.RETRY_WAIT,
            models.BackgroundJob.available_at <= now,
        )
        .values(status=JobStatus.QUEUED)
    )
    db.commit()
    return res.rowcount or 0


# ── 2.3 Recovery supervisor ─────────────────────────────────────────────────

def recover_abandoned_leases(db: Session, now: Optional[datetime] = None) -> int:
    """Make expired RUNNING leases eligible for retry (or fail if exhausted).

    Returns the number of jobs recovered.
    """
    now = now or utc_now_naive()
    stale = (
        db.query(models.BackgroundJob)
        .filter(
            models.BackgroundJob.status == JobStatus.RUNNING,
            models.BackgroundJob.lease_expires_at.isnot(None),
            models.BackgroundJob.lease_expires_at < now,
        )
        .all()
    )
    for job in stale:
        fail(db, job, error_code="lease_expired",
             error_detail="worker lease expired; recovered by supervisor", now=now)
    return len(stale)


# ── Cancellation & replay (audited, operator actions) ───────────────────────

def cancel(db: Session, job: models.BackgroundJob, *, actor_id: Optional[int] = None) -> None:
    """Cancel a non-running, non-terminal job. Emits an audit event."""
    assert_transition(job.status, JobStatus.CANCELLED)
    job.status = JobStatus.CANCELLED
    job.finished_at = utc_now_naive()
    db.add(job)
    _audit(db, "job.cancel", job, actor_id=actor_id)
    db.commit()


def replay(db: Session, job: models.BackgroundJob, *,
           actor_id: Optional[int] = None) -> models.BackgroundJob:
    """Replay a terminal FAILED job as a NEW job. Preserves the original history.

    Emits an attributable audit event; the original row is never mutated.
    """
    if job.status != JobStatus.FAILED:
        raise JobError(f"only failed jobs can be replayed (status={job.status})")
    new = models.BackgroundJob(
        job_id=uuid.uuid4().hex,
        job_type=job.job_type,
        org_id=job.org_id,
        requested_by=actor_id if actor_id is not None else job.requested_by,
        idempotency_key=f"{job.idempotency_key}:replay:{uuid.uuid4().hex[:8]}",
        payload_version=job.payload_version,
        payload=job.payload,
        status=JobStatus.QUEUED,
        priority=job.priority,
        attempt=0,
        max_attempts=job.max_attempts,
        available_at=utc_now_naive(),
        correlation_id=job.correlation_id,
        replay_of=job.job_id,
    )
    db.add(new)
    _audit(db, "job.replay", job, actor_id=actor_id, extra={"replay_job_id": new.job_id})
    db.commit()
    return new


# ── 2.4 Retention ───────────────────────────────────────────────────────────

def purge_terminal_jobs(db: Session, *, older_than: datetime) -> int:
    """Governed retention: delete terminal jobs finished before ``older_than``."""
    res = db.execute(
        text(
            "DELETE FROM background_jobs WHERE status IN "
            "('succeeded','failed','cancelled') AND finished_at IS NOT NULL "
            "AND finished_at < :cutoff"
        ),
        {"cutoff": older_than},
    )
    db.commit()
    return res.rowcount or 0
