"""EPIC-017 shared helpers for secret rotation: encrypted-column registry,
cadence constant, and evidence read/write. Imported by the re-encrypt ops
script and the secrets ops health check.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend import models

# Single canonical cadence source (days). Read once.
SECRET_ROTATION_MAX_AGE_DAYS = int(os.environ.get("SECRET_ROTATION_MAX_AGE_DAYS", "90"))

# DB columns encrypted with ENCRYPTION_KEY (verified via encrypt() call sites).
ENCRYPTED_COLUMNS = [
    (models.AIIntegration, "api_key"),
    (models.StoreConnection, "api_key"),
    (models.StoreConnection, "api_secret"),
    (models.StoreConnection, "access_token"),
]


def last_rotation_at(db: Session, secret_name: str) -> Optional[datetime]:
    row = (
        db.query(models.SecretRotationEvent)
        .filter(models.SecretRotationEvent.secret_name == secret_name)
        .order_by(models.SecretRotationEvent.rotated_at.desc())
        .first()
    )
    return row.rotated_at if row else None


def record_rotation_event(
    db: Session,
    *,
    secret_name: str,
    operator: str,
    rows_reencrypted: Optional[int] = None,
    old_key_fingerprint: Optional[str] = None,
    new_key_fingerprint: Optional[str] = None,
    notes: Optional[str] = None,
) -> models.SecretRotationEvent:
    event = models.SecretRotationEvent(
        secret_name=secret_name,
        rotated_at=datetime.now(timezone.utc),
        operator=operator,
        rows_reencrypted=rows_reencrypted,
        old_key_fingerprint=old_key_fingerprint,
        new_key_fingerprint=new_key_fingerprint,
        notes=notes,
    )
    db.add(event)
    db.commit()
    return event


def encryption_retiring_keys_present() -> bool:
    from backend.encryption import _parse_keys
    return bool(_parse_keys(os.environ.get("ENCRYPTION_KEYS_RETIRING")))


def jwt_retiring_keys_present() -> bool:
    raw = os.environ.get("JWT_SECRET_KEYS_RETIRING")
    return bool([p for p in (raw or "").split(",") if p.strip()])
