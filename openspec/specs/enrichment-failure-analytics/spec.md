# enrichment-failure-analytics Specification

## Purpose
TBD - created by archiving change enrichment-quality-signals. Update Purpose after archive.
## Requirements
### Requirement: enrichment_failure_reason stored on failed entities
The system SHALL store a machine-readable failure reason on `raw_entities.enrichment_failure_reason` (nullable VARCHAR 30) whenever `enrichment_status` transitions to `failed`. Valid values: `no_match`, `api_error`, `rate_limited`, `circuit_open`, `timeout`, `all_sources_failed`.

#### Scenario: Worker writes failure reason on transition to failed
- **WHEN** the enrichment worker sets `enrichment_status = 'failed'` for an entity
- **THEN** `enrichment_failure_reason` is set to the appropriate category string

#### Scenario: no_match written when all sources return empty
- **WHEN** every enabled source is queried and none returns a usable record
- **THEN** `enrichment_failure_reason = 'no_match'`

#### Scenario: circuit_open written when breaker prevents call
- **WHEN** a source's circuit breaker is OPEN and the call is skipped
- **THEN** `enrichment_failure_reason = 'circuit_open'` (if all sources were open)

#### Scenario: Pre-existing failed rows retain NULL reason
- **WHEN** an entity's `enrichment_failure_reason` is NULL (pre-migration row)
- **THEN** the system treats it as "unknown" and does not error

### Requirement: GET /enrichment/sources/stats returns aggregate quality signals
The system SHALL expose `GET /enrichment/sources/stats` (auth required, any role) returning per-domain and per-source aggregates: total entities, enriched count, failed count, failure reason breakdown, and dominant source (most common `enrichment_source` value among completed entities).

#### Scenario: Stats aggregated per domain
- **WHEN** an authenticated user calls `GET /enrichment/sources/stats`
- **THEN** the response contains one entry per domain with `total`, `enriched`, `failed`, `failure_reasons` (map of reason→count), and `dominant_source`

#### Scenario: Stats filterable by domain_id query param
- **WHEN** the user calls `GET /enrichment/sources/stats?domain_id=science`
- **THEN** only the science domain's stats are returned

#### Scenario: Empty domain returns zero counts
- **WHEN** a domain has no entities
- **THEN** the response entry shows `total: 0, enriched: 0, failed: 0`

#### Scenario: Requires authentication
- **WHEN** an unauthenticated request is made to `GET /enrichment/sources/stats`
- **THEN** the system returns HTTP 401

### Requirement: Composite DB index on enrichment_source and enrichment_status
The system SHALL add a composite index on `raw_entities(enrichment_source, enrichment_status)` to support efficient aggregation queries.

#### Scenario: Index exists after migration
- **WHEN** the application starts after the migration runs
- **THEN** the composite index `ix_re_source_status` exists on `raw_entities`

