## Context

Every scope-aware endpoint in UKIP currently contains inline domain filtering logic such as:

```python
if domain_id == "all":
    pass  # no filter
elif domain_id == "default":
    query = query.filter(or_(RawEntity.domain == "default", RawEntity.domain.is_(None)))
else:
    query = query.filter(RawEntity.domain == domain_id)
```

This pattern is duplicated across at least 12 backend files and mirrors a parallel set of `=== "all"` / `=== "default"` comparisons in the frontend. Each duplication is a regression surface. The `legacy_default` case (historical records stored with `domain = "default"` or `domain = NULL`) is handled inconsistently — some endpoints include it in aggregates, others exclude it silently.

## Goals / Non-Goals

**Goals**
- One canonical function that converts a `DomainScope` string into a SQLAlchemy filter expression
- One canonical TypeScript type that all frontend pages consume for scope comparison
- Zero inline `== "all"` / `== "default"` / `is_(None)` domain branches remaining in router code
- No change to stored data — `domain` column values are unchanged

**Non-Goals**
- Multi-tenancy isolation (handled separately by `tenant_access.py`)
- UI changes beyond `DomainContext` type export
- New API surface — this is a refactor, not a new feature

## Decisions

### 1. `DomainScope` as a plain string alias, not an enum

**Decision**: `DomainScope = str` with a validator function, not a Python `Enum`.

**Rationale**: FastAPI query params and Pydantic models already handle `str`. An `Enum` would require changes at every API boundary (serialization, OpenAPI schema). A plain string with a validator (`is_valid_scope(s)`) is simpler and equally safe.

**Alternative considered**: `Literal["all", "legacy_default"] | str` — rejected because `domain:{id}` requires a dynamic prefix, making `Literal` incomplete.

### 2. Resolver returns a SQLAlchemy `BinaryExpression | None`

**Decision**: `resolve_domain_filter(scope, model)` returns `None` for `all` (caller adds no filter) and a `BinaryExpression` for the other two cases.

**Rationale**: Returning `None` for `all` avoids generating a tautological `WHERE 1=1` clause and keeps query plans clean.

### 3. Frontend `DomainScope` type is a branded string

**Decision**: `type DomainScope = string` exported from `DomainContext`; helpers `isAllScope(s)`, `isLegacyScope(s)`, `domainIdFromScope(s)` replace raw equality comparisons.

**Rationale**: TypeScript brands add friction without adding expressiveness here since the values cross API boundaries as plain JSON strings. Helper functions give the same safety with less ceremony.

### 4. Migration is incremental — router by router

**Decision**: Replace inline filtering in routers one file at a time; each PR is independently testable.

**Rationale**: A single giant refactor PR is hard to review and risks introducing regressions across the entire system simultaneously. Incremental replacement lets the test suite catch regressions per-module.

## Risks / Trade-offs

- **[Risk] Missed call site** — a router that still uses raw `"default"` after the contract exists creates a silent inconsistency. → Mitigation: grep-based CI lint rule that fails if `== "default"` or `== "all"` appears in router files after the contract is deployed.
- **[Risk] `legacy_default` scope excludes new records with domain `"default"`** — if new ingestion still sets `domain = "default"`, those records fall under `legacy_default` rather than a concrete domain. → Mitigation: ingestion wizard already prompts for domain selection; document that `"default"` domain assignment for new records is deprecated.
- **[Risk] Frontend scope mismatch** — a component that reads `activeDomainId` directly instead of the typed scope helper stays broken. → Mitigation: TypeScript helper functions make the correct path obvious; existing components are updated as part of this change.

## Migration Plan

1. Create `backend/domain_scope.py` with `DomainScope` alias, `resolve_domain_filter()`, `parse_scope()`, `is_valid_scope()`.
2. Update `backend/tenant_access.py` helpers to delegate to `resolve_domain_filter` where applicable.
3. Migrate routers in order: `analytics.py` → `entities.py` → `ai_rag.py` → `domains.py` → `olap.py` → `reports.py` → remaining files.
4. Export `DomainScope` type and scope helpers from `DomainContext.tsx`.
5. Update frontend pages to use helpers instead of raw string comparisons.
6. Add CI lint check: `grep -r '"all"\|"default"' backend/routers/ --include="*.py"` must return zero matches for domain-comparison patterns after migration.
7. Run full test suite; add missing coverage for `legacy_default` filter behavior.
