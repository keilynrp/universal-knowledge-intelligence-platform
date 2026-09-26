from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AlertChannelUpdate")


@_attrs_define
class AlertChannelUpdate:
    """
    Attributes:
        events (list[str] | None | Unset):
        is_active (bool | None | Unset):
        name (None | str | Unset):
        pushover_token (None | str | Unset):
        pushover_user (None | str | Unset):
        type_ (None | str | Unset):
        webhook_url (None | str | Unset):
    """

    events: list[str] | None | Unset = UNSET
    is_active: bool | None | Unset = UNSET
    name: None | str | Unset = UNSET
    pushover_token: None | str | Unset = UNSET
    pushover_user: None | str | Unset = UNSET
    type_: None | str | Unset = UNSET
    webhook_url: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        events: list[str] | None | Unset
        if isinstance(self.events, Unset):
            events = UNSET
        elif isinstance(self.events, list):
            events = self.events

        else:
            events = self.events

        is_active: bool | None | Unset
        if isinstance(self.is_active, Unset):
            is_active = UNSET
        else:
            is_active = self.is_active

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        pushover_token: None | str | Unset
        if isinstance(self.pushover_token, Unset):
            pushover_token = UNSET
        else:
            pushover_token = self.pushover_token

        pushover_user: None | str | Unset
        if isinstance(self.pushover_user, Unset):
            pushover_user = UNSET
        else:
            pushover_user = self.pushover_user

        type_: None | str | Unset
        if isinstance(self.type_, Unset):
            type_ = UNSET
        else:
            type_ = self.type_

        webhook_url: None | str | Unset
        if isinstance(self.webhook_url, Unset):
            webhook_url = UNSET
        else:
            webhook_url = self.webhook_url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if events is not UNSET:
            field_dict["events"] = events
        if is_active is not UNSET:
            field_dict["is_active"] = is_active
        if name is not UNSET:
            field_dict["name"] = name
        if pushover_token is not UNSET:
            field_dict["pushover_token"] = pushover_token
        if pushover_user is not UNSET:
            field_dict["pushover_user"] = pushover_user
        if type_ is not UNSET:
            field_dict["type"] = type_
        if webhook_url is not UNSET:
            field_dict["webhook_url"] = webhook_url

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_events(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                events_type_0 = cast(list[str], data)

                return events_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        events = _parse_events(d.pop("events", UNSET))

        def _parse_is_active(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        is_active = _parse_is_active(d.pop("is_active", UNSET))

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_pushover_token(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        pushover_token = _parse_pushover_token(d.pop("pushover_token", UNSET))

        def _parse_pushover_user(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        pushover_user = _parse_pushover_user(d.pop("pushover_user", UNSET))

        def _parse_type_(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        type_ = _parse_type_(d.pop("type", UNSET))

        def _parse_webhook_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        webhook_url = _parse_webhook_url(d.pop("webhook_url", UNSET))

        alert_channel_update = cls(
            events=events,
            is_active=is_active,
            name=name,
            pushover_token=pushover_token,
            pushover_user=pushover_user,
            type_=type_,
            webhook_url=webhook_url,
        )

        alert_channel_update.additional_properties = d
        return alert_channel_update

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
