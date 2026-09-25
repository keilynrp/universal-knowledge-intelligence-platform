"""Which reads are audited, decided without a database or a request object.

Phase 4 of the openspec change ``attribute-and-audit-reads`` (#375). The audit
log recorded only mutations, so "what did this credential read" had no answer:
an empty window could mean "never used" or "used only to read", including
reading ``GET /audit-log/export``, which did not record its own execution.

Auditing every read would bury the log. Reads are audited by class instead, and
this module is the whole rule, strings in and a class out:

    read_audit_class(method, route, query, principal) -> "EXPORT" | "READ" | None

  1. method is not GET or HEAD                      -> None (mutations are audited as before)
  2. no principal                                   -> None (anonymous; the request log has it)
  3. route in EXPORT_ROUTES                         -> "EXPORT"
  4. route under /audit-log                         -> "READ"  (reading the evidence is evidence)
  5. authenticated with an API key                  -> "READ"  (programmatic access)
  6. skip > 0, or limit > BULK_LIMIT                -> "READ"  (a page past the first, or a bulk pull)
  7. otherwise                                      -> None

``BULK_LIMIT`` comes from what the UI actually asks for: pages of 20 to 50, and
one dashboard widget that loads 500 entities on every render. Anything above
that is not browsing, and ``skip > 0`` catches a pagination sweep whatever its
page size, which is exactly what the 2026-09-22 tabletop saw.

An audited read keeps ``limit``, ``skip`` and the *names* of the query
parameters, never their values: a search term can be a person's name, and an
access log must not become a record of what people were searched for.
"""
from __future__ import annotations

from collections.abc import Mapping

from backend.principal import Principal

EXPORT = "EXPORT"
READ = "READ"

BULK_LIMIT = 500

#: Every GET route that hands data out as a file or an export payload. A
#: route-coverage test fails when a GET route that looks like one (its template
#: says export, download or csv, or it streams a file) is in neither this table
#: nor ``EXPORT_EXCLUSIONS``.
EXPORT_ROUTES: frozenset[str] = frozenset({
    "/audit-log/export",
    "/cube/export/{domain_id}",
    "/export",
    "/export/graph",
    "/exports/sales-deck",
    "/exports/sales-deck/data",
    "/exports/{entity_id}/jsonld",
    "/field-correspondence-rules/review-export.csv",
})

#: Routes that look like exports and hand out no data. Each needs a reason.
EXPORT_EXCLUSIONS: dict[str, str] = {
    "/retrospective/export/readiness": "reports whether a warehouse export is configured; returns no records",
}

_AUDIT_LOG_PREFIX = "/audit-log"
_READ_METHODS = frozenset({"GET", "HEAD"})


def _int_param(query: Mapping[str, str], name: str) -> int | None:
    raw = query.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def read_audit_class(
    method: str,
    route: str,
    query: Mapping[str, str],
    principal: Principal | None,
) -> str | None:
    """The audit class of a read, or None if it is not audited. See the module docstring."""
    if method.upper() not in _READ_METHODS:
        return None
    if principal is None:
        return None
    if route in EXPORT_ROUTES:
        return EXPORT
    if route == _AUDIT_LOG_PREFIX or route.startswith(_AUDIT_LOG_PREFIX + "/"):
        return READ
    if principal.api_key_id is not None:
        return READ
    skip = _int_param(query, "skip")
    limit = _int_param(query, "limit")
    if (skip is not None and skip > 0) or (limit is not None and limit > BULK_LIMIT):
        return READ
    return None


def read_details(query: Mapping[str, str]) -> dict[str, object]:
    """What an audited read records about its query: paging, and parameter names only."""
    details: dict[str, object] = {"query_keys": sorted(set(query.keys()))}
    for name in ("limit", "skip"):
        value = _int_param(query, name)
        if value is not None:
            details[name] = value
    return details
