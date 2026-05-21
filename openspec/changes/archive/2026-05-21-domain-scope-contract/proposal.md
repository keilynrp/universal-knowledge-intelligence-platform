## Why

UKIP has no single domain scope contract. The strings `"all"`, `"default"`, `""`, and concrete domain IDs are interpreted independently by the frontend context, backend analytics, OLAP, graph, RAG, enrichment, and reporting layers — causing recurring regressions where a scope change in one layer does not propagate cleanly to others, and where historical `"default"` records are silently excluded or double-counted in aggregate queries.

## What Changes

- **Introduce a `DomainScope` value type** with three legal values: `all`, `domain:{id}`, `legacy_default`. All scope-aware code uses this type exclusively.
- **Backend scope resolver** (`backend/domain_scope.py`) — a single function that converts any `DomainScope` value into a SQLAlchemy filter, replacing scattered `if domain_id == "all"` / `if domain_id == "default"` blocks across every router.
- **Frontend typed scope** — `DomainContext` emits a typed `DomainScope` string; all pages consume it without local re-interpretation.
- **Deprecate raw `"default"` string** — internal code that compares against the literal `"default"` is replaced by the resolver. Historical records stored with `domain = "default"` continue to work under `legacy_default` scope.
- **All affected endpoints** updated to call the resolver instead of branching inline.

## Capabilities

### New Capabilities

- `domain-scope-resolver`: Backend pure function and Pydantic type that converts a `DomainScope` string into a SQLAlchemy WHERE clause. Covers `all` (no domain filter), `domain:{id}` (exact match), and `legacy_default` (matches `"default"` and NULL). Used by every scope-aware router.
- `domain-scope-frontend-contract`: Typed `DomainScope` value exported from `DomainContext`; replaces ad-hoc `activeDomainId === "all"` / `=== "default"` comparisons in pages and components.

### Modified Capabilities

- `system-hardening-and-regression-control`: Domain scope contract implementation satisfies the first item in the progressive hardening sequence defined in this spec.

## Impact

- **New file**: `backend/domain_scope.py` — resolver, type alias, helpers
- **Modified backend**: `backend/tenant_access.py`, `backend/routers/analytics.py`, `backend/routers/entities.py`, `backend/routers/ai_rag.py`, `backend/routers/domains.py`, `backend/olap.py`, `backend/routers/reports.py`, `backend/enrichment_worker.py` — replace inline domain string comparisons with resolver calls
- **Modified frontend**: `frontend/app/contexts/DomainContext.tsx` — export `DomainScope` type; `frontend/app/` pages — replace `=== "all"` / `=== "default"` comparisons with typed scope checks
- **No new dependencies** — pure Python typing + SQLAlchemy filters already in use
- **No database migration** — stored domain values are unchanged; resolver adapts at query time
