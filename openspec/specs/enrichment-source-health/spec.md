# enrichment-source-health Specification

## Purpose
TBD - created by archiving change enrichment-quality-signals. Update Purpose after archive.
## Requirements
### Requirement: GET /enrichment/sources/health returns real-time source health
The system SHALL expose `GET /enrichment/sources/health` (auth required, any role) returning the current state of each enrichment source's circuit breaker and in-process counters: `name`, `state` (CLOSED/OPEN/HALF_OPEN), `failure_count`, `success_count`, `consecutive_failures`.

#### Scenario: Returns health for all sources
- **WHEN** an authenticated user calls `GET /enrichment/sources/health`
- **THEN** the response contains one entry per registered enrichment source with `state`, `failure_count`, `success_count`, and `consecutive_failures`

#### Scenario: Open circuit is flagged
- **WHEN** a source's circuit breaker is in OPEN state
- **THEN** that source's entry shows `state: "OPEN"` and `failure_count >= failure_threshold`

#### Scenario: Requires authentication
- **WHEN** an unauthenticated request is made to `GET /enrichment/sources/health`
- **THEN** the system returns HTTP 401

### Requirement: CircuitBreaker tracks success_count
The `CircuitBreaker` class SHALL maintain a `success_count` integer counter that increments each time a protected call completes without raising an exception. The counter resets to 0 when the circuit transitions from HALF_OPEN to CLOSED (successful probe).

#### Scenario: Success increments counter
- **WHEN** a protected call completes successfully (no exception)
- **THEN** `circuit.success_count` increases by 1

#### Scenario: Counter is accessible as a property
- **WHEN** code reads `circuit.success_count`
- **THEN** it returns the current accumulated success count as an integer

### Requirement: Enrichment source health card on analytics dashboard
The analytics dashboard SHALL display an "Enrichment Sources" card below the scheduler card showing each source's circuit state badge (green CLOSED, red OPEN, amber HALF_OPEN) and failure/success counts.

#### Scenario: CLOSED source shows green badge
- **WHEN** a source's circuit is CLOSED
- **THEN** the card row shows a green "Healthy" badge and the success count

#### Scenario: OPEN source shows red badge with failure count
- **WHEN** a source's circuit is OPEN
- **THEN** the card row shows a red "Circuit Open" badge, the failure count, and an estimated recovery time

#### Scenario: HALF_OPEN source shows amber badge
- **WHEN** a source's circuit is HALF_OPEN (probe in flight)
- **THEN** the card row shows an amber "Probing" badge

