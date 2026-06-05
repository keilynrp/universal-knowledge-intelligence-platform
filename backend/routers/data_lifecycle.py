"""EPIC-016 — Data lifecycle admin endpoints.

Slice 2 (US-071): subject/tenant export (DSAR).
Slice 3 (US-072): cascade deletion / right to erasure.
Slice 4 (US-073): retention policy management + manual purge trigger.

POST /admin/data-lifecycle/export
  — admin-only; returns a portable JSON bundle of all org-scoped data for
    the active tenant, and records a DataLifecycleEvent audit trail.
POST /admin/data-lifecycle/delete
  — admin-only; erases all org-scoped data in DB + ChromaDB, with a strong
    confirmation echo and a DataLifecycleEvent audit trail.
GET  /admin/data-lifecycle/events
  — admin-only; list lifecycle events for the active org.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.services.data_lifecycle import (
    collect_subject_data,
    complete_event,
    delete_subject_data,
    purge_expired_orgs,
    record_event,
)
from backend.tenant_access import resolve_request_org_id, scope_query_to_org

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/data-lifecycle", tags=["admin", "data-lifecycle"])


class DeletionRequest(BaseModel):
    # Explicit confirmation: caller must echo back "DELETE org <org_id>" to proceed.
    confirm: str


@router.post("/export")
def export_subject_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
) -> JSONResponse:
    """Export all tenant-scoped data for the active organization.

    Returns a portable JSON bundle keyed by surface (entities, annotations, …)
    plus a ``_counts`` summary. Records a DataLifecycleEvent for the audit trail.
    The ``Content-Disposition`` header suggests a filename for download.
    """
    org_id = resolve_request_org_id(db, current_user)

    event = record_event(
        db,
        org_id=org_id,
        action="export",
        subject_type="org",
        subject_ref=str(org_id) if org_id is not None else "legacy_global",
        requested_by=current_user.id,
        scope={"org_id": org_id},
    )

    try:
        bundle = collect_subject_data(db, org_id)
        counts = bundle.get("_counts", {})
        complete_event(db, event, status="completed", evidence=counts)
    except Exception as exc:
        complete_event(db, event, status="failed", evidence={"error": str(exc)})
        logger.exception("DSAR export failed for org_id=%s", org_id)
        raise

    return JSONResponse(
        content=bundle,
        headers={
            "Content-Disposition": (
                f'attachment; filename="ukip-export-org{org_id}.json"'
            )
        },
    )


@router.post("/delete")
def delete_tenant_data(
    payload: DeletionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
) -> dict:
    """Erase all org-scoped data for the active tenant (right to erasure / GDPR Art. 17).

    **Irreversible.** Requires an explicit confirmation string:
        ``{"confirm": "DELETE org <org_id>"}``

    Cascade: erases every tenant-owned DB surface plus the corresponding
    ChromaDB vector documents. DataLifecycleEvent audit records are retained
    as compliance evidence. Records a completed event with per-store counts.
    """
    org_id = resolve_request_org_id(db, current_user)
    expected = f"DELETE org {org_id}"
    if payload.confirm != expected:
        raise HTTPException(
            status_code=422,
            detail=f"Confirmation mismatch. Expected: {expected!r}",
        )

    event = record_event(
        db,
        org_id=org_id,
        action="deletion",
        subject_type="org",
        subject_ref=str(org_id) if org_id is not None else "legacy_global",
        requested_by=current_user.id,
        scope={"org_id": org_id},
    )

    try:
        counts = delete_subject_data(db, org_id)
        complete_event(db, event, status="completed", evidence=counts)
    except Exception as exc:
        complete_event(db, event, status="failed", evidence={"error": str(exc)})
        logger.exception("Cascade deletion failed for org_id=%s", org_id)
        raise

    return {"deleted": True, "org_id": org_id, "evidence": counts}


@router.get("/events")
def list_lifecycle_events(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
) -> list[dict]:
    """List all lifecycle events for the active organization, newest first."""
    org_id = resolve_request_org_id(db, current_user)
    events = (
        scope_query_to_org(
            db.query(models.DataLifecycleEvent),
            models.DataLifecycleEvent,
            org_id,
        )
        .order_by(models.DataLifecycleEvent.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": e.id,
            "action": e.action,
            "subject_type": e.subject_type,
            "subject_ref": e.subject_ref,
            "status": e.status,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
        }
        for e in events
    ]


# ── Slice 4 (US-073): Retention policy endpoints ─────────────────────────────

class RetentionPolicyUpsert(BaseModel):
    data_class: str = "all"
    retention_days: int | None = None  # None disables auto-purge


@router.get("/retention")
def get_retention_policy(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
) -> dict:
    """Return the retention policy for the active org (or the platform default if none set)."""
    org_id = resolve_request_org_id(db, current_user)
    policy = db.query(models.RetentionPolicy).filter(
        models.RetentionPolicy.org_id == (org_id if org_id is not None else None)
    ).first()
    if not policy:
        return {"org_id": org_id, "data_class": "all", "retention_days": None}
    return {
        "id": policy.id,
        "org_id": policy.org_id,
        "data_class": policy.data_class,
        "retention_days": policy.retention_days,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
    }


@router.put("/retention")
def upsert_retention_policy(
    payload: RetentionPolicyUpsert,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
) -> dict:
    """Set or update the retention policy for the active org."""
    org_id = resolve_request_org_id(db, current_user)
    from backend.tenant_access import persisted_org_id
    persisted = persisted_org_id(org_id)

    policy = db.query(models.RetentionPolicy).filter(
        models.RetentionPolicy.org_id == persisted,
        models.RetentionPolicy.data_class == payload.data_class,
    ).first()
    if policy:
        policy.retention_days = payload.retention_days
    else:
        policy = models.RetentionPolicy(
            org_id=persisted,
            data_class=payload.data_class,
            retention_days=payload.retention_days,
        )
        db.add(policy)
    db.commit()
    db.refresh(policy)
    return {"org_id": policy.org_id, "data_class": policy.data_class,
            "retention_days": policy.retention_days}


@router.post("/purge")
def trigger_retention_purge(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin")),
) -> dict:
    """Manually trigger a retention purge run (super_admin only).

    Scans all orgs with a retention policy and purges expired data.
    Same logic as the scheduled RetentionPurger loop.
    """
    summary = purge_expired_orgs(db)
    return {"purged_orgs": len(summary), "detail": summary}
