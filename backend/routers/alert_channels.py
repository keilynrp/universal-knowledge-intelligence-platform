"""
Sprint 81 — Alert Channels: Slack / Teams / Discord / generic webhook alerts.

Endpoints:
  GET    /alert-channels                — list all channels (admin+)
  POST   /alert-channels                — create channel (admin+, 201)
  GET    /alert-channels/events         — available event catalogue
  GET    /alert-channels/{id}           — get single
  PUT    /alert-channels/{id}           — update
  DELETE /alert-channels/{id}           — delete
  POST   /alert-channels/{id}/test      — send a test alert
"""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from backend import models
from backend.auth import require_role
from backend.database import get_db
from backend.notifications.alert_sender import ALL_EVENTS, ALL_EVENT_IDS, fire_alert
from backend.tenant_access import (
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alert-channels"])

_VALID_TYPES = {"slack", "teams", "discord", "webhook"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _encrypt_url(url: str) -> str:
    try:
        from backend.encryption import encrypt_value
        return encrypt_value(url)
    except Exception:
        return url


def _serialize(c: models.AlertChannel) -> dict:
    return {
        "id":               c.id,
        "name":             c.name,
        "type":             c.type,
        "events":           json.loads(c.events) if c.events else [],
        "is_active":        c.is_active,
        "last_fired_at":    c.last_fired_at.isoformat() if c.last_fired_at else None,
        "last_fire_status": c.last_fire_status,
        "total_fired":      c.total_fired,
        "created_at":       c.created_at.isoformat() if c.created_at else None,
        # webhook_url intentionally omitted from responses (treat like a secret)
    }


# ── Schemas ───────────────────────────────────────────────────────────────────

class AlertChannelCreate(BaseModel):
    name:        str       = Field(min_length=1, max_length=200)
    type:        str       = Field(default="slack", pattern="^(slack|teams|discord|webhook)$")
    webhook_url: str       = Field(min_length=10, max_length=2000)
    events:      List[str] = Field(default_factory=list)


class AlertChannelUpdate(BaseModel):
    name:        Optional[str]       = Field(default=None, min_length=1, max_length=200)
    type:        Optional[str]       = Field(default=None, pattern="^(slack|teams|discord|webhook)$")
    webhook_url: Optional[str]       = Field(default=None, min_length=10, max_length=2000)
    events:      Optional[List[str]] = None
    is_active:   Optional[bool]      = None


# ── Event catalogue ───────────────────────────────────────────────────────────

@router.get("/alert-channels/events", tags=["alert-channels"])
def list_alert_events(_: models.User = Depends(require_role("super_admin", "admin"))):
    return [{"id": e[0], "label": e[1], "description": e[2]} for e in ALL_EVENTS]


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/alert-channels", status_code=201, tags=["alert-channels"])
def create_alert_channel(
    payload: AlertChannelCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    invalid_events = [e for e in payload.events if e not in ALL_EVENT_IDS]
    if invalid_events:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown events: {invalid_events}. Valid: {sorted(ALL_EVENT_IDS)}",
        )
    org_id = resolve_request_org_id(db, current_user)
    ch = models.AlertChannel(
        org_id=persisted_org_id(org_id),
        name=payload.name.strip(),
        type=payload.type,
        webhook_url=_encrypt_url(payload.webhook_url),
        events=json.dumps(payload.events),
        is_active=True,
        total_fired=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return _serialize(ch)


@router.get("/alert-channels", tags=["alert-channels"])
def list_alert_channels(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    channels = (
        scope_query_to_org(db.query(models.AlertChannel), models.AlertChannel, org_id)
        .order_by(models.AlertChannel.id.desc())
        .all()
    )
    return [_serialize(c) for c in channels]


@router.get("/alert-channels/{channel_id}", tags=["alert-channels"])
def get_alert_channel(
    channel_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    ch = get_scoped_record(db, models.AlertChannel, channel_id, org_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Alert channel not found")
    return _serialize(ch)


@router.put("/alert-channels/{channel_id}", tags=["alert-channels"])
def update_alert_channel(
    channel_id: int = Path(..., ge=1),
    payload: AlertChannelUpdate = ...,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    ch = get_scoped_record(db, models.AlertChannel, channel_id, org_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Alert channel not found")
    if payload.name is not None:
        ch.name = payload.name.strip()
    if payload.type is not None:
        ch.type = payload.type
    if payload.webhook_url is not None:
        ch.webhook_url = _encrypt_url(payload.webhook_url)
    if payload.events is not None:
        invalid = [e for e in payload.events if e not in ALL_EVENT_IDS]
        if invalid:
            raise HTTPException(status_code=422, detail=f"Unknown events: {invalid}")
        ch.events = json.dumps(payload.events)
    if payload.is_active is not None:
        ch.is_active = payload.is_active
    db.commit()
    db.refresh(ch)
    return _serialize(ch)


@router.delete("/alert-channels/{channel_id}", tags=["alert-channels"])
def delete_alert_channel(
    channel_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    ch = get_scoped_record(db, models.AlertChannel, channel_id, org_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Alert channel not found")
    db.delete(ch)
    db.commit()
    return {"deleted": channel_id}


@router.post("/alert-channels/{channel_id}/test", tags=["alert-channels"])
def test_alert_channel(
    channel_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Send a test message to verify the channel is configured correctly."""
    org_id = resolve_request_org_id(db, current_user)
    ch = get_scoped_record(db, models.AlertChannel, channel_id, org_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Alert channel not found")
    ok = fire_alert(
        channel_type=ch.type,
        webhook_url_encrypted=ch.webhook_url,
        event="test",
        message="UKIP Alert Channel Test",
        details={"channel": ch.name, "type": ch.type, "status": "This is a test message"},
    )
    return {"success": ok, "channel_id": channel_id, "channel_name": ch.name}
