"""Who a request is acting as, once authentication has accepted it.

The auth dependencies resolve the acting identity on every authenticated
request, through exactly the checks that decide whether the request proceeds.
They record the result here so that the request log and the audit middleware
read it instead of re-deriving it. Re-deriving it is how an API-key mutation
came to be audited with no identity, and a revoked token with one
(openspec change ``attribute-and-audit-reads``).

Nothing is recorded for a request that authentication refused, so a missing
principal means anonymous or refused, never "unknown but accepted".

There is no username on purpose: the id is enough to join, and whatever is
recorded here ends up in log lines.
"""
from __future__ import annotations

from dataclasses import dataclass

from starlette.requests import Request


@dataclass(frozen=True)
class Principal:
    user_id: int
    session_id: str | None = None   # JWT: the ``sid`` naming a user_sessions row
    api_key_id: int | None = None   # API key: the key's row id

    def log_fields(self) -> dict[str, int | str]:
        """The identity fields for a log record, omitting the ones that do not apply."""
        fields: dict[str, int | str] = {"user_id": self.user_id}
        if self.session_id is not None:
            fields["session_id"] = self.session_id
        if self.api_key_id is not None:
            fields["api_key_id"] = self.api_key_id
        return fields


def record_principal(request: Request, principal: Principal) -> None:
    request.state.principal = principal


def principal_of(request: Request) -> Principal | None:
    """The accepted principal of a request, or None if there was none.

    Middlewares read this after ``call_next``. Starlette keeps ``request.state``
    in the ASGI scope, which the endpoint's dependencies and every
    ``BaseHTTPMiddleware`` share; ``test_request_principal.py`` holds that.
    """
    principal = getattr(request.state, "principal", None)
    return principal if isinstance(principal, Principal) else None
