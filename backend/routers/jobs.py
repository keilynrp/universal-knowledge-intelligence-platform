"""Operability API for the durable job runtime (ADR-007, task 3.3).

Tenant-scoped, role-gated: status, list, cancellation, authorized replay, queue
metrics, and health. Cross-tenant access returns no data and performs no
transition. Cancellation and replay require an elevated role and emit audit.
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend import models
from backend.auth import require_role
from backend.database import get_db
from backend.jobs import metrics, service
from backend.tenant_access import resolve_request_org_id

router = APIRouter(prefix="/jobs", tags=["jobs"])

_READ_ROLES = ("super_admin", "admin", "editor", "viewer")
_OPERATE_ROLES = ("super_admin", "admin")
_LIST_CAP = 200


def _is_super_admin(user: models.User) -> bool:
    return getattr(user, "role", None) == "super_admin"


def _serialize(job: models.BackgroundJob) -> dict:
    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "org_id": job.org_id,
        "status": job.status,
        "priority": job.priority,
        "attempt": job.attempt,
        "max_attempts": job.max_attempts,
        "available_at": job.available_at,
        "lease_owner": job.lease_owner,
        "lease_expires_at": job.lease_expires_at,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error_code": job.error_code,
        "error_detail": job.error_detail,
        "correlation_id": job.correlation_id,
        "replay_of": job.replay_of,
        "payload": json.loads(job.payload) if job.payload else None,  # refs only
    }


def _scoped_query(db: Session, user: models.User):
    """Query scoped to the caller's tenant; super_admin sees all tenants."""
    q = db.query(models.BackgroundJob)
    if _is_super_admin(user):
        return q
    org_id = resolve_request_org_id(db, user)
    return q.filter(models.BackgroundJob.org_id == org_id)


def _get_scoped(db: Session, user: models.User, job_id: str) -> models.BackgroundJob:
    job = _scoped_query(db, user).filter(models.BackgroundJob.job_id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("")
def list_jobs(
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=_LIST_CAP),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_READ_ROLES)),
):
    """List jobs in the caller's tenant scope, newest first."""
    q = _scoped_query(db, current_user)
    if status:
        q = q.filter(models.BackgroundJob.status == status)
    if job_type:
        q = q.filter(models.BackgroundJob.job_type == job_type)
    rows = q.order_by(models.BackgroundJob.id.desc()).limit(limit).all()
    return {"count": len(rows), "jobs": [_serialize(j) for j in rows]}


@router.get("/metrics")
def job_metrics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_READ_ROLES)),
):
    """Queue depth, status counts, oldest-queued age by type, expired leases."""
    org_id = None if _is_super_admin(current_user) else resolve_request_org_id(db, current_user)
    return metrics.job_metrics(db, org_id=org_id)


@router.get("/health")
def job_health(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_OPERATE_ROLES)),
):
    """Runtime health: queue age SLO, expired leases, worker liveness."""
    return metrics.health(db)


@router.get("/{job_id}")
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_READ_ROLES)),
):
    """Status + bounded diagnostics for one job (tenant-scoped)."""
    return _serialize(_get_scoped(db, current_user, job_id))


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_OPERATE_ROLES)),
):
    """Cancel a non-running, non-terminal job (audited)."""
    job = _get_scoped(db, current_user, job_id)
    try:
        service.cancel(db, job, actor_id=current_user.id)
    except Exception as exc:  # InvalidTransition → 409
        raise HTTPException(status_code=409, detail=str(exc))
    return _serialize(job)


@router.post("/{job_id}/replay")
def replay_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_OPERATE_ROLES)),
):
    """Replay a terminal failed job as a new job (audited; original preserved)."""
    job = _get_scoped(db, current_user, job_id)
    try:
        new = service.replay(db, job, actor_id=current_user.id)
    except service.JobError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"replayed_from": job.job_id, "new_job": _serialize(new)}
