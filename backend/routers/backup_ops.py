"""Admin-only backup assurance metadata endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend import models
from backend.auth import require_role
from backend.backup_assurance import (
    evaluate_backup_freshness,
    failure_reason_from_event,
    latest_completed_backup,
    latest_failed_backup,
    parse_event_evidence,
    record_event,
)
from backend.database import get_db
from backend.schemas_backup import (
    BackupEventCreate,
    BackupEventResponse,
    BackupStatusResponse,
)


router = APIRouter(
    prefix="/ops/backups",
    tags=["operations", "backups"],
    dependencies=[Depends(require_role("super_admin", "admin"))],
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def backup_event_ordering():
    return (
        models.BackupAssuranceEvent.completed_at.desc().nullslast(),
        models.BackupAssuranceEvent.created_at.desc(),
        models.BackupAssuranceEvent.id.desc(),
    )


def _event_response(event: models.BackupAssuranceEvent) -> BackupEventResponse:
    return BackupEventResponse(
        id=event.id,
        event_type=event.event_type,
        status=event.status,
        environment=event.environment,
        provider=event.provider,
        backup_id=event.backup_id,
        started_at=event.started_at,
        completed_at=event.completed_at,
        release=event.release,
        alembic_revision=event.alembic_revision,
        size_bytes=event.size_bytes,
        integrity_ref=event.integrity_ref,
        encrypted=event.encrypted,
        storage_region=event.storage_region,
        retention_class=event.retention_class,
        operator=event.operator,
        expected_rpo_hours=event.expected_rpo_hours,
        expected_rto_hours=event.expected_rto_hours,
        achieved_rpo_hours=event.achieved_rpo_hours,
        achieved_rto_hours=event.achieved_rto_hours,
        evidence=parse_event_evidence(event),
        created_at=event.created_at,
    )


@router.post(
    "/events",
    response_model=BackupEventResponse,
    status_code=201,
)
def create_backup_event(
    payload: BackupEventCreate,
    db: Session = Depends(get_db),
):
    event = record_event(db, **payload.model_dump())
    db.commit()
    db.refresh(event)
    return _event_response(event)


@router.get("", response_model=list[BackupEventResponse])
def list_backup_events(
    environment: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(models.BackupAssuranceEvent)
    if environment is not None:
        query = query.filter(models.BackupAssuranceEvent.environment == environment)
    events = query.order_by(*backup_event_ordering()).limit(limit).all()
    return [_event_response(event) for event in events]


@router.get("/status", response_model=BackupStatusResponse)
def backup_status(
    environment: str = Query(
        default_factory=lambda: os.environ.get(
            "UKIP_BACKUP_ENVIRONMENT",
            "production",
        ),
        min_length=1,
    ),
    db: Session = Depends(get_db),
):
    evaluated_at = utc_now()
    latest = latest_completed_backup(db, environment)
    latest_failure = latest_failed_backup(db, environment)
    result = evaluate_backup_freshness(
        latest_completed_at=latest.completed_at if latest else None,
        now=evaluated_at,
        size_bytes=latest.size_bytes if latest else None,
        integrity_ref=latest.integrity_ref if latest else None,
        provider_reachable=os.environ.get(
            "UKIP_BACKUP_PROVIDER_REACHABLE",
            "1",
        ) == "1",
    )
    return {
        "environment": environment,
        **result,
        "evidence_collected_at": evaluated_at,
        "last_failure_at": (
            latest_failure.completed_at or latest_failure.created_at
            if latest_failure
            else None
        ),
        "last_failure_reason": failure_reason_from_event(latest_failure),
        "latest_backup": _event_response(latest) if latest else None,
    }
