## ADDED Requirements

### Requirement: Infrastructure decisions support production trust
UKIP SHALL evaluate infrastructure and operations decisions against reliability, observability, deployment safety, data integrity, and recovery.

#### Scenario: Startup or migration behavior changes
- **WHEN** UKIP changes startup commands, database migrations, or container health checks
- **THEN** the change documents production readiness impact and validation evidence

#### Scenario: Background job is introduced
- **WHEN** UKIP introduces a scheduler, worker, or long-running job
- **THEN** it defines retry behavior, failure visibility, operational metrics, and recovery expectations

### Requirement: Strategic services have operational visibility
Strategic services SHALL expose enough operational signals to diagnose production health.

#### Scenario: Enrichment pipeline fails
- **WHEN** enrichment or reconciliation fails in production
- **THEN** operators can identify affected service, provider dependency, job state, error class, and retry/recovery path
