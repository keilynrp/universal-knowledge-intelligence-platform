"""Platform authentication and SSO settings."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import require_role
from backend.database import get_db

router = APIRouter(tags=["settings"])


def sso_provider_configured() -> bool:
    return all(
        (os.environ.get(name) or "").strip()
        for name in ("SSO_CLIENT_ID", "SSO_CLIENT_SECRET", "SSO_METADATA_URL")
    )


def get_or_create_auth_settings(db: Session) -> models.PlatformAuthSettings:
    settings = db.get(models.PlatformAuthSettings, 1)
    if not settings:
        models.PlatformAuthSettings.__table__.create(bind=db.get_bind(), checkfirst=True)
        settings = models.PlatformAuthSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def response_from_settings(settings: models.PlatformAuthSettings) -> schemas.PlatformAuthSettingsResponse:
    return schemas.PlatformAuthSettingsResponse(
        sso_enabled=bool(settings.sso_enabled),
        sso_login_button_visible=bool(settings.sso_login_button_visible),
        sso_provider_label=settings.sso_provider_label or "SSO",
        sso_auto_provision=bool(settings.sso_auto_provision),
        sso_default_role=settings.sso_default_role or "viewer",
        sso_allowed_domains=settings.sso_allowed_domains or "",
        sso_provider_configured=sso_provider_configured(),
    )


@router.get("/auth/sso/settings", response_model=schemas.PublicSsoSettingsResponse)
def get_public_sso_settings(db: Session = Depends(get_db)):
    settings = get_or_create_auth_settings(db)
    return schemas.PublicSsoSettingsResponse(
        sso_enabled=bool(settings.sso_enabled),
        sso_login_button_visible=bool(settings.sso_login_button_visible),
        sso_provider_label=settings.sso_provider_label or "SSO",
        sso_provider_configured=sso_provider_configured(),
    )


@router.get("/settings/auth", response_model=schemas.PlatformAuthSettingsResponse)
def get_platform_auth_settings(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    return response_from_settings(get_or_create_auth_settings(db))


@router.put("/settings/auth", response_model=schemas.PlatformAuthSettingsResponse)
def update_platform_auth_settings(
    payload: schemas.PlatformAuthSettingsUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    settings = get_or_create_auth_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip()
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return response_from_settings(settings)
