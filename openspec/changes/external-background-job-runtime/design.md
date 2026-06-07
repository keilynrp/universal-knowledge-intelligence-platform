## Context

Three execution models coexist today:

- an asyncio enrichment scheduler started from FastAPI lifespan;
- a scheduled-import daemon thread started from FastAPI lifespan;
- a scheduled-report daemon thread started from FastAPI lifespan.

The design must remove process coupling without breaking existing scheduling
APIs or tenant isolation.

## Architecture decision

Use a broker-backed, at-least-once delivery model with durable job metadata in
PostgreSQL. Broker technology remains an implementation decision until a short
evaluation compares Celery, Dramatiq, and an intentionally small PostgreSQL
lease queue against the requirements below.

The system SHALL NOT claim exactly-once behavior. Every handler must be
idempotent.

## Components

1. **Producer:** validates authorization and tenant scope, persists a job
   envelope, and publishes a reference.
2. **Scheduler/dispatcher:** finds due schedules and creates jobs using a stable
   schedule occurrence key.
3. **Worker:** claims work, renews a lease, executes the handler, and persists a
   terminal result.
4. **Recovery supervisor:** makes abandoned leases eligible for retry.
5. **Operations API:** exposes status, cancellation, authorized replay, and
   bounded diagnostics.

## Job envelope

Minimum fields:

- `job_id`
- `job_type`
- `org_id`
- `requested_by`
- `idempotency_key`
- `payload_version`
- encrypted or referenced payload
- `status`
- `priority`
- `attempt`
- `max_attempts`
- `available_at`
- `lease_owner`
- `lease_expires_at`
- `created_at`, `started_at`, `finished_at`
- bounded error code and sanitized details
- correlation/request ID

Payloads must not contain reusable credentials. Workers resolve credentials
through the governed configuration path.

## State machine

`pending -> queued -> running -> succeeded`

Allowed failure paths:

- `running -> retry_wait -> queued`
- `running -> failed`
- `pending|queued|retry_wait -> cancelled`
- expired `running -> retry_wait|failed`

Transitions are compare-and-set operations. Invalid transitions fail closed and
emit an audit event.

## Tenant isolation

- `org_id` is mandatory for customer work.
- Producer authorization is revalidated before enqueue.
- Worker queries and side effects use the persisted `org_id`, never a global
  ambient context.
- Status, cancel, and replay APIs apply tenant scope and role checks.
- Dead-letter and error metadata are tenant-scoped.

## Reliability

- Stable idempotency keys prevent duplicate schedule occurrences.
- Side-effecting handlers record checkpoints where partial completion matters.
- Retry policy is typed by error class.
- Rate limits and provider circuit breakers remain authoritative.
- Worker shutdown stops new claims, renews or releases current leases safely,
  and finishes within a bounded drain period.

## Observability

Required metrics:

- queue depth and oldest-job age by job type;
- accepted, started, succeeded, retried, failed, cancelled;
- runtime and wait-time distributions;
- lease expirations and replay count;
- tenant-safe correlation identifiers;
- worker heartbeat, concurrency, and saturation.

Alerts must cover unavailable workers, growing oldest-job age, terminal failure
rate, and repeated lease expiration.

## Rollout

1. Add durable schema and shadow-write job metadata.
2. Externalize scheduled reports as the lowest-volume slice.
3. Externalize scheduled imports.
4. Externalize enrichment scheduling and execution.
5. Disable in-process loops by default.
6. Remove compatibility code only after the observation window and rollback review.

Each slice has a feature flag and cannot advance until parity, duplicate, and
recovery tests pass.

## Security and privacy

- No secrets or full sensitive records in broker messages or logs.
- Cancellation and replay require elevated roles and immutable audit.
- Payload retention follows the related data class retention policy.
- Broker and worker credentials are independently rotatable.

## Open decisions

- Broker/runtime selection.
- Whether job payloads live entirely in PostgreSQL or use encrypted object
  storage for large imports.
- Initial per-job SLOs and worker concurrency limits based on measured workloads.

