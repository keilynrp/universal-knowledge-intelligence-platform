"""
Phase 12 Sprint 51 — Audit Log endpoints
  GET  /audit-log          — paginated list with filters  (admin+)
  GET  /audit-log/stats    — summary counters             (admin+)
  GET  /audit-log/export   — CSV download                 (admin+)
"""

# ruff: noqa: B008 — every endpoint below uses FastAPI's own recommended
# `Depends(...)`/`Query(...)` dependency-injection idiom in an argument default,
# which is exactly what B008 ("no function call as a default") exists to catch
# in ordinary code. Same justification, and same file-level waiver, as
# backend/routers/backup_ops.py.

import csv
import io
import ipaddress
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    href: str | None = Field(default=None, max_length=512)
    kind: str | None = Field(default=None, max_length=40)
    route: str | None = Field(default=None, max_length=512)
    module_label: str | None = Field(default=None, max_length=160)
    domain_id: str | None = Field(default=None, max_length=120)
    api_path: str | None = Field(default=None, max_length=512)
    method: str | None = Field(default=None, max_length=12)
    status: str = Field(default="started", max_length=40)
    status_code: int | None = None
    detail: str | None = Field(default=None, max_length=1000)


# ── Query helper ──────────────────────────────────────────────────────────────

# The first question after finding a suspicious address in an incident is what
# else came from it (#378). The description is shared by every endpoint that
# takes the filter, so they cannot drift apart.
_IP_FILTER = Query(
    default=None,
    max_length=64,
    description="Exact client address, IPv4 or IPv6. Normalised before matching.",
)


# "Everything this session did": the pivot once a session is known to be
# hostile (openspec attribute-and-audit-reads). A session id is opaque, so it is
# matched exactly and only trimmed.
_SESSION_FILTER = Query(
    default=None,
    max_length=64,
    description="Exact session id (the `sid` a token names), as shown in the sessions list.",
)


