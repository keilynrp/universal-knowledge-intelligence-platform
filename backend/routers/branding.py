"""
Custom Branding Settings endpoints (Sprint 44).
  GET  /branding/settings  — PUBLIC (no auth — needed at app load before login)
  PUT  /branding/settings  — admin+
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import require_role
from backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_or_create_settings(db: Session) -> models.BrandingSettings:
    s = db.get(models.BrandingSettings, 1)
    if not s:
        s = models.BrandingSettings(id=1)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


# ── GET /branding/settings ────────────────────────────────────────────────────

@router.get("/branding/settings", tags=["branding"])
def get_branding_settings(db: Session = Depends(get_db)):
    """Public — returns current branding configuration. No auth required."""
    s = _get_or_create_settings(db)
    return schemas.BrandingSettingsResponse.model_validate(s)


# ── PUT /branding/settings ────────────────────────────────────────────────────

@router.put("/branding/settings", tags=["branding"])
def update_branding_settings(
    payload: schemas.BrandingSettingsUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    s = _get_or_create_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    logger.info("Branding settings updated")
    return schemas.BrandingSettingsResponse.model_validate(s)
