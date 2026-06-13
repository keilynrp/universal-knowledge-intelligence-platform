"""Provider-neutral persistence and health evaluation for backup assurance."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models import BackupAssuranceEvent


BACKUP_RPO_HOURS = 24
BACKUP_CRITICAL_AFTER_HOURS = 26

_VALID_EVENT_STATUSES = {
    "backup": {"completed", "failed"},
    "restore_drill": {"passed", "passed_with_risk", "failed"},
}
_SECRET_KEY_MARKERS = {
    "secret",
    "password",
    "token",
    "credential",
    "database_url",
    "connection_string",
}


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = str(key).casefold()
            if any(marker in normalized_key for marker in _SECRET_KEY_MARKERS):
                return True
            if _contains_secret_key(nested_value):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_secret_key(item) for item in value)
    return False


def record_event(
    db: Session,
    *,
    event_type: str,
    status: str,
    environment: str,
    provider: str,
    started_at: datetime,
    operator: str,
    backup_id: str | None = None,
    completed_at: datetime | None = None,
    release: str | None = None,
    alembic_revision: str | None = None,
    size_bytes: int | None = None,
    integrity_ref: str | None = None,
    encrypted: bool | None = None,
    storage_region: str | None = None,
    retention_class: str | None = None,
    expected_rpo_hours: float | None = None,
    expected_rto_hours: float | None = None,
    achieved_rpo_hours: float | None = None,
    achieved_rto_hours: float | None = None,
    evidence: dict[str, Any] | None = None,
) -> BackupAssuranceEvent:
    if event_type not in _VALID_EVENT_STATUSES:
        raise ValueError(f"Unsupported event_type: {event_type!r}")
    if status not in _VALID_EVENT_STATUSES[event_type]:
        raise ValueError(
            f"Unsupported status {status!r} for event_type {event_type!r}"
        )
    if evidence is not None and _contains_secret_key(evidence):
        raise ValueError("Evidence contains a secret-like key")

    event = BackupAssuranceEvent(
        event_type=event_type,
        status=status,
        environment=environment,
        provider=provider,
        backup_id=backup_id,
        started_at=_utc_naive(started_at),
        completed_at=_utc_naive(completed_at),
        release=release,
        alembic_revision=alembic_revision,
        size_bytes=size_bytes,
        integrity_ref=integrity_ref,
        encrypted=encrypted,
        storage_region=storage_region,
        retention_class=retention_class,
        operator=operator,
        expected_rpo_hours=expected_rpo_hours,
        expected_rto_hours=expected_rto_hours,
        achieved_rpo_hours=achieved_rpo_hours,
        achieved_rto_hours=achieved_rto_hours,
        evidence_json=json.dumps(evidence, sort_keys=True) if evidence is not None else None,
    )
    db.add(event)
    db.flush()
    db.refresh(event)
    return event


def evaluate_backup_freshness(
    *,
    latest_completed_at: datetime | None,
    now: datetime,
    size_bytes: int | None,
    integrity_ref: str | None,
    provider_reachable: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    age_hours: float | None = None

    if latest_completed_at is None:
        reasons.append("backup_missing")
    else:
        completed_utc = _utc_naive(latest_completed_at)
        now_utc = _utc_naive(now)
        age_hours = (now_utc - completed_utc).total_seconds() / 3600
        if age_hours < 0:
            reasons.append("backup_from_future")
        if age_hours > BACKUP_CRITICAL_AFTER_HOURS:
            reasons.append("backup_stale")

    if size_bytes is None or size_bytes <= 0:
        reasons.append("backup_empty")
    if not integrity_ref:
        reasons.append("integrity_missing")
    if not provider_reachable:
        reasons.append("provider_unreachable")

    if reasons:
        status = "critical"
    elif age_hours is not None and age_hours > BACKUP_RPO_HOURS:
        status = "warning"
        reasons.append("backup_approaching_critical_threshold")
    else:
        status = "ok"

    return {
        "status": status,
        "age_hours": age_hours,
        "rpo_hours": BACKUP_RPO_HOURS,
        "critical_after_hours": BACKUP_CRITICAL_AFTER_HOURS,
        "reason_codes": reasons,
    }


def latest_completed_backup(
    db: Session,
    environment: str,
) -> BackupAssuranceEvent | None:
    return (
        db.query(BackupAssuranceEvent)
        .filter(
            BackupAssuranceEvent.event_type == "backup",
            BackupAssuranceEvent.status == "completed",
            BackupAssuranceEvent.environment == environment,
            BackupAssuranceEvent.completed_at.is_not(None),
        )
        .order_by(
            BackupAssuranceEvent.completed_at.desc(),
            BackupAssuranceEvent.id.desc(),
        )
        .first()
    )


def latest_failed_backup(
    db: Session,
    environment: str,
) -> BackupAssuranceEvent | None:
    return (
        db.query(BackupAssuranceEvent)
        .filter(
            BackupAssuranceEvent.event_type == "backup",
            BackupAssuranceEvent.status == "failed",
            BackupAssuranceEvent.environment == environment,
        )
        .order_by(*failed_backup_ordering())
        .first()
    )


def failed_backup_ordering():
    return (
        BackupAssuranceEvent.completed_at.desc().nullslast(),
        BackupAssuranceEvent.created_at.desc(),
        BackupAssuranceEvent.id.desc(),
    )


def parse_event_evidence(
    event: BackupAssuranceEvent | None,
) -> dict[str, Any] | None:
    if event is None or not event.evidence_json:
        return None
    try:
        evidence = json.loads(event.evidence_json)
    except (TypeError, ValueError):
        return None
    return evidence if isinstance(evidence, dict) else None


def failure_reason_from_event(
    event: BackupAssuranceEvent | None,
) -> str | None:
    evidence = parse_event_evidence(event)
    if evidence is None:
        return None
    reason = evidence.get("failure_reason")
    return reason if isinstance(reason, str) and reason.strip() else None
