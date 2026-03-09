"""
Email Notification Settings endpoints (Sprint 43).
  GET    /notifications/settings  — admin+
  PUT    /notifications/settings  — admin+
  POST   /notifications/test      — admin+ (sends test email)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import require_role
from backend.database import get_db
from backend.notifications.email_sender import send_notification

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_or_create_settings(db: Session) -> models.NotificationSettings:
    s = db.get(models.NotificationSettings, 1)
    if not s:
        s = models.NotificationSettings(id=1)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _encrypt_password(plain: str) -> str:
    """Encrypt SMTP password using the Fernet key, if available."""
    if not plain:
        return ""
    try:
        from backend.encryption import encrypt_value
        return encrypt_value(plain)
    except Exception:
        logger.warning("Could not encrypt SMTP password; storing as-is")
        return plain


# ── GET /notifications/settings ───────────────────────────────────────────────

@router.get("/notifications/settings", tags=["notifications"])
def get_notification_settings(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    s = _get_or_create_settings(db)
    return schemas.NotificationSettingsResponse.model_validate(s)


# ── PUT /notifications/settings ───────────────────────────────────────────────

@router.put("/notifications/settings", tags=["notifications"])
def update_notification_settings(
    payload: schemas.NotificationSettingsUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    s = _get_or_create_settings(db)
    data = payload.model_dump(exclude_unset=True)

    if "smtp_password" in data:
        plain = data.pop("smtp_password")
        if plain:
            s.smtp_password = _encrypt_password(plain)
    for field, value in data.items():
        setattr(s, field, value)

    db.commit()
    db.refresh(s)
    return schemas.NotificationSettingsResponse.model_validate(s)


# ── POST /notifications/test ──────────────────────────────────────────────────

@router.post("/notifications/test", tags=["notifications"])
def test_notification(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    s = _get_or_create_settings(db)
    sent = send_notification(
        s,
        subject="UKIP: Test Notification",
        body="This is a test email from the UKIP platform. If you received this, your SMTP settings are working correctly.",
    )
    return {"sent": sent}
