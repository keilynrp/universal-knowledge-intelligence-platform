"""Pydantic contracts for backup assurance operations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


EventType = Literal["backup", "restore_drill"]
EventStatus = Literal["completed", "failed", "passed", "passed_with_risk"]

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


def _serialize_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = str(key).casefold()
            if any(marker in normalized_key for marker in _SECRET_KEY_MARKERS):
                return True
            if _contains_secret_key(nested_value):
                return True
    elif isinstance(value, list):
        return any(_contains_secret_key(item) for item in value)
    return False


class BackupEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    status: EventStatus
    environment: str = Field(min_length=1, max_length=50)
    provider: str = Field(min_length=1, max_length=80)
    backup_id: str | None = Field(default=None, max_length=200)
    started_at: datetime
    completed_at: datetime | None = None
    release: str | None = Field(default=None, max_length=120)
    alembic_revision: str | None = Field(default=None, max_length=120)
    size_bytes: int | None = Field(default=None, ge=0)
    integrity_ref: str | None = Field(default=None, max_length=200)
    encrypted: bool | None = None
    storage_region: str | None = Field(default=None, max_length=120)
    retention_class: str | None = Field(default=None, max_length=30)
    operator: str = Field(min_length=1, max_length=120)
    expected_rpo_hours: float | None = Field(default=None, ge=0)
    expected_rto_hours: float | None = Field(default=None, ge=0)
    achieved_rpo_hours: float | None = Field(default=None, ge=0)
    achieved_rto_hours: float | None = Field(default=None, ge=0)
    evidence: dict[str, Any] | None = None

    @field_validator("environment", "provider", "operator")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_utc_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must include a UTC offset")
        return value.astimezone(timezone.utc)

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        if len(value) > 50:
            raise ValueError("evidence must contain at most 50 top-level keys")
        if _contains_secret_key(value):
            raise ValueError("evidence contains a secret-like key")
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("evidence must be JSON-compatible") from exc
        return value

    @model_validator(mode="after")
    def validate_event_status(self):
        if self.status not in _VALID_EVENT_STATUSES[self.event_type]:
            raise ValueError(
                f"status {self.status!r} is invalid for event_type {self.event_type!r}"
            )
        if self.completed_at is None:
            raise ValueError("terminal events require completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must be greater than or equal to started_at")
        if self.completed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("completed_at cannot be more than five minutes in the future")
        return self


class BackupEventResponse(BaseModel):
    id: int
    event_type: str
    status: str
    environment: str
    provider: str
    backup_id: str | None
    started_at: datetime
    completed_at: datetime | None
    release: str | None
    alembic_revision: str | None
    size_bytes: int | None
    integrity_ref: str | None
    encrypted: bool | None
    storage_region: str | None
    retention_class: str | None
    operator: str
    expected_rpo_hours: float | None
    expected_rto_hours: float | None
    achieved_rpo_hours: float | None
    achieved_rto_hours: float | None
    evidence: dict[str, Any] | None
    created_at: datetime

    @field_serializer("started_at", "completed_at", "created_at")
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        return _serialize_utc(value)


class BackupStatusResponse(BaseModel):
    environment: str
    status: Literal["ok", "warning", "critical"]
    age_hours: float | None
    rpo_hours: int
    critical_after_hours: int
    reason_codes: list[str]
    provider_reachable: bool
    provider_reachability_source: str
    evidence_collected_at: datetime | None
    last_failure_at: datetime | None
    last_failure_reason: str | None
    latest_backup: BackupEventResponse | None

    @field_serializer("evidence_collected_at", "last_failure_at")
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        return _serialize_utc(value)
