## ADDED Requirements

### Requirement: DomainScope type is exported from DomainContext
The frontend SHALL export a `DomainScope` type alias from `frontend/app/contexts/DomainContext.tsx`. All pages and components that consume the active domain scope SHALL use this type instead of raw `string` or ad-hoc equality comparisons.

The exported type SHALL be:
```typescript
export type DomainScope = string;
```

No other module SHALL define its own local domain scope type or perform inline `=== "all"` / `=== "default"` comparisons after migration.

#### Scenario: DomainScope type is importable
- **WHEN** a page imports `DomainScope` from `DomainContext`
- **THEN** TypeScript resolves the import without error

### Requirement: Three scope helper functions replace raw string comparisons
The frontend SHALL export three pure helper functions from `DomainContext`:

```typescript
export function isAllScope(scope: DomainScope): boolean
export function isLegacyScope(scope: DomainScope): boolean
export function domainIdFromScope(scope: DomainScope): string | null
```

Behaviour:
- `isAllScope("all")` → `true`; any other value → `false`
- `isLegacyScope("legacy_default")` → `true`; any other value → `false`
- `domainIdFromScope("domain:science")` → `"science"`
- `domainIdFromScope("all")` → `null`
- `domainIdFromScope("legacy_default")` → `null`

#### Scenario: isAllScope identifies the aggregate scope
- **WHEN** `isAllScope("all")` is called
- **THEN** it returns `true`
- **WHEN** `isAllScope("domain:science")` is called
- **THEN** it returns `false`

#### Scenario: isLegacyScope identifies legacy_default
- **WHEN** `isLegacyScope("legacy_default")` is called
- **THEN** it returns `true`
- **WHEN** `isLegacyScope("all")` is called
- **THEN** it returns `false`

#### Scenario: domainIdFromScope extracts the concrete domain
- **WHEN** `domainIdFromScope("domain:healthcare")` is called
- **THEN** it returns `"healthcare"`
- **WHEN** `domainIdFromScope("all")` is called
- **THEN** it returns `null`

### Requirement: DomainContext emits DomainScope, not raw string
The `DomainContextType` interface SHALL type `activeDomainId` as `DomainScope`. The setter `setActiveDomainId` SHALL accept `DomainScope`.

No page or component SHALL receive `activeDomainId` typed as plain `string` after migration — it SHALL always carry the `DomainScope` alias so TypeScript guides callers toward the helper functions.

#### Scenario: activeDomainId is typed as DomainScope
- **WHEN** a component destructures `{ activeDomainId }` from `useDomain()`
- **THEN** TypeScript infers `activeDomainId: DomainScope`
- **AND** direct `=== "all"` comparisons produce no TypeScript error but are flagged in code review as violations of this contract (use `isAllScope()` instead)

### Requirement: Pages use helper functions for all scope-conditional rendering
Every frontend page that previously contained `activeDomainId === "all"` or `activeDomainId === "default"` SHALL call the corresponding helper function instead.

The inline patterns `=== "all"`, `=== "default"`, `=== "legacy_default"` used for scope branching SHALL NOT appear in page or component files under `frontend/app/` after migration.

#### Scenario: Analytics dashboard renders correctly for all-scope
- **WHEN** `activeDomainId` is `"all"` and the analytics dashboard renders
- **THEN** the page calls `isAllScope(activeDomainId)` to determine aggregate mode
- **AND** no raw `=== "all"` comparison is present in `analytics/dashboard/page.tsx`

#### Scenario: OLAP page passes scope to backend correctly
- **WHEN** `activeDomainId` is `"domain:science"` and the OLAP page fires its request
- **THEN** it calls `domainIdFromScope(activeDomainId)` to obtain `"science"` for the API path
- **AND** no raw string slicing (`replace("domain:", "")`) appears in the page

#### Scenario: Legacy scope passed to API
- **WHEN** `activeDomainId` is `"legacy_default"` and any scope-aware page fires its API request
- **THEN** the raw `"legacy_default"` string is sent to the backend as-is
- **AND** `isLegacyScope(activeDomainId)` returns `true` when checked in that page

### Requirement: Domain selector emits canonical DomainScope values
The domain selector component SHALL only produce values that are valid `DomainScope` strings:
- `"all"` for the aggregate option
- `"legacy_default"` for the historical-default option (when exposed)
- `"domain:{id}"` for each concrete domain

The selector SHALL NOT emit the bare strings `"default"` or `""` as user-selectable scope values.

#### Scenario: Selector emits prefixed domain ID
- **WHEN** the user selects the domain with id `"science"` from the dropdown
- **THEN** `setActiveDomainId` is called with `"domain:science"`
- **AND** the context value for `activeDomainId` becomes `"domain:science"`

#### Scenario: Selector emits "all" for aggregate option
- **WHEN** the user selects the "All domains" option
- **THEN** `setActiveDomainId` is called with `"all"`
