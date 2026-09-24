import datetime
from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    action: None | str | Unset = UNSET,
    resource_type: None | str | Unset = UNSET,
    username: None | str | Unset = UNSET,
    from_date: datetime.datetime | None | Unset = UNSET,
    to_date: datetime.datetime | None | Unset = UNSET,
    ip_address: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_action: None | str | Unset
    if isinstance(action, Unset):
        json_action = UNSET
    else:
        json_action = action
    params["action"] = json_action

    json_resource_type: None | str | Unset
    if isinstance(resource_type, Unset):
        json_resource_type = UNSET
    else:
        json_resource_type = resource_type
    params["resource_type"] = json_resource_type

    json_username: None | str | Unset
    if isinstance(username, Unset):
        json_username = UNSET
    else:
        json_username = username
    params["username"] = json_username

    json_from_date: None | str | Unset
    if isinstance(from_date, Unset):
        json_from_date = UNSET
    elif isinstance(from_date, datetime.datetime):
        json_from_date = from_date.isoformat()
    else:
        json_from_date = from_date
    params["from_date"] = json_from_date

    json_to_date: None | str | Unset
    if isinstance(to_date, Unset):
        json_to_date = UNSET
    elif isinstance(to_date, datetime.datetime):
        json_to_date = to_date.isoformat()
    else:
        json_to_date = to_date
    params["to_date"] = json_to_date

    json_ip_address: None | str | Unset
    if isinstance(ip_address, Unset):
        json_ip_address = UNSET
    else:
        json_ip_address = ip_address
    params["ip_address"] = json_ip_address

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/audit-log/export",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = response.json()
        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Any | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    action: None | str | Unset = UNSET,
    resource_type: None | str | Unset = UNSET,
    username: None | str | Unset = UNSET,
    from_date: datetime.datetime | None | Unset = UNSET,
    to_date: datetime.datetime | None | Unset = UNSET,
    ip_address: None | str | Unset = UNSET,
) -> Response[Any | HTTPValidationError]:
    """Export Csv

     Download filtered audit log as CSV.

    Args:
        action (None | str | Unset):
        resource_type (None | str | Unset):
        username (None | str | Unset):
        from_date (datetime.datetime | None | Unset):
        to_date (datetime.datetime | None | Unset):
        ip_address (None | str | Unset): Exact client address, IPv4 or IPv6. Normalised before
            matching.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        action=action,
        resource_type=resource_type,
        username=username,
        from_date=from_date,
        to_date=to_date,
        ip_address=ip_address,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    action: None | str | Unset = UNSET,
    resource_type: None | str | Unset = UNSET,
    username: None | str | Unset = UNSET,
    from_date: datetime.datetime | None | Unset = UNSET,
    to_date: datetime.datetime | None | Unset = UNSET,
    ip_address: None | str | Unset = UNSET,
) -> Any | HTTPValidationError | None:
    """Export Csv

     Download filtered audit log as CSV.

    Args:
        action (None | str | Unset):
        resource_type (None | str | Unset):
        username (None | str | Unset):
        from_date (datetime.datetime | None | Unset):
        to_date (datetime.datetime | None | Unset):
        ip_address (None | str | Unset): Exact client address, IPv4 or IPv6. Normalised before
            matching.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        action=action,
        resource_type=resource_type,
        username=username,
        from_date=from_date,
        to_date=to_date,
        ip_address=ip_address,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    action: None | str | Unset = UNSET,
    resource_type: None | str | Unset = UNSET,
    username: None | str | Unset = UNSET,
    from_date: datetime.datetime | None | Unset = UNSET,
    to_date: datetime.datetime | None | Unset = UNSET,
    ip_address: None | str | Unset = UNSET,
) -> Response[Any | HTTPValidationError]:
    """Export Csv

     Download filtered audit log as CSV.

    Args:
        action (None | str | Unset):
        resource_type (None | str | Unset):
        username (None | str | Unset):
        from_date (datetime.datetime | None | Unset):
        to_date (datetime.datetime | None | Unset):
        ip_address (None | str | Unset): Exact client address, IPv4 or IPv6. Normalised before
            matching.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        action=action,
        resource_type=resource_type,
        username=username,
        from_date=from_date,
        to_date=to_date,
        ip_address=ip_address,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    action: None | str | Unset = UNSET,
    resource_type: None | str | Unset = UNSET,
    username: None | str | Unset = UNSET,
    from_date: datetime.datetime | None | Unset = UNSET,
    to_date: datetime.datetime | None | Unset = UNSET,
    ip_address: None | str | Unset = UNSET,
) -> Any | HTTPValidationError | None:
    """Export Csv

     Download filtered audit log as CSV.

    Args:
        action (None | str | Unset):
        resource_type (None | str | Unset):
        username (None | str | Unset):
        from_date (datetime.datetime | None | Unset):
        to_date (datetime.datetime | None | Unset):
        ip_address (None | str | Unset): Exact client address, IPv4 or IPv6. Normalised before
            matching.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            action=action,
            resource_type=resource_type,
            username=username,
            from_date=from_date,
            to_date=to_date,
            ip_address=ip_address,
        )
    ).parsed
