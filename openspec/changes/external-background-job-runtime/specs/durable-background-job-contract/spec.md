## ADDED Requirements

### Requirement: Accepted background work is durable

The system SHALL persist a tenant-scoped job envelope before acknowledging
background work as accepted.

#### Scenario: Broker is unavailable during acceptance
- **WHEN** the durable job envelope is persisted but publication fails
- **THEN** the job remains recoverable for later dispatch
- **AND** the API does not report that execution has started

#### Scenario: Persistence fails
- **WHEN** the job envelope cannot be persisted
- **THEN** the request fails visibly
- **AND** no broker message is treated as authoritative work

### Requirement: Delivery is at least once and handlers are idempotent

The system SHALL support duplicate delivery without duplicating externally
visible side effects.

#### Scenario: Worker completes a side effect and crashes before acknowledgement
- **WHEN** the same job is delivered again
- **THEN** its stable idempotency key identifies the prior effect
- **AND** the handler returns the existing result or safely resumes

### Requirement: Tenant scope follows the complete lifecycle

Every customer job SHALL have a non-null organization scope used for enqueue,
claim, execution, status, cancellation, replay, logs, and evidence.

#### Scenario: User requests another tenant's job
- **WHEN** a non-super-admin requests status, cancellation, or replay
- **THEN** the system returns no cross-tenant job data
- **AND** no transition occurs

### Requirement: Job transitions are explicit and auditable

The system SHALL enforce a finite state machine using atomic transitions.

#### Scenario: Two workers claim one job
- **WHEN** concurrent workers attempt to claim the same available job
- **THEN** at most one claim succeeds
- **AND** the losing worker performs no handler side effect

#### Scenario: Authorized replay is requested
- **WHEN** an operator replays a terminal failed job
- **THEN** the system creates an attributable audit event
- **AND** preserves the original failure and attempt history

### Requirement: Failures and saturation are observable

The system SHALL expose bounded metrics and health state for queue age, depth,
worker heartbeat, retries, terminal failures, and lease expirations.

#### Scenario: Oldest queued job exceeds its SLO
- **WHEN** queue age crosses the configured threshold
- **THEN** an operational alert is emitted
- **AND** the affected job type is identifiable without exposing tenant data

### Requirement: Process roles scale independently

API, scheduler, and worker roles SHALL be independently startable and SHALL NOT
require in-process scheduler loops in API replicas.

#### Scenario: A second API replica starts
- **WHEN** the deployment scales the API horizontally
- **THEN** no duplicate scheduler loop is created
- **AND** existing queued work continues independently

