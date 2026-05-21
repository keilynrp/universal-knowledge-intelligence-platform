## ADDED Requirements

### Requirement: DomainScope type and legal values are defined in one module
The system SHALL define `DomainScope` as a string alias in `backend/domain_scope.py`. The three legal scope values SHALL be:
- `"all"` — aggregate over all records regardless of domain
- `"domain:{id}"` — records where `domain == {id}` (exact match, case-sensitive)
- `"legacy_default"` — records where `domain == "default"` OR `domain IS NULL`

No other module SHALL define or validate domain scope strings independently.

#### Scenario: Valid scope strings
- **WHEN** `is_valid_scope("all")` is called
- **THEN** it returns `True`
- **WHEN** `is_valid_scope("domain:science")` is called
- **THEN** it returns `True`
- **WHEN** `is_valid_scope("legacy_default")` is called
- **THEN** it returns `True`

#### Scenario: Invalid scope strings are rejected
- **WHEN** `is_valid_scope("default")` is called
- **THEN** it returns `False`
- **WHEN** `is_valid_scope("")` is called
- **THEN** it returns `False`
- **WHEN** `is_valid_scope("science")` is called (bare domain ID without prefix)
- **THEN** it returns `False`

### Requirement: parse_scope converts legacy inputs to DomainScope
The system SHALL provide `parse_scope(raw: str) -> DomainScope` that converts legacy raw domain strings into valid scope values. Specifically:
- `"all"` → `"all"`
- `""` or `None` → `"all"`
- `"default"` → `"legacy_default"`
- Any other non-empty string `s` → `"domain:{s}"`

#### Scenario: Legacy "default" is normalized
- **WHEN** `parse_scope("default")` is called
- **THEN** it returns `"legacy_default"`

#### Scenario: Empty string becomes all
- **WHEN** `parse_scope("")` is called
- **THEN** it returns `"all"`

#### Scenario: Bare domain ID is prefixed
- **WHEN** `parse_scope("science")` is called
- **THEN** it returns `"domain:science"`

#### Scenario: Already-valid scope passes through
- **WHEN** `parse_scope("domain:science")` is called
- **THEN** it returns `"domain:science"`

### Requirement: resolve_domain_filter returns a SQLAlchemy expression or None
The system SHALL provide `resolve_domain_filter(scope: DomainScope, model) -> BinaryExpression | None` where:
- `"all"` → returns `None` (caller adds no WHERE clause)
- `"domain:{id}"` → returns `model.domain == id`
- `"legacy_default"` → returns `or_(model.domain == "default", model.domain.is_(None))`

The resolver SHALL NOT apply any tenant/org scoping — that remains in `tenant_access.py`.

#### Scenario: all scope produces no filter
- **WHEN** `resolve_domain_filter("all", RawEntity)` is called
- **THEN** it returns `None`
- **AND** the caller's query has no domain WHERE clause

#### Scenario: concrete domain scope produces equality filter
- **WHEN** `resolve_domain_filter("domain:science", RawEntity)` is called
- **THEN** it returns an expression equivalent to `RawEntity.domain == "science"`

#### Scenario: legacy_default scope matches default and NULL
- **WHEN** `resolve_domain_filter("legacy_default", RawEntity)` is called
- **THEN** it returns an expression matching rows where `domain = 'default'` OR `domain IS NULL`

### Requirement: Routers use resolve_domain_filter exclusively for domain filtering
Every backend router that previously contained inline domain comparisons SHALL call `resolve_domain_filter` instead. The inline patterns `if domain_id == "all"`, `if domain_id == "default"`, and `.filter(RawEntity.domain.is_(None))` used for domain scoping SHALL NOT appear in router files after migration.

#### Scenario: Analytics endpoint uses resolver
- **WHEN** `GET /analyzers/topics/{domain_id}` is called with `domain_id = "legacy_default"`
- **THEN** the query matches records with `domain = "default"` OR `domain IS NULL`
- **AND** no inline `== "default"` comparison exists in `analytics.py`

#### Scenario: OLAP endpoint uses resolver
- **WHEN** `GET /cube/dimensions/{domain_id}` is called with `domain_id = "domain:healthcare"`
- **THEN** the query filters to `domain = "healthcare"` only

### Requirement: CI lint check enforces the contract
The project SHALL include a lint check that fails if any file under `backend/routers/` contains domain scope comparison patterns (`== "default"`, `== "all"`, `.domain.is_(None)` used for scope purposes) after the migration is complete.

#### Scenario: Lint passes after migration
- **WHEN** the lint check runs on a fully migrated codebase
- **THEN** it reports zero violations

#### Scenario: Lint catches a new violation
- **WHEN** a developer adds `if domain_id == "default":` to a router file
- **THEN** the lint check fails with a message identifying the file and line
