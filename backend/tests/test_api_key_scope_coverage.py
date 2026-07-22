"""
Route-coverage guard for API key scope classification.

Spec: openspec/changes/enforce-api-key-scopes/specs/api-key-scope-enforcement/spec.md
  - "Every route resolves to a scope"

Two distinct jobs here:

1. **Totality** — every registered route classifies. This holds by construction
   (``scope_required`` has a fail-closed default), so it guards against a future
   refactor that introduces a hole rather than proving today's behaviour.

2. **Liveness of the tables** — every hand-written entry in ``ADMIN_PATHS``,
   ``ADMIN_EXEMPT_PATHS``, and ``READ_OVERRIDES`` must correspond to a route
   that actually exists. A typo'd or stale entry is dead configuration that
   silently protects nothing, and nothing else would ever tell us.
"""
from __future__ import annotations

import pytest

from backend.api_key_scopes import (
    ADMIN,
    ADMIN_EXEMPT_PATHS,
    ADMIN_PATHS,
    ALL_SCOPES,
    READ,
    READ_OVERRIDES,
    WRITE,
    scope_required,
)
from backend.main import app

#: Routes served by the framework or intentionally public; they never carry an
#: API key, so they are excluded from table-liveness accounting.
_INFRA_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/static", "/embed", "/health")


def _app_routes() -> list[tuple[str, str]]:
    """Every (method, route-template) pair registered on the application."""
    pairs: list[tuple[str, str]] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        methods = getattr(route, "methods", None)
        if not methods:  # WebSocket routes expose no methods
            pairs.append(("GET", path))
            continue
        pairs.extend((method, path) for method in methods)
    return sorted(set(pairs))


def _is_infra(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _INFRA_PREFIXES)


ROUTES = _app_routes()


def test_application_exposes_routes() -> None:
    """Guard the guard: an empty route list would make every check below vacuous."""
    assert len(ROUTES) > 300


def test_every_route_resolves_to_exactly_one_scope() -> None:
    unclassified = [
        (method, path)
        for method, path in ROUTES
        if scope_required(method, path) not in ALL_SCOPES
    ]
    assert unclassified == []


def test_every_admin_prefix_matches_a_real_route() -> None:
    """A prefix matching nothing is dead configuration."""
    dead = [
        prefix
        for prefix in ADMIN_PATHS
        if not any(
            path == prefix or path.startswith(prefix + "/") for _, path in ROUTES
        )
    ]
    assert dead == [], f"ADMIN_PATHS entries match no route: {dead}"


def test_every_admin_exemption_matches_a_real_route() -> None:
    dead = [
        exempt
        for exempt in ADMIN_EXEMPT_PATHS
        if not any(
            path == exempt or path.startswith(exempt + "/") for _, path in ROUTES
        )
    ]
    assert dead == [], f"ADMIN_EXEMPT_PATHS entries match no route: {dead}"


def test_every_read_override_matches_a_real_route() -> None:
    """An override whose path drifted no longer relaxes anything."""
    registered = set(ROUTES)
    dead = sorted(entry for entry in READ_OVERRIDES if entry not in registered)
    assert dead == [], f"READ_OVERRIDES entries match no route: {dead}"


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/api-keys"),
        ("DELETE", "/api-keys/{key_id}"),
        ("POST", "/users"),
        ("DELETE", "/users/{user_id}"),
        ("POST", "/organizations"),
        ("POST", "/stores"),
        ("PUT", "/settings/auth"),
        ("POST", "/admin/data-lifecycle/purge"),
        ("POST", "/admin/workspace-reset"),
        ("GET", "/ops/secrets"),
        ("POST", "/webhooks"),
    ],
)
def test_known_sensitive_routes_require_admin(method: str, path: str) -> None:
    """Named explicitly so that loosening one of these fails a test by name."""
    assert scope_required(method, path) == ADMIN


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/users/me"),
        ("POST", "/users/me/password"),
        ("GET", "/entities"),
        ("POST", "/entities"),
        ("POST", "/rag/query"),
    ],
)
def test_known_non_admin_routes_are_not_admin(method: str, path: str) -> None:
    """The complement: over-restriction is safe, but not free. Catch it too."""
    assert scope_required(method, path) != ADMIN


def test_mutating_routes_default_to_write_not_read() -> None:
    """The fail-closed default must actually be reached by ordinary mutations."""
    mutations = [
        (method, path)
        for method, path in ROUTES
        if method in {"POST", "PUT", "PATCH", "DELETE"} and not _is_infra(path)
    ]
    downgraded = [
        (method, path)
        for method, path in mutations
        if scope_required(method, path) == READ
        and (method, path) not in READ_OVERRIDES
    ]
    assert downgraded == [], (
        f"mutating routes classified as read without an explicit override: {downgraded}"
    )


def test_classification_table_is_reportable(tmp_path_factory) -> None:
    """Write the full table to a file so a reviewer can read it after a CI run.

    Deliberately not ``capsys``: capturing the output is exactly what stops it
    from being reviewable. pytest also swallows stdout on a passing test, so a
    file is the only form that survives.
    """
    counts = {READ: 0, WRITE: 0, ADMIN: 0}
    lines: list[str] = []
    for method, path in ROUTES:
        scope = scope_required(method, path)
        counts[scope] += 1
        lines.append(f"{scope:6s} {method:7s} {path}")

    summary = f"totals: {counts} over {len(ROUTES)} route/method pairs"
    report = tmp_path_factory.mktemp("scopes") / "classification.txt"
    report.write_text("\n".join(lines) + "\n\n" + summary + "\n", encoding="utf-8")

    print(f"\nscope classification table -> {report}\n{summary}")

    assert sum(counts.values()) == len(ROUTES)
    assert counts[ADMIN] > 0 and counts[WRITE] > 0 and counts[READ] > 0
