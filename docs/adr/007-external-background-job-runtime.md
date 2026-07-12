# ADR-007: External Background Job Runtime on a PostgreSQL Lease Queue

## Status

Accepted

## Date

2026-07-12

## Context

UKIP starts all durable background work inside the FastAPI web process, from the
application lifespan:

- `background_enrichment_worker` (asyncio) — enrichment execution;
- `authority batch_worker.run_batch_worker` (asyncio) — already backed by a DB
  job table (`authority_resolve_jobs`) with atomic claim + time-based recovery;
- `coauthor_recompute_loop` (asyncio) — derived-stats recompute;
- `enrichment_scheduler.start_loop` (asyncio) — enrichment scheduling;
- `scheduled_imports.start_scheduler` (daemon thread);
- `scheduled_reports.start_scheduler` (daemon thread).

This couples API availability to durable work and constrains the backend to a
single replica: a web restart can interrupt in-flight work, and horizontally
scaling the API would run duplicate scheduler loops. That is incompatible with
the reliability and recoverability expected of a high-assurance enterprise
deployment (ER-OPS-001).

We need durable, recoverable, tenant-scoped background execution with API,
scheduler, and workers scaling independently. The runtime technology was left
open pending a comparison against accepted requirements.

## Decision

Adopt an **at-least-once, broker-free durable job runtime backed by PostgreSQL**:
a lease queue using `SELECT … FOR UPDATE SKIP LOCKED` for atomic claims, with
explicit leases (`lease_owner`, `lease_expires_at`), typed retries, cancellation,
and an abandoned-lease recovery supervisor. Job metadata lives in PostgreSQL in
the same database as the producers, so enqueue is transactional with the work
that requested it.

Consequences of the model:

- The system **does not** claim exactly-once execution. Every handler **must be
  idempotent**, keyed by a stable tenant-scoped idempotency key.
- API, scheduler/dispatcher, and worker are **separate entrypoints**; API
  replicas run **no** scheduler loop.
- Transitions are compare-and-set; invalid transitions fail closed and emit an
  audit event.

This formalizes and generalizes the pattern already proven in-repo by
`authority_resolve_jobs` (which today claims atomically and recovers via
`reset_stale_jobs`, but lacks an explicit lease). The new contract adds real
leases, typed retry, cancellation, replay, and observability.

### Rejected alternatives

- **Celery (+ Redis/RabbitMQ)** — mature and full-featured, but heavy
  operational surface (beat singleton lock, broker + result backend), and splits
  the source of truth between the broker and PostgreSQL. Overkill for UKIP's
  current workload; adds a hard broker dependency to the durable path.
- **Dramatiq (+ Redis)** — lighter than Celery, but still introduces a broker on
  the durable path. UKIP's Redis is currently a **fail-open cache**; making
  durability depend on it would change its reliability contract and create two
  sources of truth for job state.
- **Keep in-process loops** — the status quo this change exists to remove.

Broker-backed runtimes remain re-evaluable if measured throughput ever exceeds
what a Postgres lease queue serves (not the case at current scale). The handler
and producer contracts are written to not assume the queue implementation, so a
future broker swap stays behind the same envelope.

## Consequences

- **Easier:** durable across API/worker restarts; independent scaling; no new
  infrastructure to run, secure, or rotate; transactional enqueue; reuse of
  existing tenant-isolation and audit patterns; a proven in-repo precedent.
- **Harder:** we build (not buy) the scheduler/dispatcher, lease renewal, and
  recovery; throughput is bounded by PostgreSQL (acceptable and monitorable via
  queue-age SLOs); every handler must be made idempotent before cutover.

## References

- Change: `external-background-job-runtime` (proposal.md, design.md)
- Spec: `durable-background-job-contract`
- Companion: `docs/architecture/external-background-job-runtime-discovery.md`
  (inventory, workload characteristics, runtime evaluation, threat model)
- Prior art: `authority_resolve_jobs` + `backend/authority/batch_worker.py`;
  EPIC-012 tenant isolation; EPIC-016 retention; ADR-004 circuit breaker
