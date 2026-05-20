## Implementation Tasks

### Phase 1 — Backend core module

- [x] **TASK-001** Create `backend/domain_scope.py`
  - Define `DomainScope = str` type alias
  - Implement `is_valid_scope(s: str) -> bool`: returns `True` for `"all"`, `"legacy_default"`, and strings matching `^domain:.+$`; `False` otherwise
  - Implement `parse_scope(raw: str | None) -> DomainScope`: maps `None`/`""` → `"all"`, `"default"` → `"legacy_default"`, `"all"` → `"all"`, any other string `s` → `"domain:{s}"`; already-valid `"domain:x"` and `"legacy_default"` pass through unchanged
  - Implement `resolve_domain_filter(scope: DomainScope, model) -> BinaryExpression | None`: `"all"` → `None`, `"domain:{id}"` → `model.domain == id`, `"legacy_default"` → `or_(model.domain == "default", model.domain.is_(None))`
  - No external dependencies beyond SQLAlchemy (already in use)

- [x] **TASK-002** Write unit tests for `backend/domain_scope.py`
  - File: `backend/tests/test_domain_scope.py`
  - Cover all `is_valid_scope` scenarios: valid strings, invalid strings
  - Cover all `parse_scope` scenarios: None, empty string, `"default"`, `"all"`, bare ID, already-valid scope
  - Cover all `resolve_domain_filter` scenarios: `"all"` returns None, `"domain:science"` returns equality filter, `"legacy_default"` returns OR filter
  - Test that resolver does not import or touch tenant_access.py

### Phase 2 — Backend router migration

- [x] **TASK-003** Migrate `backend/routers/analytics.py`
  - Remove inline `if domain_id == "all":` / `elif domain_id == "default":` blocks
  - Call `parse_scope(domain_id)` on route entry to normalize the raw path param
  - Apply `resolve_domain_filter(scope, RawEntity)` to build the WHERE clause
  - Verify: no `== "all"`, `== "default"`, or bare `.domain.is_(None)` patterns remain

- [x] **TASK-004** Migrate `backend/routers/entities.py`
  - Same pattern as TASK-003
  - All entity list endpoints and enrich endpoints use `resolve_domain_filter`

- [x] **TASK-005** Migrate `backend/routers/ai_rag.py`
  - No inline domain scope patterns found — already clean.

- [x] **TASK-006** Migrate `backend/routers/domains.py`
  - No inline domain scope patterns found — already clean.

- [x] **TASK-007** Migrate `backend/olap.py`
  - No inline domain scope patterns found — already clean.

- [x] **TASK-008** Migrate `backend/routers/reports.py`
  - No SQL-level domain comparisons found — Field default is a data value, not scope logic.

- [x] **TASK-009** Migrate `backend/enrichment_worker.py`
  - Replaced `if domain_id == "default":` block with `resolve_domain_filter(parse_scope(...))`.

- [x] **TASK-010** Update `backend/tenant_access.py`
  - Delegate domain filtering to `resolve_domain_filter` where applicable
  - Tenant/org scoping logic remains in `tenant_access.py` — do not merge concerns

### Phase 3 — Frontend contract

- [x] **TASK-011** Update `frontend/app/contexts/DomainContext.tsx`
  - Export `type DomainScope = string`
  - Type `activeDomainId` as `DomainScope` in `DomainContextType`
  - Export `isAllScope(scope: DomainScope): boolean`
  - Export `isLegacyScope(scope: DomainScope): boolean`
  - Export `domainIdFromScope(scope: DomainScope): string | null`

- [x] **TASK-012** Update domain selector to emit canonical scope values
  - Updated Header.tsx to import and use `isAllScope`, `domainIdFromScope`
  - Replaced raw `=== "all"` and `=== "default"` comparisons with helper calls
  - Selector "all" option emits `"all"`, domain options emit `domain.id` (backend normalizes via parse_scope)

- [x] **TASK-013** Migrate `frontend/app/analytics/dashboard/page.tsx`
  - Replaced `dashboardDomainId !== "all"` with `!isAllScope(dashboardDomainId)`

- [x] **TASK-014** Migrate `frontend/app/analytics/topics/page.tsx`
  - No raw domain scope comparisons found — already clean.

- [x] **TASK-015** Migrate `frontend/app/analytics/olap/page.tsx`
  - No raw domain scope comparisons found — already clean.

- [x] **TASK-016** Migrate remaining frontend pages under `frontend/app/`
  - Updated `analytics/graph/page.tsx`: replaced `!== "all"` with `!isAllScope()`
  - Other pages had only data-fallback `|| "default"` / `?? "default"` patterns (not scope comparisons)

### Phase 4 — CI lint guard

- [x] **TASK-017** Add lint check script `scripts/lint_domain_scope.py`
  - Scans all `*.py` files under `backend/routers/` and `backend/enrichment_worker.py`
  - Fails (exit 1) if any file contains `== "default"`, `== "all"`, or `.domain.is_(` in scope context
  - Passes with zero violations on fully migrated codebase (51 files scanned)

- [x] **TASK-018** Wire lint check into CI
  - Added `domain-scope-lint` job to `.github/workflows/lint.yml`
  - Job runs `python scripts/lint_domain_scope.py` and fails the build on any violation

### Phase 5 — Verification

- [x] **TASK-019** Run full backend test suite
  - 1896 passed, 7 skipped, 2 pre-existing failures in test_enrichment_worker.py (confirmed pre-migration)
  - 24 new domain_scope unit tests all passing
  - Zero regressions introduced

- [x] **TASK-020** Run frontend type check
  - `npx tsc --noEmit` — zero type errors

- [x] **TASK-021** Manual smoke test
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
