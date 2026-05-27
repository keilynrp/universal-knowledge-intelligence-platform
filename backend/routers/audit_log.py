"""
Phase 12 Sprint 51 — Audit Log endpoints
  GET  /audit-log          — paginated list with filters  (admin+)
  GET  /audit-log/stats    — summary counters             (admin+)
  GET  /audit-log/export   — CSV download                 (admin+)
"""
import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.services.assistant_actions import require_assistant_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit-log", tags=["audit"])


class AssistantActionAuditPayload(BaseModel):
    action_id: str = Field(..., min_length=1, max_length=120)
    label: str = Field(..., min_length=1, max_length=240)
    href: Optional[str] = Field(default=None, max_length=512)
    kind: Optional[str] = Field(default=None, max_length=40)
    route: Optional[str] = Field(default=None, max_length=512)
    module_label: Optional[str] = Field(default=None, max_length=160)
    domain_id: Optional[str] = Field(default=None, max_length=120)
    api_path: Optional[str] = Field(default=None, max_length=512)
    method: Optional[str] = Field(default=None, max_length=12)
    status: str = Field(default="started", max_length=40)
    status_code: Optional[int] = None
    detail: Optional[str] = Field(default=None, max_length=1000)


# ── Query helper ──────────────────────────────────────────────────────────────

def _base_query(
    db: Session,
    action: Optional[str],
    resource_type: Optional[str],
    username: Optional[str],
    from_date: Optional[datetime],
    to_date: Optional[datetime],
):
    q = db.query(models.AuditLog)
    if action:
        q = q.filter(models.AuditLog.action == action.upper())
    if resource_type:
        q = q.filter(models.AuditLog.entity_type == resource_type)
    if username:
        q = q.filter(models.AuditLog.username == username)
    if from_date:
        q = q.filter(models.AuditLog.created_at >= from_date)
    if to_date:
        q = q.filter(models.AuditLog.created_at <= to_date)
    return q


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/assistant-action")
def record_assistant_action(
    payload: AssistantActionAuditPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Record a contextual UKIP Assistant action without granting audit-log access."""
    endpoint = payload.api_path or payload.href or payload.route or "/assistant"
    details = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    entry = models.AuditLog(
        action="ASSISTANT_ACTION",
        entity_type="assistant_action",
        user_id=current_user.id,
        username=current_user.username,
        endpoint=endpoint,
        method=(payload.method or "ASSISTANT").upper(),
        status_code=payload.status_code,
        ip_address=request.client.host if request.client else None,
        details=json.dumps(details),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    logger.info("Recorded assistant action audit event id=%s action_id=%s", entry.id, payload.action_id)
    return {"recorded": True, "id": entry.id}


@router.get("")
def list_audit_log(
    action:        Optional[str]      = Query(default=None),
    resource_type: Optional[str]      = Query(default=None),
    username:      Optional[str]      = Query(default=None),
    from_date:     Optional[datetime] = Query(default=None),
    to_date:       Optional[datetime] = Query(default=None),
    skip:          int                = Query(default=0, ge=0),
    limit:         int                = Query(default=50, ge=1, le=200),
    db:            Session            = Depends(get_db),
    _:             models.User        = Depends(require_role("super_admin", "admin")),
):
    """Paginated audit log, newest first. Admin+ only."""
    q = _base_query(db, action, resource_type, username, from_date, to_date)
    total = q.count()
    rows  = q.order_by(models.AuditLog.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "skip":  skip,
        "limit": limit,
        "items": [_serialize(r) for r in rows],
    }


@router.get("/stats")
def audit_stats(
    db: Session    = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Summary counters over the entire audit log."""
    total = db.query(models.AuditLog).count()

    by_action = {
        row.action: row.cnt
        for row in db.query(
            models.AuditLog.action,
            func.count(models.AuditLog.id).label("cnt"),
        ).group_by(models.AuditLog.action).all()
    }

    by_resource = {
        row.entity_type: row.cnt
        for row in db.query(
            models.AuditLog.entity_type,
            func.count(models.AuditLog.id).label("cnt"),
        ).group_by(models.AuditLog.entity_type).all()
    }

    top_users = [
        {"username": row.username or "anonymous", "count": row.cnt}
        for row in db.query(
            models.AuditLog.username,
            func.count(models.AuditLog.id).label("cnt"),
        )
        .group_by(models.AuditLog.username)
        .order_by(func.count(models.AuditLog.id).desc())
        .limit(10)
        .all()
    ]

    # Last 7 days — daily counts
    from sqlalchemy import text as _text
    daily_rows = db.execute(_text(
        "SELECT DATE(created_at) AS day, COUNT(*) AS cnt "
        "FROM audit_logs "
        "WHERE created_at >= DATE('now', '-6 days') "
        "GROUP BY day ORDER BY day"
    )).fetchall()
    last_7_days = [{"date": str(r[0]), "count": r[1]} for r in daily_rows]

    return {
        "total":       total,
        "by_action":   by_action,
        "by_resource": by_resource,
        "top_users":   top_users,
        "last_7_days": last_7_days,
    }


@router.get("/export")
def export_csv(
    request:       Request,
    action:        Optional[str]      = Query(default=None),
    resource_type: Optional[str]      = Query(default=None),
    username:      Optional[str]      = Query(default=None),
    from_date:     Optional[datetime] = Query(default=None),
    to_date:       Optional[datetime] = Query(default=None),
    db:            Session            = Depends(get_db),
    current_user:  models.User        = Depends(require_role("super_admin", "admin")),
):
    """Download filtered audit log as CSV."""
    if request.headers.get("X-Assistant-Action-Id") == "audit-export":
        require_assistant_action(current_user, "audit-export")

    rows = (
        _base_query(db, action, resource_type, username, from_date, to_date)
        .order_by(models.AuditLog.created_at.desc())
        .limit(10_000)          # safety cap
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "username", "action", "resource_type", "resource_id",
        "endpoint", "method", "status_code", "ip_address", "created_at", "details",
    ])
    for r in rows:
        writer.writerow([
            r.id, r.username or "", r.action, r.entity_type or "",
            str(r.entity_id) if r.entity_id else "", r.endpoint, r.method,
            r.status_code or "", r.ip_address or "",
            r.created_at.isoformat() if r.created_at else "", r.details or "",
        ])

    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="ukip_audit_{ts}.csv"'},
    )


# ── Serialiser ─────────────────────────────────────────────────────────────────

def _serialize(r: models.AuditLog) -> dict:
    details = None
    if r.details:
        try:
            details = json.loads(r.details)
        except json.JSONDecodeError:
            details = {"raw": r.details}
    return {
        "id":            r.id,
        "username":      r.username,
        "action":        r.action,
        "resource_type": r.entity_type,
        "resource_id":   str(r.entity_id) if r.entity_id else None,
        "endpoint":      r.endpoint,
        "method":        r.method,
        "status_code":   r.status_code,
        "ip_address":    r.ip_address,
        "created_at":    r.created_at.isoformat() if r.created_at else None,
        "details":       details,
    }
