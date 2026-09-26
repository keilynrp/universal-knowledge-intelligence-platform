from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AlertChannelCreate")


@_attrs_define
class AlertChannelCreate:
    """
    Attributes:
        name (str):
        events (list[str] | Unset):
        pushover_token (None | str | Unset):
        pushover_user (None | str | Unset):
        type_ (str | Unset):  Default: 'slack'.
        webhook_url (None | str | Unset):
    """

    name: str
    events: list[str] | Unset = UNSET
    pushover_token: None | str | Unset = UNSET
    pushover_user: None | str | Unset = UNSET
    type_: str | Unset = "slack"
    webhook_url: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        events: list[str] | Unset = UNSET
        if not isinstance(self.events, Unset):
            events = self.events

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

        type_ = self.type_

        webhook_url: None | str | Unset
        if isinstance(self.webhook_url, Unset):
            webhook_url = UNSET
        else:
            webhook_url = self.webhook_url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
            }
        )
        if events is not UNSET:
            field_dict["events"] = events
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
        name = d.pop("name")

        events = cast(list[str], d.pop("events", UNSET))

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

        type_ = d.pop("type", UNSET)

        def _parse_webhook_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        webhook_url = _parse_webhook_url(d.pop("webhook_url", UNSET))

        alert_channel_create = cls(
            name=name,
            events=events,
            pushover_token=pushover_token,
            pushover_user=pushover_user,
            type_=type_,
            webhook_url=webhook_url,
        )

        alert_channel_create.additional_properties = d
        return alert_channel_create

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
