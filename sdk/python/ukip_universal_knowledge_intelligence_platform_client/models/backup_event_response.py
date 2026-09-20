from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.backup_event_response_evidence_type_0 import BackupEventResponseEvidenceType0


T = TypeVar("T", bound="BackupEventResponse")


@_attrs_define
class BackupEventResponse:
    """
    Attributes:
        achieved_rpo_hours (float | None):
        achieved_rto_hours (float | None):
        alembic_revision (None | str):
        backup_id (None | str):
        completed_at (None | str):
        created_at (None | str):
        encrypted (bool | None):
        environment (str):
        event_type (str):
        evidence (BackupEventResponseEvidenceType0 | None):
        expected_rpo_hours (float | None):
        expected_rto_hours (float | None):
        id (int):
        integrity_ref (None | str):
        operator (str):
        provider (str):
        release (None | str):
        retention_class (None | str):
        scope (str):
        size_bytes (int | None):
        started_at (None | str):
        status (str):
        storage_region (None | str):
    """

    achieved_rpo_hours: float | None
    achieved_rto_hours: float | None
    alembic_revision: None | str
    backup_id: None | str
    completed_at: None | str
    created_at: None | str
    encrypted: bool | None
    environment: str
    event_type: str
    evidence: BackupEventResponseEvidenceType0 | None
    expected_rpo_hours: float | None
    expected_rto_hours: float | None
    id: int
    integrity_ref: None | str
    operator: str
    provider: str
    release: None | str
    retention_class: None | str
    scope: str
    size_bytes: int | None
    started_at: None | str
    status: str
    storage_region: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.backup_event_response_evidence_type_0 import BackupEventResponseEvidenceType0

        achieved_rpo_hours: float | None
        achieved_rpo_hours = self.achieved_rpo_hours

        achieved_rto_hours: float | None
        achieved_rto_hours = self.achieved_rto_hours

        alembic_revision: None | str
        alembic_revision = self.alembic_revision

        backup_id: None | str
        backup_id = self.backup_id

        completed_at: None | str
        completed_at = self.completed_at

        created_at: None | str
        created_at = self.created_at

        encrypted: bool | None
        encrypted = self.encrypted

        environment = self.environment

        event_type = self.event_type

        evidence: dict[str, Any] | None
        if isinstance(self.evidence, BackupEventResponseEvidenceType0):
            evidence = self.evidence.to_dict()
        else:
            evidence = self.evidence

        expected_rpo_hours: float | None
        expected_rpo_hours = self.expected_rpo_hours

        expected_rto_hours: float | None
        expected_rto_hours = self.expected_rto_hours

        id = self.id

        integrity_ref: None | str
        integrity_ref = self.integrity_ref

        operator = self.operator

        provider = self.provider

        release: None | str
        release = self.release

        retention_class: None | str
        retention_class = self.retention_class

        scope = self.scope

        size_bytes: int | None
        size_bytes = self.size_bytes

        started_at: None | str
        started_at = self.started_at

        status = self.status

        storage_region: None | str
        storage_region = self.storage_region

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "achieved_rpo_hours": achieved_rpo_hours,
                "achieved_rto_hours": achieved_rto_hours,
                "alembic_revision": alembic_revision,
                "backup_id": backup_id,
                "completed_at": completed_at,
                "created_at": created_at,
                "encrypted": encrypted,
                "environment": environment,
                "event_type": event_type,
                "evidence": evidence,
                "expected_rpo_hours": expected_rpo_hours,
                "expected_rto_hours": expected_rto_hours,
                "id": id,
                "integrity_ref": integrity_ref,
                "operator": operator,
                "provider": provider,
                "release": release,
                "retention_class": retention_class,
                "scope": scope,
                "size_bytes": size_bytes,
                "started_at": started_at,
                "status": status,
                "storage_region": storage_region,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.backup_event_response_evidence_type_0 import BackupEventResponseEvidenceType0

        d = dict(src_dict)

        def _parse_achieved_rpo_hours(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        achieved_rpo_hours = _parse_achieved_rpo_hours(d.pop("achieved_rpo_hours"))

        def _parse_achieved_rto_hours(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        achieved_rto_hours = _parse_achieved_rto_hours(d.pop("achieved_rto_hours"))

        def _parse_alembic_revision(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        alembic_revision = _parse_alembic_revision(d.pop("alembic_revision"))

        def _parse_backup_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        backup_id = _parse_backup_id(d.pop("backup_id"))

        def _parse_completed_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        completed_at = _parse_completed_at(d.pop("completed_at"))

        def _parse_created_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        created_at = _parse_created_at(d.pop("created_at"))

        def _parse_encrypted(data: object) -> bool | None:
            if data is None:
                return data
            return cast(bool | None, data)

        encrypted = _parse_encrypted(d.pop("encrypted"))

        environment = d.pop("environment")

        event_type = d.pop("event_type")

        def _parse_evidence(data: object) -> BackupEventResponseEvidenceType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                evidence_type_0 = BackupEventResponseEvidenceType0.from_dict(data)

                return evidence_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(BackupEventResponseEvidenceType0 | None, data)

        evidence = _parse_evidence(d.pop("evidence"))

        def _parse_expected_rpo_hours(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        expected_rpo_hours = _parse_expected_rpo_hours(d.pop("expected_rpo_hours"))

        def _parse_expected_rto_hours(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        expected_rto_hours = _parse_expected_rto_hours(d.pop("expected_rto_hours"))

        id = d.pop("id")

        def _parse_integrity_ref(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        integrity_ref = _parse_integrity_ref(d.pop("integrity_ref"))

        operator = d.pop("operator")

        provider = d.pop("provider")

        def _parse_release(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        release = _parse_release(d.pop("release"))

        def _parse_retention_class(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        retention_class = _parse_retention_class(d.pop("retention_class"))

        scope = d.pop("scope")

        def _parse_size_bytes(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        size_bytes = _parse_size_bytes(d.pop("size_bytes"))

        def _parse_started_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        started_at = _parse_started_at(d.pop("started_at"))

        status = d.pop("status")

        def _parse_storage_region(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        storage_region = _parse_storage_region(d.pop("storage_region"))

        backup_event_response = cls(
            achieved_rpo_hours=achieved_rpo_hours,
            achieved_rto_hours=achieved_rto_hours,
            alembic_revision=alembic_revision,
            backup_id=backup_id,
            completed_at=completed_at,
            created_at=created_at,
            encrypted=encrypted,
            environment=environment,
            event_type=event_type,
            evidence=evidence,
            expected_rpo_hours=expected_rpo_hours,
            expected_rto_hours=expected_rto_hours,
            id=id,
            integrity_ref=integrity_ref,
            operator=operator,
            provider=provider,
            release=release,
            retention_class=retention_class,
            scope=scope,
            size_bytes=size_bytes,
            started_at=started_at,
            status=status,
            storage_region=storage_region,
        )

        backup_event_response.additional_properties = d
        return backup_event_response

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
