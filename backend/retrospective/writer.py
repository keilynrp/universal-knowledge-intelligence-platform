"""Idempotent append-only writers for the retrospective layer.

Enforces, at the write boundary (ADR-006 companion inventory §2–3):
- **Registry validation** — only registered families at their current schema
  version may be written.
- **Payload bounds** — serialized JSON payload must be <= ``MAX_PAYLOAD_BYTES``.
- **Idempotency** — a replayed writer with the same
  ``(org_id, type, idempotency_key)`` returns the existing record instead of
  inserting a duplicate.
- **Tenant scope** — ``org_id`` is persisted exactly as resolved by the caller
  (``None`` = governed platform-level aggregate).

The writers never mutate operational tables. Append-only is additionally
enforced by ORM listeners on the models.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from .registry import (
    MAX_PAYLOAD_BYTES,
    resolve_event_version,
    resolve_snapshot_version,
)


class RetrospectiveWriteError(Exception):
    """Base error for retrospective writes."""


class PayloadTooLargeError(RetrospectiveWriteError):
    """Raised when a serialized payload exceeds ``MAX_PAYLOAD_BYTES``."""


class TenantScopeError(RetrospectiveWriteError):
    """Raised when the resolved tenant scope is invalid."""


def _serialize(payload: Any, field: str) -> str:
    """Serialize a payload to bounded JSON, rejecting oversized values."""
    if payload is None:
        raise RetrospectiveWriteError(f"{field} payload is required")
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)
    size = len(encoded.encode("utf-8"))
    if size > MAX_PAYLOAD_BYTES:
        raise PayloadTooLargeError(
            f"{field} payload is {size} bytes; limit is {MAX_PAYLOAD_BYTES} bytes"
        )
    return encoded


def _serialize_optional(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def _validate_org(org_id: int | None) -> int | None:
    if org_id is not None and not isinstance(org_id, int):
        raise TenantScopeError(f"org_id must be an int or None, got {type(org_id).__name__}")
    return org_id


def record_event(
    db: Session,
    *,
    event_type: str,
    org_id: int | None,
    domain_object_type: str,
    domain_object_id: str,
    occurred_at: datetime,
    source: str,
    idempotency_key: str,
    payload: Any,
    actor_type: str = "system",
    actor_id: str | None = None,
    correlation_id: str | None = None,
    lineage: Any | None = None,
    schema_version: int | None = None,
) -> models.RetrospectiveEvent:
    """Idempotently append a governed retrospective event.

    Returns the newly created event, or the pre-existing one if a record with
    the same ``(org_id, event_type, idempotency_key)`` already exists.
    """
    org_id = _validate_org(org_id)
    version = resolve_event_version(event_type, schema_version)
    if not idempotency_key:
        raise RetrospectiveWriteError("idempotency_key is required")

    existing = _find_existing_event(db, org_id, event_type, idempotency_key)
    if existing is not None:
        return existing

    encoded_payload = _serialize(payload, "event")
    record = models.RetrospectiveEvent(
        event_id=uuid.uuid4().hex,
        event_type=event_type,
        schema_version=version,
        org_id=org_id,
        domain_object_type=domain_object_type,
        domain_object_id=str(domain_object_id),
        occurred_at=occurred_at,
        source=source,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        payload=encoded_payload,
        lineage=_serialize_optional(lineage),
    )
    return _insert_or_get(
        db, record, _find_existing_event, org_id, event_type, idempotency_key
    )


def record_snapshot(
    db: Session,
    *,
    snapshot_type: str,
    org_id: int | None,
    subject_type: str,
    subject_id: str,
    valid_at: datetime,
    idempotency_key: str,
    payload: Any,
    lineage: Any | None = None,
    schema_version: int | None = None,
) -> models.RetrospectiveSnapshot:
    """Idempotently append a point-in-time snapshot.

    Returns the newly created snapshot, or the pre-existing one if a record with
    the same ``(org_id, snapshot_type, idempotency_key)`` already exists.
    """
    org_id = _validate_org(org_id)
    version = resolve_snapshot_version(snapshot_type, schema_version)
    if not idempotency_key:
        raise RetrospectiveWriteError("idempotency_key is required")

    existing = _find_existing_snapshot(db, org_id, snapshot_type, idempotency_key)
    if existing is not None:
        return existing

    encoded_payload = _serialize(payload, "snapshot")
    record = models.RetrospectiveSnapshot(
        snapshot_id=uuid.uuid4().hex,
        snapshot_type=snapshot_type,
        schema_version=version,
        org_id=org_id,
        subject_type=subject_type,
        subject_id=str(subject_id),
        valid_at=valid_at,
        idempotency_key=idempotency_key,
        payload=encoded_payload,
        lineage=_serialize_optional(lineage),
    )
    return _insert_or_get(
        db, record, _find_existing_snapshot, org_id, snapshot_type, idempotency_key
    )


# ── Idempotency helpers ─────────────────────────────────────────────────────

def _find_existing_event(db, org_id, event_type, idempotency_key):
    return (
        db.query(models.RetrospectiveEvent)
        .filter(
            models.RetrospectiveEvent.org_id.is_(org_id)
            if org_id is None
            else models.RetrospectiveEvent.org_id == org_id,
            models.RetrospectiveEvent.event_type == event_type,
            models.RetrospectiveEvent.idempotency_key == idempotency_key,
        )
        .first()
    )


def _find_existing_snapshot(db, org_id, snapshot_type, idempotency_key):
    return (
        db.query(models.RetrospectiveSnapshot)
        .filter(
            models.RetrospectiveSnapshot.org_id.is_(org_id)
            if org_id is None
            else models.RetrospectiveSnapshot.org_id == org_id,
            models.RetrospectiveSnapshot.snapshot_type == snapshot_type,
            models.RetrospectiveSnapshot.idempotency_key == idempotency_key,
        )
        .first()
    )


def _insert_or_get(db, record, finder, org_id, type_value, idempotency_key):
    """Insert a record, falling back to the existing row on a unique-key race."""
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = finder(db, org_id, type_value, idempotency_key)
        if existing is not None:
            return existing
        raise
    return record
