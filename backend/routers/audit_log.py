"""
Phase 12 Sprint 51 — Audit Log endpoints
  GET  /audit-log          — paginated list with filters  (admin+)
  GET  /audit-log/stats    — summary counters             (admin+)
  GET  /audit-log/export   — CSV download                 (admin+)
"""
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.auth import require_role
from backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit-log", tags=["audit"])


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
    action:        Optional[str]      = Query(default=None),
    resource_type: Optional[str]      = Query(default=None),
    username:      Optional[str]      = Query(default=None),
    from_date:     Optional[datetime] = Query(default=None),
    to_date:       Optional[datetime] = Query(default=None),
    db:            Session            = Depends(get_db),
    _:             models.User        = Depends(require_role("super_admin", "admin")),
):
    """Download filtered audit log as CSV."""
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
        "endpoint", "method", "status_code", "ip_address", "created_at",
    ])
    for r in rows:
        writer.writerow([
            r.id, r.username or "", r.action, r.entity_type or "",
            str(r.entity_id) if r.entity_id else "", r.endpoint, r.method,
            r.status_code or "", r.ip_address or "",
            r.created_at.isoformat() if r.created_at else "",
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
    }
