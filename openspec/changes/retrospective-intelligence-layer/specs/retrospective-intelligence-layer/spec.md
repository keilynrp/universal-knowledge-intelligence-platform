# retrospective-intelligence-layer Specification

## Purpose

Define UKIP's internal bounded context for governed retrospective analysis over
historical entities, metrics, derived signals, workflow decisions, and data
quality.

## Requirements

### Requirement: Historical events use a governed append-only envelope

The system SHALL persist retrospective domain events using an append-only
envelope with `event_id`, `event_type`, `schema_version`, `org_id`,
`domain_object_type`, `domain_object_id`, `recorded_at`, `occurred_at`,
`source`, `actor_type`, `actor_id`, `correlation_id`, `idempotency_key`,
`payload`, and `lineage`.

#### Scenario: Event is recorded with tenant scope

- **WHEN** a journal metric recomputation emits a retrospective event
- **THEN** the event includes the caller's resolved `org_id`
- **AND** retrospective readers only return it to authorized users in that scope

#### Scenario: Duplicate event is suppressed

- **WHEN** the same writer retries with the same `idempotency_key`
- **THEN** the system stores one event and returns the existing event identity

#### Scenario: Event mutation is rejected

- **WHEN** application code attempts to update a stored event payload
- **THEN** the system rejects the mutation unless it is an approved retention
  deletion operation

### Requirement: Snapshots support point-in-time reconstruction

The system SHALL persist snapshots for selected entities, relationships,
metrics, and derived signals using `snapshot_id`, `snapshot_type`,
`schema_version`, `org_id`, `subject_type`, `subject_id`, `valid_at`,
`recorded_at`, `payload`, and `lineage`.

#### Scenario: Current state can be compared with a prior snapshot

- **WHEN** a user requests a journal's current NIF state compared with a prior
  `valid_at` timestamp
- **THEN** the system returns the current values, the prior snapshot values, and
  which values changed

#### Scenario: Missing snapshot is explicit

- **WHEN** no snapshot exists at or before the requested timestamp
- **THEN** the system returns a typed missing-history result instead of falling
  back silently to current operational state

### Requirement: Retrospective reads do not mutate operational state

The retrospective query service SHALL read historical events, snapshots, and
analytical marts without writing to operational entity, enrichment, authority,
or journal metric tables.

#### Scenario: Historical comparison is read-only

- **WHEN** a user runs a current-vs-prior comparison
- **THEN** no operational entity or metric rows are modified

### Requirement: Retrospective values preserve provenance and null semantics

The system SHALL preserve whether values are source-provided, inferred,
normalized, unknown, not applicable, deleted, or unavailable at the requested
time.

#### Scenario: Unknown differs from unavailable

- **WHEN** a historical snapshot contains an explicitly unknown field value
- **THEN** the API marks it as `unknown`
- **AND** does not present it as missing history

### Requirement: Historical analytical marts support trends and cohorts

The system SHALL derive bounded analytical marts for time-series, cohort,
coverage, drift, and backtesting analysis from historical events and snapshots.

#### Scenario: Cohort analysis uses stable membership

- **WHEN** a user analyzes journals first enriched in May 2026
- **THEN** cohort membership is based on historical event timestamps
- **AND** later changes to current journal state do not change membership
