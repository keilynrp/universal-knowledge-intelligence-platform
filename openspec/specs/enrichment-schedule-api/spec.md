# enrichment-schedule-api Specification

## Purpose
TBD - created by archiving change enrichment-scheduler. Update Purpose after archive.
## Requirements
### Requirement: GET /enrichment/schedule returns global scheduler state
The system SHALL expose `GET /enrichment/schedule` (auth required, any role) returning the scheduler's current state: `enabled`, `interval_seconds`, `last_run_at` (ISO timestamp or null), `next_run_at` (estimated), `domains_monitored` (count of enabled policies), `total_queued_last_run` (sum of queued_count across all domains in the last scheduler cycle).

#### Scenario: Returns scheduler state when running
- **WHEN** an authenticated user calls `GET /enrichment/schedule`
- **THEN** the response includes `enabled: true`, `interval_seconds: 60`, and current timing fields

#### Scenario: Requires authentication
- **WHEN** an unauthenticated request is made to `GET /enrichment/schedule`
- **THEN** the system returns HTTP 401

### Requirement: GET /enrichment/schedule/{domain_id} returns per-domain staleness report
The system SHALL expose `GET /enrichment/schedule/{domain_id}` (auth required, any role) returning: `domain_id`, `policy` (the DomainEnrichmentPolicy fields), `current_enrichment_pct` (float), `total_entities` (int), `enriched_entities` (int), `stale_entities` (int — count of `none` + `failed`), `last_run` (most recent `enrichment_scheduler_runs` row or null), `is_stale` (bool).

#### Scenario: Domain with policy returns full report
- **WHEN** an authenticated user requests `GET /enrichment/schedule/science`
- **THEN** the response includes live entity counts and the current policy

#### Scenario: Domain with no explicit policy uses defaults
- **WHEN** requesting a domain that has no `DomainEnrichmentPolicy` row
- **THEN** the response returns default policy values with live entity counts

#### Scenario: Unknown domain returns 404
- **WHEN** requesting a domain_id that does not exist in the schema registry
- **THEN** the system returns HTTP 404

### Requirement: POST /enrichment/schedule/{domain_id}/trigger manually runs the scheduler for one domain
The system SHALL expose `POST /enrichment/schedule/{domain_id}/trigger` (admin+ role) that immediately executes the staleness check and re-queue logic for the specified domain, respecting the existing policy, and records the run with `triggered_by = 'manual'`.

#### Scenario: Manual trigger re-queues stale entities
- **WHEN** an admin POSTs to `/enrichment/schedule/science/trigger` and science has stale entities
- **THEN** entities are re-queued, a run row is written, and the response returns `{ domain_id, queued_count, triggered_by: "manual" }`

#### Scenario: Manual trigger on healthy domain returns queued_count 0
- **WHEN** the domain is already fully enriched
- **THEN** the response returns `{ queued_count: 0 }` with HTTP 200

#### Scenario: Requires admin role
- **WHEN** a viewer or editor calls `POST /enrichment/schedule/{domain_id}/trigger`
- **THEN** the system returns HTTP 403

### Requirement: PUT /enrichment/schedule/{domain_id}/policy updates the domain enrichment policy
The system SHALL expose `PUT /enrichment/schedule/{domain_id}/policy` (admin+ role) that creates or updates the `DomainEnrichmentPolicy` for the given domain. Accepted fields: `enabled`, `min_enrichment_pct` (0.0–100.0), `max_budget_per_run` (1–10000), `staleness_threshold_days` (1–3650).

#### Scenario: Creates new policy when none exists
- **WHEN** an admin PUTs a policy for a domain that has no existing row
- **THEN** a new `DomainEnrichmentPolicy` row is created and returned with HTTP 201

#### Scenario: Updates existing policy
- **WHEN** an admin PUTs a policy for a domain that already has a row
- **THEN** the existing row is updated and returned with HTTP 200

#### Scenario: Disabling policy stops auto re-queuing
- **WHEN** an admin sets `enabled: false` via PUT
- **THEN** the scheduler no longer re-queues entities for that domain on subsequent runs

#### Scenario: Invalid min_enrichment_pct is rejected
- **WHEN** the request body contains `min_enrichment_pct: 150`
- **THEN** the system returns HTTP 422

#### Scenario: Requires admin role
- **WHEN** a viewer or editor calls `PUT /enrichment/schedule/{domain_id}/policy`
- **THEN** the system returns HTTP 403

### Requirement: GET /enrichment/schedule/{domain_id}/runs returns run history
The system SHALL expose `GET /enrichment/schedule/{domain_id}/runs` (auth required, any role) returning the 20 most recent `enrichment_scheduler_runs` rows for the domain, ordered by `started_at` descending, with optional `limit` query param (1–100).

#### Scenario: Returns run history for a domain
- **WHEN** an authenticated user requests run history for a domain with past runs
- **THEN** the response returns a list of run records ordered newest-first

#### Scenario: Empty history returns empty list
- **WHEN** the domain has no run records
- **THEN** the response returns `{ runs: [] }` with HTTP 200

