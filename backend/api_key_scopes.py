"""
Scope derivation for UKIP API keys.

Pure logic: no database, no FastAPI, no request object. Every classification is
a function of ``(method, route_template)``, which makes the whole truth table
unit-testable without a client.

Design: openspec/changes/enforce-api-key-scopes/design.md

The rule set is ordered, and the order is the security property:

    1. path is admin-exempt          -> fall through to the method rule
    2. path is under an admin path   -> "admin"
    3. (method, path) is overridden  -> "read"
    4. method is safe                -> "read"
    5. otherwise                     -> "write"     (fail-closed default)

Rule 5 is what makes a route added tomorrow safe by default: an unclassified
mutating route demands a write key rather than none.
"""
from __future__ import annotations

from typing import Iterable

READ = "read"
WRITE = "write"
ADMIN = "admin"

ALL_SCOPES: tuple[str, ...] = (READ, WRITE, ADMIN)

#: Methods that cannot change server state, per RFC 9110 §9.2.1.
SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})

#: Escalating hierarchy: holding a scope implies holding everything below it.
SCOPE_IMPLIES: dict[str, frozenset[str]] = {
    ADMIN: frozenset({ADMIN, WRITE, READ}),
    WRITE: frozenset({WRITE, READ}),
    READ: frozenset({READ}),
}

#: Surfaces where a leaked write-scoped key would be catastrophic rather than
#: merely bad. Matched as path prefixes on the *route template*.
#:
#: The grouping rationale:
#:   - identity and tenancy       -> /users, /organizations
#:   - credential minting         -> /api-keys (a write key must not be able to
#:                                   create an admin key: privilege escalation)
#:   - stored third-party secrets -> /stores
#:   - platform auth config       -> /settings/auth, /auth/sso/settings
#:   - destructive / operational  -> /admin (data fixes, lifecycle purge,
#:                                   workspace reset), /ops (backups, secrets)
#:   - standing data exfiltration -> /webhooks, /alert-channels, /workflows
#:     (all three persist a configuration that ships data to an operator-supplied
#:     URL; creating one with a write key would turn a limited credential into an
#:     open data tap)
ADMIN_PATHS: tuple[str, ...] = (
    "/admin",
    "/alert-channels",
    "/api-keys",
    "/auth/sso/settings",
    "/ops",
    "/organizations",
    "/settings/auth",
    "/stores",
    "/users",
    "/webhooks",
    "/workflows",
)

#: Routes that sit under an admin prefix but are self-service rather than
#: administrative. Evaluated before ADMIN_PATHS.
ADMIN_EXEMPT_PATHS: tuple[str, ...] = (
    "/users/me",
)

#: ``POST`` routes whose effect is a query, a preview, or an export rather than
#: a mutation. Without these, an integrator would need a write-scoped key merely
#: to run a search.
#:
#: Every entry was verified to perform no session mutation in its handler.
#: Incidental writes (audit entries, telemetry) do not make a route a mutation;
#: changing data the caller could otherwise modify does.
READ_OVERRIDES: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/agentic-chat/query"),
        ("POST", "/analytics/roi"),
        ("POST", "/analyze"),
        ("POST", "/cube/query"),
        ("POST", "/exports/excel"),
        ("POST", "/exports/pdf"),
        ("POST", "/exports/pptx"),
        ("POST", "/harmonization/preview/{step_id}"),
        ("POST", "/nlq/query"),
        ("POST", "/rag/query"),
        ("POST", "/retrospective/export/events"),
        ("POST", "/retrospective/export/snapshots"),
        ("POST", "/scientific/dois/preview"),
        ("POST", "/scientific/search"),
        ("POST", "/transformations/preview"),
        ("POST", "/upload/preview"),
        ("POST", "/upload/suggest-mapping"),
    }
)


def _under(path: str, prefix: str) -> bool:
    """True when ``path`` is ``prefix`` or sits beneath it.

    Compares whole segments, so ``/users`` does not match ``/users-summary``.
    """
    return path == prefix or path.startswith(prefix + "/")


def scope_required(method: str, path: str) -> str:
    """Return the scope a key must hold to call ``method path``.

    ``path`` should be the route template (``/entities/{entity_id}``), not a
    concrete URL, so that an identifier containing an admin-looking segment
    cannot alter the classification.
    """
    normalized_method = (method or "").strip().upper()

    if any(_under(path, exempt) for exempt in ADMIN_EXEMPT_PATHS):
        pass  # self-service: skip the admin table, apply the method rule below
    elif any(_under(path, prefix) for prefix in ADMIN_PATHS):
        return ADMIN

    if (normalized_method, path) in READ_OVERRIDES:
        return READ

    if normalized_method in SAFE_METHODS:
        return READ

    return WRITE


def satisfies(granted: Iterable[str], required: str) -> bool:
    """True when any granted scope implies ``required``.

    Unrecognized scope values grant nothing.
    """
    return any(required in SCOPE_IMPLIES.get(scope, frozenset()) for scope in granted)
