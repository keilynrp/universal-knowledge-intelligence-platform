from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.backup_status_response_status import BackupStatusResponseStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.backup_event_response import BackupEventResponse


T = TypeVar("T", bound="BackupStatusResponse")


@_attrs_define
class BackupStatusResponse:
    """
    Attributes:
        age_hours (float | None):
        critical_after_hours (int):
        environment (str):
        evidence_collected_at (None | str):
        last_failure_at (None | str):
        last_failure_reason (None | str):
        latest_backup (BackupEventResponse | None):
        provider_reachability_source (str):
        provider_reachable (bool):
        reason_codes (list[str]):
        rpo_hours (int):
        status (BackupStatusResponseStatus):
        latest_volume_backup (BackupEventResponse | None | Unset):
    """

    age_hours: float | None
    critical_after_hours: int
    environment: str
    evidence_collected_at: None | str
    last_failure_at: None | str
    last_failure_reason: None | str
    latest_backup: BackupEventResponse | None
    provider_reachability_source: str
    provider_reachable: bool
    reason_codes: list[str]
    rpo_hours: int
    status: BackupStatusResponseStatus
    latest_volume_backup: BackupEventResponse | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.backup_event_response import BackupEventResponse

        age_hours: float | None
        age_hours = self.age_hours

        critical_after_hours = self.critical_after_hours

        environment = self.environment

        evidence_collected_at: None | str
        evidence_collected_at = self.evidence_collected_at

        last_failure_at: None | str
        last_failure_at = self.last_failure_at

        last_failure_reason: None | str
        last_failure_reason = self.last_failure_reason

        latest_backup: dict[str, Any] | None
        if isinstance(self.latest_backup, BackupEventResponse):
            latest_backup = self.latest_backup.to_dict()
        else:
            latest_backup = self.latest_backup

        provider_reachability_source = self.provider_reachability_source

        provider_reachable = self.provider_reachable

        reason_codes = self.reason_codes

        rpo_hours = self.rpo_hours

        status = self.status.value

        latest_volume_backup: dict[str, Any] | None | Unset
        if isinstance(self.latest_volume_backup, Unset):
            latest_volume_backup = UNSET
        elif isinstance(self.latest_volume_backup, BackupEventResponse):
            latest_volume_backup = self.latest_volume_backup.to_dict()
        else:
            latest_volume_backup = self.latest_volume_backup

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "age_hours": age_hours,
                "critical_after_hours": critical_after_hours,
                "environment": environment,
                "evidence_collected_at": evidence_collected_at,
                "last_failure_at": last_failure_at,
                "last_failure_reason": last_failure_reason,
                "latest_backup": latest_backup,
                "provider_reachability_source": provider_reachability_source,
                "provider_reachable": provider_reachable,
                "reason_codes": reason_codes,
                "rpo_hours": rpo_hours,
                "status": status,
            }
        )
        if latest_volume_backup is not UNSET:
            field_dict["latest_volume_backup"] = latest_volume_backup

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.backup_event_response import BackupEventResponse

        d = dict(src_dict)

        def _parse_age_hours(data: object) -> float | None:
            if data is None:
                return data
            return cast(float | None, data)

        age_hours = _parse_age_hours(d.pop("age_hours"))

        critical_after_hours = d.pop("critical_after_hours")

        environment = d.pop("environment")

        def _parse_evidence_collected_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        evidence_collected_at = _parse_evidence_collected_at(d.pop("evidence_collected_at"))

        def _parse_last_failure_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        last_failure_at = _parse_last_failure_at(d.pop("last_failure_at"))

        def _parse_last_failure_reason(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        last_failure_reason = _parse_last_failure_reason(d.pop("last_failure_reason"))

        def _parse_latest_backup(data: object) -> BackupEventResponse | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                latest_backup_type_0 = BackupEventResponse.from_dict(data)

                return latest_backup_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(BackupEventResponse | None, data)

        latest_backup = _parse_latest_backup(d.pop("latest_backup"))

        provider_reachability_source = d.pop("provider_reachability_source")

        provider_reachable = d.pop("provider_reachable")

        reason_codes = cast(list[str], d.pop("reason_codes"))

        rpo_hours = d.pop("rpo_hours")

        status = BackupStatusResponseStatus(d.pop("status"))

        def _parse_latest_volume_backup(data: object) -> BackupEventResponse | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                latest_volume_backup_type_0 = BackupEventResponse.from_dict(data)

                return latest_volume_backup_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(BackupEventResponse | None | Unset, data)

        latest_volume_backup = _parse_latest_volume_backup(d.pop("latest_volume_backup", UNSET))

        backup_status_response = cls(
            age_hours=age_hours,
            critical_after_hours=critical_after_hours,
            environment=environment,
            evidence_collected_at=evidence_collected_at,
            last_failure_at=last_failure_at,
            last_failure_reason=last_failure_reason,
            latest_backup=latest_backup,
            provider_reachability_source=provider_reachability_source,
            provider_reachable=provider_reachable,
            reason_codes=reason_codes,
            rpo_hours=rpo_hours,
            status=status,
            latest_volume_backup=latest_volume_backup,
        )

        backup_status_response.additional_properties = d
        return backup_status_response

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
