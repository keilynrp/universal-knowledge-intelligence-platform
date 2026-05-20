# entity-query-service Specification

## Purpose
TBD - created by archiving change read-model. Update Purpose after archive.
## Requirements
### Requirement: entity_base_q factory always applies the three mandatory guards
The system SHALL provide `entity_base_q(db, scope, org_id=None)` in `backend/services/entity_query.py`. Every call to this function MUST apply, in order: (1) exclude `source = 'graph_materializer'`, (2) apply `resolve_domain_filter(parse_scope(scope), RawEntity)`, (3) apply `scope_query_to_org(org_id)` when `org_id` is not None. The returned object SHALL be a SQLAlchemy Query that callers can chain with additional `.filter()`, `.limit()`, and `.all()` calls.

#### Scenario: All three guards applied when org_id is provided
- **WHEN** `entity_base_q(db, "domain:science", org_id=42)` is called
- **THEN** the returned query MUST filter out `source = 'graph_materializer'` rows, restrict to the `science` domain, and restrict to `org_id = 42`

#### Scenario: Source exclusion and domain filter applied when org_id is None
- **WHEN** `entity_base_q(db, "all", org_id=None)` is called
- **THEN** the returned query MUST filter out `source = 'graph_materializer'` rows and NOT apply any org restriction

#### Scenario: Legacy scope string handled transparently
- **WHEN** `entity_base_q(db, "legacy_default", org_id=None)` is called
- **THEN** `parse_scope` normalises the scope and the query runs without error

---

### Requirement: count_total returns the scoped non-derived entity count
The system SHALL provide `count_total(db, scope, org_id=None) -> int` that returns `entity_base_q(db, scope, org_id).count()`.

#### Scenario: Empty domain returns zero
- **WHEN** `count_total(db, "domain:empty_workspace", org_id=None)` is called and the domain has no entities
- **THEN** the return value SHALL be `0`

#### Scenario: Count excludes graph_materializer rows
- **WHEN** the database contains one user-uploaded entity and one `source='graph_materializer'` entity in the same domain
- **THEN** `count_total` SHALL return `1`

---

### Requirement: count_by_status returns entities filtered by enrichment_status
The system SHALL provide `count_by_status(db, scope, status, org_id=None) -> int` that returns the count of entities matching a given `EnrichmentStatus` value within the scoped base query.

#### Scenario: Counts only completed entities
- **WHEN** the domain has 3 completed and 2 pending entities
- **THEN** `count_by_status(db, scope, EnrichmentStatus.completed)` SHALL return `3`

---

### Requirement: count_enriched is a convenience wrapper for completed status
The system SHALL provide `count_enriched(db, scope, org_id=None) -> int` equivalent to `count_by_status(db, scope, EnrichmentStatus.completed, org_id)`.

#### Scenario: Equivalent to count_by_status with completed
- **WHEN** `count_enriched(db, scope)` and `count_by_status(db, scope, EnrichmentStatus.completed)` are called on the same database
- **THEN** both SHALL return the same value

---

### Requirement: derived_status_service uses entity_base_q exclusively
All six per-resource compute functions in `DerivedStatusService` SHALL use `entity_base_q` as their query base. No inline `db.query(models.RawEntity).filter(models.RawEntity.source != "graph_materializer")` SHALL remain in `derived_status_service.py`.

#### Scenario: No inline source guard in derived_status_service
- **WHEN** `derived_status_service.py` is read
- **THEN** the string `"graph_materializer"` SHALL NOT appear in any inline query; it SHALL appear only inside `entity_query.py`

---

### Requirement: entity_query module is importable with no side effects
Importing `backend.services.entity_query` SHALL not connect to the database, start threads, or register anything globally.

#### Scenario: Safe import at module level
- **WHEN** `from backend.services.entity_query import entity_base_q` is executed
- **THEN** no database connection is opened and no side effects occur

