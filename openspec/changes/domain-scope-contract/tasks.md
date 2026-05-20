## Implementation Tasks

### Phase 1 — Backend core module

- [ ] **TASK-001** Create `backend/domain_scope.py`
  - Define `DomainScope = str` type alias
  - Implement `is_valid_scope(s: str) -> bool`: returns `True` for `"all"`, `"legacy_default"`, and strings matching `^domain:.+$`; `False` otherwise
  - Implement `parse_scope(raw: str | None) -> DomainScope`: maps `None`/`""` → `"all"`, `"default"` → `"legacy_default"`, `"all"` → `"all"`, any other string `s` → `"domain:{s}"`; already-valid `"domain:x"` and `"legacy_default"` pass through unchanged
  - Implement `resolve_domain_filter(scope: DomainScope, model) -> BinaryExpression | None`: `"all"` → `None`, `"domain:{id}"` → `model.domain == id`, `"legacy_default"` → `or_(model.domain == "default", model.domain.is_(None))`
  - No external dependencies beyond SQLAlchemy (already in use)

- [ ] **TASK-002** Write unit tests for `backend/domain_scope.py`
  - File: `backend/tests/test_domain_scope.py`
  - Cover all `is_valid_scope` scenarios: valid strings, invalid strings
  - Cover all `parse_scope` scenarios: None, empty string, `"default"`, `"all"`, bare ID, already-valid scope
  - Cover all `resolve_domain_filter` scenarios: `"all"` returns None, `"domain:science"` returns equality filter, `"legacy_default"` returns OR filter
  - Test that resolver does not import or touch tenant_access.py

### Phase 2 — Backend router migration

- [ ] **TASK-003** Migrate `backend/routers/analytics.py`
  - Remove inline `if domain_id == "all":` / `elif domain_id == "default":` blocks
  - Call `parse_scope(domain_id)` on route entry to normalize the raw path param
  - Apply `resolve_domain_filter(scope, RawEntity)` to build the WHERE clause
  - Verify: no `== "all"`, `== "default"`, or bare `.domain.is_(None)` patterns remain

- [ ] **TASK-004** Migrate `backend/routers/entities.py`
  - Same pattern as TASK-003
  - All entity list endpoints and enrich endpoints use `resolve_domain_filter`

- [ ] **TASK-005** Migrate `backend/routers/ai_rag.py`
  - RAG context indexing and query endpoints use `resolve_domain_filter`

- [ ] **TASK-006** Migrate `backend/routers/domains.py`
  - Domain-scoped queries use `resolve_domain_filter`

- [ ] **TASK-007** Migrate `backend/olap.py`
  - `_load_domain_df()` uses `resolve_domain_filter` instead of inline comparisons

- [ ] **TASK-008** Migrate `backend/routers/reports.py`
  - Report generation endpoints use `resolve_domain_filter`

- [ ] **TASK-009** Migrate `backend/enrichment_worker.py`
  - Any domain-scoped entity queries use `resolve_domain_filter`

- [ ] **TASK-010** Update `backend/tenant_access.py`
  - Delegate domain filtering to `resolve_domain_filter` where applicable
  - Tenant/org scoping logic remains in `tenant_access.py` — do not merge concerns

### Phase 3 — Frontend contract

- [ ] **TASK-011** Update `frontend/app/contexts/DomainContext.tsx`
  - Export `type DomainScope = string`
  - Type `activeDomainId` as `DomainScope` in `DomainContextType`
  - Export `isAllScope(scope: DomainScope): boolean`
  - Export `isLegacyScope(scope: DomainScope): boolean`
  - Export `domainIdFromScope(scope: DomainScope): string | null`

- [ ] **TASK-012** Update domain selector to emit canonical scope values
  - Concrete domain options emit `"domain:{id}"` (not bare `id`)
  - "All" option emits `"all"`
  - Verify `setActiveDomainId` is never called with `""` or `"default"`

- [ ] **TASK-013** Migrate `frontend/app/analytics/dashboard/page.tsx`
  - Replace `activeDomainId === "all"` with `isAllScope(activeDomainId)`
  - Replace `activeDomainId === "default"` or `=== "legacy_default"` with `isLegacyScope(activeDomainId)`
  - Use `domainIdFromScope(activeDomainId)` to build API path segments

- [ ] **TASK-014** Migrate `frontend/app/analytics/topics/page.tsx`
  - Same pattern as TASK-013

- [ ] **TASK-015** Migrate `frontend/app/analytics/olap/page.tsx`
  - Use `domainIdFromScope(activeDomainId)` for cube dimension and query endpoints

- [ ] **TASK-016** Migrate remaining frontend pages under `frontend/app/`
  - Audit: `entities/page.tsx`, `analytics/graph/page.tsx`, `page.tsx` (home), any other page using `activeDomainId` comparisons
  - Replace all raw equality comparisons with helper function calls

### Phase 4 — CI lint guard

- [ ] **TASK-017** Add lint check script `scripts/lint_domain_scope.py`
  - Scans all `*.py` files under `backend/routers/` and `backend/enrichment_worker.py`
  - Fails (exit 1) if any file contains the pattern `== "default"` or `== "all"` in a context that is a domain scope comparison
  - Prints file path + line number for each violation
  - Passes silently (exit 0) when no violations found

- [ ] **TASK-018** Wire lint check into CI
  - Add a step to the existing test pipeline (e.g., `pytest` job or a dedicated `lint` job) that runs `python scripts/lint_domain_scope.py`
  - Confirm the step fails the build on violation

### Phase 5 — Verification

- [ ] **TASK-019** Run full backend test suite
  - `pytest backend/tests -q`
  - All existing tests must pass
  - New tests from TASK-002 must pass
  - No regressions in analytics, entities, OLAP, RAG, reports endpoints

- [ ] **TASK-020** Run frontend type check
  - `cd frontend && npm exec tsc -- --noEmit --pretty false`
  - Zero type errors

- [ ] **TASK-021** Manual smoke test
  - With `domain_id = "all"`: analytics and OLAP endpoints return aggregate data (no WHERE clause on domain)
  - With `domain_id = "domain:science"`: only science-domain records returned
  - With `domain_id = "legacy_default"`: records where `domain = "default"` OR `domain IS NULL` are included
  - Frontend domain selector emits correct scope strings; page-level rendering branches correctly via helper functions

## Acceptance Criteria

- `backend/domain_scope.py` exists and all unit tests pass
- Zero inline `== "default"` or `== "all"` domain comparisons in `backend/routers/*.py` or `backend/enrichment_worker.py`
- `resolve_domain_filter` is the only path for domain scoping in backend queries
- `DomainScope` type and `isAllScope`, `isLegacyScope`, `domainIdFromScope` exported from `DomainContext.tsx`
- Zero `=== "all"` or `=== "default"` raw domain comparisons in `frontend/app/**/*.tsx`
- CI lint check passes with zero violations on a fully migrated codebase
- All existing tests pass; new unit tests added for resolver and helpers
