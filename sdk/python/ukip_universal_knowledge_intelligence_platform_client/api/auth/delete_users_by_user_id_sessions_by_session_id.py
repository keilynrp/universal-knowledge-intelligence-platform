from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    user_id: int,
    session_id: int,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/users/{user_id}/sessions/{session_id}".format(
            user_id=quote(str(user_id), safe=""),
            session_id=quote(str(session_id), safe=""),
        ),
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
    user_id: int,
    session_id: int,
    *,
    client: AuthenticatedClient,
) -> Response[Any | HTTPValidationError]:
    """Revoke User Session

     Revoke one session belonging to another user. Requires super_admin.

    Unlike deactivation there is no last-super_admin guard, and none is wanted:
    this removes a credential, not a person, and the account keeps working from
    its other sessions.

    Args:
        user_id (int):
        session_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        user_id=user_id,
        session_id=session_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    user_id: int,
    session_id: int,
    *,
    client: AuthenticatedClient,
) -> Any | HTTPValidationError | None:
    """Revoke User Session

     Revoke one session belonging to another user. Requires super_admin.

    Unlike deactivation there is no last-super_admin guard, and none is wanted:
    this removes a credential, not a person, and the account keeps working from
    its other sessions.

    Args:
        user_id (int):
        session_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return sync_detailed(
        user_id=user_id,
        session_id=session_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    user_id: int,
    session_id: int,
    *,
    client: AuthenticatedClient,
) -> Response[Any | HTTPValidationError]:
    """Revoke User Session

     Revoke one session belonging to another user. Requires super_admin.

    Unlike deactivation there is no last-super_admin guard, and none is wanted:
    this removes a credential, not a person, and the account keeps working from
    its other sessions.

    Args:
        user_id (int):
        session_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        user_id=user_id,
        session_id=session_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    user_id: int,
    session_id: int,
    *,
    client: AuthenticatedClient,
) -> Any | HTTPValidationError | None:
    """Revoke User Session

     Revoke one session belonging to another user. Requires super_admin.

    Unlike deactivation there is no last-super_admin guard, and none is wanted:
    this removes a credential, not a person, and the account keeps working from
    its other sessions.

    Args:
        user_id (int):
        session_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            user_id=user_id,
            session_id=session_id,
            client=client,
        )
    ).parsed
