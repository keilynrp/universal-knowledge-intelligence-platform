## Why

Eighteen routers and `derived_status_service.py` each construct raw `db.query(models.RawEntity)` calls by hand, composing the same three guards every time: exclude `source = 'graph_materializer'`, apply `resolve_domain_filter(scope)`, and apply `scope_query_to_org(org_id)`. The `source != 'graph_materializer'` exclusion alone is copy-pasted seven times inside `derived_status_service.py`. Any new query that forgets one guard silently returns wrong data — no type checker or linter catches it.

## What Changes

- **Create `backend/services/entity_query.py`** — a thin read-only query-builder module that encapsulates the three mandatory guards behind a single `entity_base_q(db, scope, org_id)` factory function and common count helpers (`count_total`, `count_by_status`, `count_enriched`).
- **Refactor `backend/services/derived_status_service.py`** — replace all seven inline `db.query(RawEntity).filter(source != 'graph_materializer')` blocks with calls to `entity_base_q`.
- **Refactor the three highest-duplication routers** — `backend/routers/entities.py`, `backend/routers/analytics.py`, `backend/routers/disambiguation.py` — to use `entity_base_q` for their entity count and list queries.
- **No API or schema changes** — this is an internal refactor; all response shapes remain identical.

## Capabilities

### New Capabilities

- `entity-query-service`: A `backend/services/entity_query.py` module exposing `entity_base_q(db, scope, org_id)` and count helpers, centralizing the three mandatory RawEntity query guards.

### Modified Capabilities

*(none — no spec-level behavior changes)*

## Impact

- **`backend/services/entity_query.py`** — new file (~60 lines)
- **`backend/services/derived_status_service.py`** — 7 inline query blocks replaced
- **`backend/routers/entities.py`** — entity count/list queries updated
- **`backend/routers/analytics.py`** — dashboard and stats queries updated
- **`backend/routers/disambiguation.py`** — entity fetch queries updated
- **`backend/tests/test_entity_query.py`** — new test file for the query service
- No dependency changes; `entity_query.py` imports only from `backend.models`, `backend.domain_scope`, `backend.tenant_access`, `backend.schemas`
