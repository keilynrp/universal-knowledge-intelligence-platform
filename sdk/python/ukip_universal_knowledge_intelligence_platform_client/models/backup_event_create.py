from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.backup_event_create_event_type import BackupEventCreateEventType
from ..models.backup_event_create_scope import BackupEventCreateScope
from ..models.backup_event_create_status import BackupEventCreateStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.backup_event_create_evidence_type_0 import BackupEventCreateEvidenceType0


T = TypeVar("T", bound="BackupEventCreate")


@_attrs_define
class BackupEventCreate:
    """
    Attributes:
        environment (str):
        event_type (BackupEventCreateEventType):
        provider (str):
        started_at (datetime.datetime):
        status (BackupEventCreateStatus):
        achieved_rpo_hours (float | None | Unset):
        achieved_rto_hours (float | None | Unset):
        alembic_revision (None | str | Unset):
        backup_id (None | str | Unset):
        completed_at (datetime.datetime | None | Unset):
        encrypted (bool | None | Unset):
        evidence (BackupEventCreateEvidenceType0 | None | Unset):
        expected_rpo_hours (float | None | Unset):
        expected_rto_hours (float | None | Unset):
        integrity_ref (None | str | Unset):
        release (None | str | Unset):
        retention_class (None | str | Unset):
        scope (BackupEventCreateScope | Unset):  Default: BackupEventCreateScope.DATABASE.
        size_bytes (int | None | Unset):
        storage_region (None | str | Unset):
    """

    environment: str
    event_type: BackupEventCreateEventType
    provider: str
    started_at: datetime.datetime
    status: BackupEventCreateStatus
    achieved_rpo_hours: float | None | Unset = UNSET
    achieved_rto_hours: float | None | Unset = UNSET
    alembic_revision: None | str | Unset = UNSET
    backup_id: None | str | Unset = UNSET
    completed_at: datetime.datetime | None | Unset = UNSET
    encrypted: bool | None | Unset = UNSET
    evidence: BackupEventCreateEvidenceType0 | None | Unset = UNSET
    expected_rpo_hours: float | None | Unset = UNSET
    expected_rto_hours: float | None | Unset = UNSET
    integrity_ref: None | str | Unset = UNSET
    release: None | str | Unset = UNSET
    retention_class: None | str | Unset = UNSET
    scope: BackupEventCreateScope | Unset = BackupEventCreateScope.DATABASE
    size_bytes: int | None | Unset = UNSET
    storage_region: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.backup_event_create_evidence_type_0 import BackupEventCreateEvidenceType0

        environment = self.environment

        event_type = self.event_type.value

        provider = self.provider

        started_at = self.started_at.isoformat()

        status = self.status.value

        achieved_rpo_hours: float | None | Unset
        if isinstance(self.achieved_rpo_hours, Unset):
            achieved_rpo_hours = UNSET
        else:
            achieved_rpo_hours = self.achieved_rpo_hours

        achieved_rto_hours: float | None | Unset
        if isinstance(self.achieved_rto_hours, Unset):
            achieved_rto_hours = UNSET
        else:
            achieved_rto_hours = self.achieved_rto_hours

        alembic_revision: None | str | Unset
        if isinstance(self.alembic_revision, Unset):
            alembic_revision = UNSET
        else:
            alembic_revision = self.alembic_revision

        backup_id: None | str | Unset
        if isinstance(self.backup_id, Unset):
            backup_id = UNSET
        else:
            backup_id = self.backup_id

        completed_at: None | str | Unset
        if isinstance(self.completed_at, Unset):
            completed_at = UNSET
        elif isinstance(self.completed_at, datetime.datetime):
            completed_at = self.completed_at.isoformat()
        else:
            completed_at = self.completed_at

        encrypted: bool | None | Unset
        if isinstance(self.encrypted, Unset):
            encrypted = UNSET
        else:
            encrypted = self.encrypted

        evidence: dict[str, Any] | None | Unset
        if isinstance(self.evidence, Unset):
            evidence = UNSET
        elif isinstance(self.evidence, BackupEventCreateEvidenceType0):
            evidence = self.evidence.to_dict()
        else:
            evidence = self.evidence

        expected_rpo_hours: float | None | Unset
        if isinstance(self.expected_rpo_hours, Unset):
            expected_rpo_hours = UNSET
        else:
            expected_rpo_hours = self.expected_rpo_hours

        expected_rto_hours: float | None | Unset
        if isinstance(self.expected_rto_hours, Unset):
            expected_rto_hours = UNSET
        else:
            expected_rto_hours = self.expected_rto_hours

        integrity_ref: None | str | Unset
        if isinstance(self.integrity_ref, Unset):
            integrity_ref = UNSET
        else:
            integrity_ref = self.integrity_ref

        release: None | str | Unset
        if isinstance(self.release, Unset):
            release = UNSET
        else:
            release = self.release

        retention_class: None | str | Unset
        if isinstance(self.retention_class, Unset):
            retention_class = UNSET
        else:
            retention_class = self.retention_class

        scope: str | Unset = UNSET
        if not isinstance(self.scope, Unset):
            scope = self.scope.value

        size_bytes: int | None | Unset
        if isinstance(self.size_bytes, Unset):
            size_bytes = UNSET
        else:
            size_bytes = self.size_bytes

        storage_region: None | str | Unset
        if isinstance(self.storage_region, Unset):
            storage_region = UNSET
        else:
            storage_region = self.storage_region

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "environment": environment,
                "event_type": event_type,
                "provider": provider,
                "started_at": started_at,
                "status": status,
            }
        )
        if achieved_rpo_hours is not UNSET:
            field_dict["achieved_rpo_hours"] = achieved_rpo_hours
        if achieved_rto_hours is not UNSET:
            field_dict["achieved_rto_hours"] = achieved_rto_hours
        if alembic_revision is not UNSET:
            field_dict["alembic_revision"] = alembic_revision
        if backup_id is not UNSET:
            field_dict["backup_id"] = backup_id
        if completed_at is not UNSET:
            field_dict["completed_at"] = completed_at
        if encrypted is not UNSET:
            field_dict["encrypted"] = encrypted
        if evidence is not UNSET:
            field_dict["evidence"] = evidence
        if expected_rpo_hours is not UNSET:
            field_dict["expected_rpo_hours"] = expected_rpo_hours
        if expected_rto_hours is not UNSET:
            field_dict["expected_rto_hours"] = expected_rto_hours
        if integrity_ref is not UNSET:
            field_dict["integrity_ref"] = integrity_ref
        if release is not UNSET:
            field_dict["release"] = release
        if retention_class is not UNSET:
            field_dict["retention_class"] = retention_class
        if scope is not UNSET:
            field_dict["scope"] = scope
        if size_bytes is not UNSET:
            field_dict["size_bytes"] = size_bytes
        if storage_region is not UNSET:
            field_dict["storage_region"] = storage_region

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.backup_event_create_evidence_type_0 import BackupEventCreateEvidenceType0

        d = dict(src_dict)
        environment = d.pop("environment")

        event_type = BackupEventCreateEventType(d.pop("event_type"))

        provider = d.pop("provider")

        started_at = datetime.datetime.fromisoformat(d.pop("started_at"))

        status = BackupEventCreateStatus(d.pop("status"))

        def _parse_achieved_rpo_hours(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        achieved_rpo_hours = _parse_achieved_rpo_hours(d.pop("achieved_rpo_hours", UNSET))

        def _parse_achieved_rto_hours(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        achieved_rto_hours = _parse_achieved_rto_hours(d.pop("achieved_rto_hours", UNSET))

        def _parse_alembic_revision(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        alembic_revision = _parse_alembic_revision(d.pop("alembic_revision", UNSET))

        def _parse_backup_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        backup_id = _parse_backup_id(d.pop("backup_id", UNSET))

        def _parse_completed_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                completed_at_type_0 = datetime.datetime.fromisoformat(data)

                return completed_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        completed_at = _parse_completed_at(d.pop("completed_at", UNSET))

        def _parse_encrypted(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        encrypted = _parse_encrypted(d.pop("encrypted", UNSET))

        def _parse_evidence(data: object) -> BackupEventCreateEvidenceType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                evidence_type_0 = BackupEventCreateEvidenceType0.from_dict(data)

                return evidence_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(BackupEventCreateEvidenceType0 | None | Unset, data)

        evidence = _parse_evidence(d.pop("evidence", UNSET))

        def _parse_expected_rpo_hours(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        expected_rpo_hours = _parse_expected_rpo_hours(d.pop("expected_rpo_hours", UNSET))

        def _parse_expected_rto_hours(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        expected_rto_hours = _parse_expected_rto_hours(d.pop("expected_rto_hours", UNSET))

        def _parse_integrity_ref(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        integrity_ref = _parse_integrity_ref(d.pop("integrity_ref", UNSET))

        def _parse_release(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        release = _parse_release(d.pop("release", UNSET))

        def _parse_retention_class(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        retention_class = _parse_retention_class(d.pop("retention_class", UNSET))

        _scope = d.pop("scope", UNSET)
        scope: BackupEventCreateScope | Unset
        if isinstance(_scope, Unset):
            scope = UNSET
        else:
            scope = BackupEventCreateScope(_scope)

        def _parse_size_bytes(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        size_bytes = _parse_size_bytes(d.pop("size_bytes", UNSET))

        def _parse_storage_region(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        storage_region = _parse_storage_region(d.pop("storage_region", UNSET))

        backup_event_create = cls(
            environment=environment,
            event_type=event_type,
            provider=provider,
            started_at=started_at,
            status=status,
            achieved_rpo_hours=achieved_rpo_hours,
            achieved_rto_hours=achieved_rto_hours,
            alembic_revision=alembic_revision,
            backup_id=backup_id,
            completed_at=completed_at,
            encrypted=encrypted,
            evidence=evidence,
            expected_rpo_hours=expected_rpo_hours,
            expected_rto_hours=expected_rto_hours,
            integrity_ref=integrity_ref,
            release=release,
            retention_class=retention_class,
            scope=scope,
            size_bytes=size_bytes,
            storage_region=storage_region,
        )

        return backup_event_create