def _session(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _normalise_ip(value: str | None) -> str | None:
    """Canonical form of an address filter, or a 422 if it is not an address.

    A typo must not look like "this address did nothing": an unparseable
    filter would silently match no row, which is the same answer a clean
    address gives. IPv6 is compared in its compressed form, the form the
    server records from the connection.
    """
    if value is None or not value.strip():
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Not an IP address: {value!r}") from None


def _base_query(
    db: Session,
    action: str | None,
    resource_type: str | None,
    username: str | None,
    from_date: datetime | None,
    to_date: datetime | None,
    ip_address: str | None = None,
    session_id: str | None = None,
):
    q = db.query(models.AuditLog)
    if action:
        # Case-insensitive: most actions are upper case (CREATE, ASSISTANT_ACTION)
        # but not all — `api_key.scope_violation` is written lower case, and
        # upper-casing the argument made it permanently unfindable.
        q = q.filter(func.lower(models.AuditLog.action) == action.lower())
    if resource_type:
        q = q.filter(models.AuditLog.entity_type == resource_type)
    if username:
        q = q.filter(models.AuditLog.username == username)
    if ip_address:
        q = q.filter(models.AuditLog.ip_address == ip_address)
    if session_id:
        q = q.filter(models.AuditLog.session_id == session_id)
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
    action:        str | None      = Query(default=None),
    resource_type: str | None      = Query(default=None),
    username:      str | None      = Query(default=None),
    from_date:     datetime | None = Query(default=None),
    to_date:       datetime | None = Query(default=None),
    ip_address:    str | None      = _IP_FILTER,
    session_id:    str | None      = _SESSION_FILTER,
    skip:          int                = Query(default=0, ge=0),
    limit:         int                = Query(default=50, ge=1, le=200),
    db:            Session            = Depends(get_db),
    _:             models.User        = Depends(require_role("super_admin", "admin")),
):
    """Paginated audit log, newest first. Admin+ only."""
    q = _base_query(
        db, action, resource_type, username, from_date, to_date,
        _normalise_ip(ip_address), _session(session_id),
    )
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
    ip_address: str | None = _IP_FILTER,
    session_id: str | None = _SESSION_FILTER,
    db: Session    = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Summary counters over the audit log, or over one address and/or session.

    With `ip_address` or `session_id` every counter is scoped to it, so an
    incident can size what came from an address or a session in one request
    before paging through the rows.
    """
    ip = _normalise_ip(ip_address)
    sid = _session(session_id)

    def scoped(q):
        if ip:
            q = q.filter(models.AuditLog.ip_address == ip)
        if sid:
            q = q.filter(models.AuditLog.session_id == sid)
        return q

    total = scoped(db.query(models.AuditLog)).count()

    by_action = {
        row.action: row.cnt
        for row in scoped(db.query(
            models.AuditLog.action,
            func.count(models.AuditLog.id).label("cnt"),
        )).group_by(models.AuditLog.action).all()
    }

    by_resource = {
        row.entity_type: row.cnt
        for row in scoped(db.query(
            models.AuditLog.entity_type,
            func.count(models.AuditLog.id).label("cnt"),
        )).group_by(models.AuditLog.entity_type).all()
    }

    top_users = [
        {"username": row.username or "anonymous", "count": row.cnt}
        for row in scoped(db.query(
            models.AuditLog.username,
            func.count(models.AuditLog.id).label("cnt"),
        ))
        .group_by(models.AuditLog.username)
        .order_by(func.count(models.AuditLog.id).desc())
        .limit(10)
        .all()
    ]

    # Last 7 days — daily counts.
    # Built from ORM constructs rather than raw SQL: the previous literal used
    # SQLite-only date arithmetic (`DATE('now', '-6 days')`) and was a 500 on the
    # PostgreSQL production runs. `func.date()` is valid on both dialects.
    cutoff = (
        datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        )
        - timedelta(days=6)
    )
    day = func.date(models.AuditLog.created_at)
    daily_rows = (
        scoped(db.query(day.label("day"), func.count(models.AuditLog.id).label("cnt")))
        .filter(models.AuditLog.created_at >= cutoff)
        .group_by(day)
        .order_by(day)
        .all()
    )
    last_7_days = [{"date": str(r.day), "count": r.cnt} for r in daily_rows]

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
    action:        str | None      = Query(default=None),
    resource_type: str | None      = Query(default=None),
    username:      str | None      = Query(default=None),
    from_date:     datetime | None = Query(default=None),
    to_date:       datetime | None = Query(default=None),
    ip_address:    str | None      = _IP_FILTER,
    session_id:    str | None      = _SESSION_FILTER,
    db:            Session            = Depends(get_db),
    current_user:  models.User        = Depends(require_role("super_admin", "admin")),
):
    """Download filtered audit log as CSV."""
    if request.headers.get("X-Assistant-Action-Id") == "audit-export":
        require_assistant_action(current_user, "audit-export")

    rows = (
        _base_query(
            db, action, resource_type, username, from_date, to_date,
            _normalise_ip(ip_address), _session(session_id),
        )
        .order_by(models.AuditLog.created_at.desc())
        .limit(10_000)          # safety cap
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "username", "action", "resource_type", "resource_id",
        "endpoint", "method", "status_code", "ip_address", "created_at", "details",
        "session_id", "api_key_id",
    ])
    for r in rows:
        writer.writerow([
            r.id, r.username or "", r.action, r.entity_type or "",
            str(r.entity_id) if r.entity_id else "", r.endpoint, r.method,
            r.status_code or "", r.ip_address or "",
            r.created_at.isoformat() if r.created_at else "", r.details or "",
            r.session_id or "", r.api_key_id or "",
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
        "session_id":    r.session_id,
        "api_key_id":    r.api_key_id,
        "created_at":    r.created_at.isoformat() if r.created_at else None,
        "details":       details,
    }
