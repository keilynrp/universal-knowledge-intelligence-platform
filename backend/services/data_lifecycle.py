"""EPIC-016 — Data lifecycle service.

Slice 1 (US-070): the audit backbone. Records tenant-scoped lifecycle events
(export / deletion / purge) with per-store evidence. Later slices (export,
deletion, retention) write through these helpers so every operation leaves a
traceable record.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend import models
from backend.tenant_access import persisted_org_id

VALID_ACTIONS = {"export", "deletion", "purge"}
VALID_SUBJECT_TYPES = {"org", "user", "entity_owner"}


def record_event(
    db: Session,
    *,
    org_id: int | None,
    action: str,
    subject_type: str,
    subject_ref: str,
    requested_by: int | None,
    scope: dict[str, Any] | None = None,
) -> models.DataLifecycleEvent:
    """Persist a 'started' lifecycle event scoped to the active org."""
    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid lifecycle action: {action!r}")
    if subject_type not in VALID_SUBJECT_TYPES:
        raise ValueError(f"Invalid subject_type: {subject_type!r}")

    event = models.DataLifecycleEvent(
        org_id=persisted_org_id(org_id),
        action=action,
        subject_type=subject_type,
        subject_ref=str(subject_ref),
        requested_by=requested_by,
        status="started",
        scope_json=json.dumps(scope or {}, ensure_ascii=False, default=str),
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def complete_event(
    db: Session,
    event: models.DataLifecycleEvent,
    *,
    status: str = "completed",
    evidence: dict[str, Any] | None = None,
) -> models.DataLifecycleEvent:
    """Mark a lifecycle event finished and attach per-store evidence."""
    if status not in {"completed", "failed"}:
        raise ValueError(f"Invalid completion status: {status!r}")
    event.status = status
    event.evidence_json = json.dumps(evidence or {}, ensure_ascii=False, default=str)
    event.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return event
