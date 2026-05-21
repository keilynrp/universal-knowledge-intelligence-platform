# enrichment-scheduler-service Specification

## Purpose
TBD - created by archiving change enrichment-scheduler. Update Purpose after archive.
## Requirements
### Requirement: Scheduler detects stale domains on a configurable interval
The system SHALL run an async background loop that wakes every 60 seconds, iterates over all active `DomainEnrichmentPolicy` rows where `enabled = true`, and re-queues eligible entities in domains whose enrichment percentage falls below `min_enrichment_pct`.

#### Scenario: Stale domain triggers re-queue
- **WHEN** a domain has `count_enriched / count_total < min_enrichment_pct` AND the policy is enabled
- **THEN** the scheduler sets up to `max_budget_per_run` entities with `enrichment_status IN ('none', 'failed')` to `pending`

#### Scenario: Healthy domain is skipped
- **WHEN** a domain has `count_enriched / count_total >= min_enrichment_pct`
- **THEN** the scheduler does not modify any entities in that domain

#### Scenario: Empty domain is skipped
- **WHEN** `count_total(db, scope)` returns 0 for a domain
- **THEN** the scheduler skips that domain without writing any rows

### Requirement: DomainEnrichmentPolicy model persists per-domain scheduler configuration
The system SHALL maintain a `domain_enrichment_policies` table with the following fields: `domain_id` (string, unique), `enabled` (bool, default true), `min_enrichment_pct` (float 0–100, default 80.0), `max_budget_per_run` (int, default 100), `staleness_threshold_days` (int, default 30), `created_at`, `updated_at`.

#### Scenario: Default policy applies when no policy row exists
- **WHEN** the scheduler encounters a domain with no `DomainEnrichmentPolicy` row
- **THEN** it uses the system defaults (enabled=true, min_enrichment_pct=80, max_budget_per_run=100)

#### Scenario: Disabled policy skips domain
- **WHEN** a domain's policy has `enabled = false`
- **THEN** the scheduler performs no re-queuing for that domain

### Requirement: Scheduler respects max_budget_per_run cap
The system SHALL NOT re-queue more than `max_budget_per_run` entities per domain per scheduler run, even if more stale entities exist.

#### Scenario: Budget cap limits re-queue
- **WHEN** 500 entities are stale but `max_budget_per_run = 100`
- **THEN** exactly 100 entities are set to `pending` in that run

#### Scenario: Fewer stale than budget re-queues all
- **WHEN** 30 entities are stale and `max_budget_per_run = 100`
- **THEN** all 30 entities are set to `pending`

### Requirement: Scheduler only re-queues none/failed entities (not completed/processing/pending)
The scheduler SHALL only set `enrichment_status = 'pending'` for entities currently in `none` or `failed` state. It SHALL NOT touch entities that are already `pending`, `processing`, or `completed`.

#### Scenario: Completed entities are never re-queued automatically
- **WHEN** a domain has all entities with `enrichment_status = 'completed'`
- **THEN** the scheduler does not re-queue any entities even if new un-enriched entities are absent

#### Scenario: Pending and processing entities are not double-queued
- **WHEN** some entities are already `pending` or `processing`
- **THEN** the scheduler does not modify those entities' status

### Requirement: Scheduler logs each run to enrichment_scheduler_runs table
The system SHALL write one row per domain per scheduler run to `enrichment_scheduler_runs`: `domain_id`, `triggered_by` ('scheduler' or 'manual'), `queued_count`, `started_at`, `finished_at`, `notes` (text, nullable).

#### Scenario: Successful run is recorded
- **WHEN** the scheduler re-queues N entities for a domain
- **THEN** a run row is written with `queued_count = N`, `triggered_by = 'scheduler'`, and accurate timestamps

#### Scenario: Zero-queue run is still recorded
- **WHEN** the scheduler determines a domain is healthy and queues nothing
- **THEN** a run row is written with `queued_count = 0`

### Requirement: Scheduler startup is wired into the FastAPI lifespan
The system SHALL start the enrichment scheduler as an `asyncio` task in the `main.py` lifespan block, immediately after the enrichment worker task. It SHALL be cancellable on application shutdown.

#### Scenario: Scheduler starts with the application
- **WHEN** the FastAPI application starts
- **THEN** the scheduler loop begins and logs "Enrichment scheduler started" at INFO level

#### Scenario: Scheduler honours UKIP_SKIP_STARTUP_SIDE_EFFECTS
- **WHEN** `UKIP_SKIP_STARTUP_SIDE_EFFECTS=1` is set (test environment)
- **THEN** the scheduler task is NOT started

