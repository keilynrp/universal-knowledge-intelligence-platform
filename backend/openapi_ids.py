"""
Stable OpenAPI operation identifiers.

Generated SDK clients turn each ``operationId`` into a public method name, so
the identifier is part of UKIP's external contract. FastAPI's default is
``{function_name}_{path}_{method}`` — which makes that public name a function
of implementation detail. Renaming a private handler would silently rename a
method every integrator calls.

We derive from **method + path** instead: the actual HTTP contract. A path or
method change *is* a breaking API change and should rename the client method;
an internal refactor is not and must not.

Trade-off, accepted deliberately: names are mechanical, and deep parameterized
routes get long ones (``get_analyzers_coauthorship_by_domain_id_diagnostics``).
That is the price of decoupling the public surface from internal naming. It can
be improved later per route with an explicit ``operation_id=`` on the decorator
— an additive, opt-in change that does not reintroduce the coupling anywhere
else.
"""
from __future__ import annotations

import re

from fastapi.routing import APIRoute

#: Order matters only for readability of the result; any deterministic pick
#: works because (method, path) is unique by construction.
_METHOD_PRIORITY = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")

_PARAM = re.compile(r"^\{(.+)\}$")
_NON_IDENT = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    """Lowercase, underscore-joined, identifier-safe."""
    return _NON_IDENT.sub("_", text.lower()).strip("_")


def _primary_method(route: APIRoute) -> str:
    methods = route.methods or set()
    for candidate in _METHOD_PRIORITY:
        if candidate in methods:
            return candidate
    return sorted(methods)[0] if methods else "get"


def operation_id_for(route: APIRoute) -> str:
    """Return the operationId for *route*, derived from its method and path.

    ``GET  /users/me``                -> ``get_users_me``
    ``DELETE /api-keys/{key_id}``     -> ``delete_api_keys_by_key_id``
    ``GET  /a/{x}/b/{y}``             -> ``get_a_by_x_b_by_y``
    """
    parts: list[str] = [_primary_method(route).lower()]

    for segment in route.path.split("/"):
        if not segment:
            continue
        parameter = _PARAM.match(segment)
        if parameter:
            parts.append("by")
            parts.append(_slug(parameter.group(1)))
        else:
            parts.append(_slug(segment))

    return "_".join(part for part in parts if part)
