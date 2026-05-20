## Context

Every entity-reading endpoint in UKIP must apply three guards before returning data:

1. **Source exclusion** — `source != 'graph_materializer'` (graph-derived synthetic entities must not appear in user-facing counts or lists)
2. **Domain filter** — `resolve_domain_filter(parse_scope(scope), RawEntity)` (scope to a workspace or "all")
3. **Org filter** — `scope_query_to_org(query, RawEntity, org_id)` (multi-tenant isolation)

Currently these are applied inline, independently, in 18 routers and the derived_status_service. Missing any one of the three produces silently wrong results. The domain-scope-contract change (already landed) centralised guard #2 behind `parse_scope` / `resolve_domain_filter`; this change wraps all three behind a single factory.

## Goals / Non-Goals

**Goals:**
- Single `entity_base_q(db, scope, org_id)` factory that always applies all three guards
- Common count helpers: `count_total`, `count_by_status`, `count_enriched`
- Full replacement inside `derived_status_service.py` (highest duplication: 7×)
- Partial replacement in the three highest-volume routers: `entities.py`, `analytics.py`, `disambiguation.py`

**Non-Goals:**
- Full sweep of all 18 routers (too disruptive in one PR; remaining routers will migrate opportunistically)
- Introducing a repository class, abstract base, or async variants (keep it simple — plain functions)
- Changing query return types or response shapes
- Applying the pattern to non-RawEntity models (EntityRelationship, AuthorityRecord, etc.)

## Decisions

### D1: Module-level functions, not a class

**Decision:** `entity_query.py` exposes plain module-level functions, not a `EntityQueryService` class.

**Rationale:** The existing codebase uses plain functions for shared logic (`domain_scope.py`, `enrichment_worker.py`). A class adds boilerplate (instantiation, `self`) with no benefit when there is no shared state. The service pattern is already used for stateful services (`DerivedStatusService`, `EntityService`); this module has no state.

**Alternative considered:** `EntityQueryService` static methods. Rejected: same as module functions but with extra noise.

### D2: `org_id` is optional, defaults to None (no org scoping)

**Decision:** `entity_base_q(db, scope, org_id=None)` — org scoping is skipped when `org_id is None`.

**Rationale:** Some callers (tests, admin utilities, derived_status_service) don't have an org context. Making `org_id` optional keeps the factory usable everywhere without requiring a sentinel value. `scope_query_to_org` already handles `None` gracefully.

### D3: Scope argument is the raw string from the router, not pre-parsed

**Decision:** `entity_base_q` accepts `scope: str` and calls `parse_scope()` internally.

**Rationale:** Routers receive scope as a string from the query parameter or domain ID. Requiring pre-parsed scope would force callers to add an extra import and call. The function does it once internally, consistent with how `derived_status_service` currently works.

### D4: Count helpers are thin wrappers, not new SQL functions

**Decision:** `count_total(db, scope, org_id)` calls `entity_base_q(...).count()`. No raw SQL.

**Rationale:** SQLAlchemy ORM `.count()` is already indexed and fast for these queries. Raw SQL would bypass the ORM guard layer and require duplicating the filter logic.

## Risks / Trade-offs

- **[Risk] Routers not yet migrated still apply guards inline** — Partial migration means two styles coexist. Mitigation: the new module is additive; old code still works. Document which routers are migrated in a comment at the top of `entity_query.py`.

- **[Risk] org_id=None silently skips org isolation** — A caller that forgets org_id gets unscoped results. Mitigation: add a docstring warning; existing callers that need org scoping already import `scope_query_to_org` explicitly and won't silently regress.

- **[Trade-off] Three routers migrated, 15 deferred** — The highest-duplication locations are addressed now; the rest are left for future PRs. Accepted: a full sweep would make the diff too large to review confidently.

## Migration Plan

1. Create `backend/services/entity_query.py` with the factory and helpers
2. Update `derived_status_service.py` — all 7 inline query blocks
3. Update `entities.py` — enrich stats, count queries
4. Update `analytics.py` — dashboard summary entity counts
5. Update `disambiguation.py` — entity fetch for field grouping
6. Add `backend/tests/test_entity_query.py`
7. Run full test suite; no response-shape changes expected

**Rollback:** `entity_query.py` is purely additive. If a caller breaks, revert the caller's import; the old inline pattern still works.

## Open Questions

*(none)*
