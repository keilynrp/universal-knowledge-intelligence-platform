"""The read-audit rule table, and the guard that keeps it complete (#375).

The rule lives in ``backend/read_audit.py`` as a pure function; these tests are
its truth table. The route-coverage test is the other half: an export route
added later must either be audited or excluded with a written reason, never
land silently in neither.
"""
from __future__ import annotations

import inspect
import re

import pytest

from backend.main import app
from backend.principal import Principal
from backend.read_audit import (
    BULK_LIMIT,
    EXPORT,
    EXPORT_EXCLUSIONS,
    EXPORT_ROUTES,
    READ,
    read_audit_class,
    read_details,
)

JWT = Principal(user_id=1, session_id="s")
KEY = Principal(user_id=1, api_key_id=9)


@pytest.mark.parametrize(
    ("method", "route", "query", "principal", "expected"),
    [
        # 1. mutations belong to the mutation path
        ("POST", "/audit-log/export", {}, JWT, None),
        ("DELETE", "/entities/{entity_id}", {}, KEY, None),
        # 2. anonymous reads are not audited
        ("GET", "/audit-log/export", {}, None, None),
        ("GET", "/entities", {"skip": "100"}, None, None),
        # 3. exports, whoever reads them
        ("GET", "/audit-log/export", {}, JWT, EXPORT),
        ("HEAD", "/export", {}, JWT, EXPORT),
        ("get", "/exports/{entity_id}/jsonld", {}, JWT, EXPORT),
        # 4. reading the evidence is evidence
        ("GET", "/audit-log", {}, JWT, READ),
        ("GET", "/audit-log/stats", {}, JWT, READ),
        ("GET", "/audit-logger", {}, JWT, None),  # prefix match is on a path segment
        # 5. every API-key read
        ("GET", "/entities", {}, KEY, READ),
        ("GET", "/users/me", {}, KEY, READ),
        # 6. paging past the first page, or a bulk pull
        ("GET", "/entities", {"skip": "1"}, JWT, READ),
        ("GET", "/entities", {"skip": "0", "limit": str(BULK_LIMIT)}, JWT, None),
        ("GET", "/entities", {"limit": str(BULK_LIMIT + 1)}, JWT, READ),
        ("GET", "/entities", {"skip": "junk", "limit": "junk"}, JWT, None),
        # 7. ordinary browsing
        ("GET", "/entities", {}, JWT, None),
        ("GET", "/users/me", {"q": "jane"}, JWT, None),
    ],
)
def test_rule_table(method, route, query, principal, expected):
    assert read_audit_class(method, route, query, principal) == expected


def test_the_ui_s_largest_routine_request_is_not_audited():
    """A dashboard widget loads /entities?limit=500 on every render."""
    assert BULK_LIMIT == 500
    assert read_audit_class("GET", "/entities", {"domain_id": "x", "limit": "500"}, JWT) is None


def test_details_keep_names_and_paging_but_no_values():
    details = read_details({"q": "jane doe", "skip": "50", "domain_id": "science"})

    assert details == {"query_keys": ["domain_id", "q", "skip"], "skip": 50}
    assert "jane" not in repr(details)
    assert "science" not in repr(details)


# ── Route coverage ────────────────────────────────────────────────────────────

_LOOKS_LIKE_EXPORT = re.compile(r"export|download|csv", re.IGNORECASE)
_STREAMS_A_FILE = re.compile(r"StreamingResponse\(|FileResponse\(|Content-Disposition|media_type\s*=")


def _get_routes() -> dict[str, object]:
    """Every GET route template on the app, walking FastAPI 0.140's nested routers."""
    found: dict[str, object] = {}

    def walk(routes, prefix=""):
        for route in routes:
            context = getattr(route, "include_context", None)
            if context is not None:
                walk(context.included_router.routes, prefix + (context.prefix or ""))
                continue
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None)
            nested = getattr(route, "routes", None)
            if nested and path is not None and not methods:
                walk(nested, prefix + path)
                continue
            if path and methods and "GET" in methods:
                found[prefix + path] = route

    walk(app.routes)
    return found


def _looks_like_export(template: str, route: object) -> bool:
    if _LOOKS_LIKE_EXPORT.search(template):
        return True
    try:
        source = inspect.getsource(route.endpoint)  # type: ignore[attr-defined]
    except (OSError, TypeError, AttributeError):
        return False
    return bool(_STREAMS_A_FILE.search(source))


def test_every_export_route_is_audited_or_excluded_with_a_reason():
    routes = _get_routes()
    assert len(routes) > 100, "the walk found too few routes; the enumeration is broken, not the table"

    unclassified = sorted(
        template for template, route in routes.items()
        if _looks_like_export(template, route)
        and template not in EXPORT_ROUTES
        and template not in EXPORT_EXCLUSIONS
    )
    assert not unclassified, (
        "GET routes that look like exports are neither audited nor excluded. Add each to "
        "EXPORT_ROUTES in backend/read_audit.py, or to EXPORT_EXCLUSIONS with the reason it "
        "hands out no data:\n  " + "\n  ".join(unclassified)
    )


def test_the_tables_name_only_routes_that_exist():
    """A stale entry audits nothing and says nothing; renaming a route must fail here."""
    routes = _get_routes()
    dead = sorted((EXPORT_ROUTES | set(EXPORT_EXCLUSIONS)) - set(routes))
    assert not dead, f"entries that match no GET route: {dead}"


def test_every_exclusion_says_why():
    assert all(reason.strip() for reason in EXPORT_EXCLUSIONS.values())
