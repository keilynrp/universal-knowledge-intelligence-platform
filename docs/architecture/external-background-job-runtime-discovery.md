# External Background Job Runtime — Discovery

> Companion to [ADR-007](../adr/007-external-background-job-runtime.md) and the
> `external-background-job-runtime` change. Satisfies Phase 1 tasks 1.1
> (inventory), 1.2 (workload characteristics), 1.3 (runtime evaluation), and 1.5
> (threat model & failure-mode analysis). The runtime decision (1.4) is the ADR.

## 1. In-process loop inventory (task 1.1)

All started from `backend/main.py` lifespan. "Scope" = targeted by this change.

| # | Loop / entrypoint | Mechanism | Producer(s) | Side effects | Tenant scope | Scope |
|---|-------------------|-----------|-------------|--------------|--------------|-------|
| 1 | `enrichment_worker.background_enrichment_worker` | asyncio task, polls `raw_entities` (status `pending`) | ingest / API enqueues via `enrichment_status` | external API calls, entity writes, RAG index, graph, authority enqueue | `RawEntity.org_id` | ✅ enrichment |
| 2 | `authority.batch_worker.run_batch_worker` | asyncio task, DB job table | `authority_resolve_jobs` rows | authority record writes | `AuthorityResolveJob.org_id` | precedent (already durable-ish) |
| 3 | `enrichment_worker.coauthor_recompute_loop` | asyncio task, polls `coauthor_dirty_scopes` | write hooks mark scopes dirty | `author_stats` recompute | scope `org_id` | derived (follows enrichment) |
| 4 | `enrichment_scheduler.start_loop` | asyncio task | `DomainEnrichmentPolicy` schedules | enqueues enrichment | policy `org_id` | ✅ scheduler |
| 5 | `scheduled_imports.start_scheduler` | **daemon thread** | `ScheduledImport` rows | import execution → entities | `ScheduledImport.org_id` | ✅ imports |
| 6 | `scheduled_reports.start_scheduler` | **daemon thread** | `ScheduledReport` rows | report generation, delivery | `ScheduledReport.org_id` | ✅ reports |

**Existing durable precedent.** `authority_resolve_jobs` + `batch_worker` already
implement: atomic claim (oldest `pending` → `processing`), progress counters, and
**time-based recovery** (`reset_stale_jobs` flips stale `processing` back to
`pending` at startup). What it lacks vs. the target contract: an explicit lease
(`lease_owner`/`lease_expires_at`), typed retry with backoff, cancellation,
authorized replay, and queue-age observability. The new contract generalizes it.

## 2. Workload characteristics (task 1.2)

Qualitative profile from current code (quantitative baselines to be captured in
the observation window, task 5.6):

| Job type | Cadence | Duration | Concurrency today | Retry today | Payload |
|----------|---------|----------|-------------------|-------------|---------|
| Enrichment (per entity) | continuous, polite-paced (~2s between claims) | seconds (external API bound) | 1 (single loop) | status reset on stale | entity id + provider cascade |
| Authority batch | on enqueue | seconds–minutes (batch) | 1 | `reset_stale_jobs` | field/entity_type + params |
| Scheduled import | cron-like per `ScheduledImport` | seconds–minutes | 1 thread | none durable | source config ref |
| Scheduled report | cron-like per `ScheduledReport` | seconds | 1 thread | none durable | report spec + recipients |

Implications for the contract:
- Volumes are **low-to-moderate** and I/O-bound (external providers), not
  CPU-bound — a Postgres lease queue amply serves this; broker throughput is not
  the constraint.
- Enrichment already rate-limits and uses provider circuit breakers (ADR-004);
  those remain authoritative and must not be bypassed by parallel workers.
- Payloads are small references (ids, config) — they fit in PostgreSQL; large
  import payloads (open decision) can move to referenced object storage later.

## 3. Runtime evaluation (task 1.3)

Criteria weighted for a high-assurance, Postgres-centric, single-region app.

| Criterion | PostgreSQL lease queue | Dramatiq (+Redis) | Celery (+Redis/RabbitMQ) |
|-----------|------------------------|-------------------|--------------------------|
| New infra to run/secure/rotate | none | broker (Redis durability) | broker + result backend |
| Source of truth for job state | single (PostgreSQL) | split (Redis + DB) | split (broker + DB) |
| Transactional enqueue with producer | yes | no | no |
| At-least-once delivery | yes (SKIP LOCKED + lease) | yes (Redis-dependent) | yes |
| Tenant isolation reuse | direct (`org_id` + existing patterns) | manual | manual |
| Scheduler singleton | dispatcher via DB lease | needs external beat/lock | beat singleton lock |
| In-repo precedent | yes (`authority_resolve_jobs`) | no | no |
| Operational surface | low | medium | high |
| Throughput ceiling | DB-bound (ample here) | high | high |

**Outcome:** PostgreSQL lease queue (ADR-007). It wins on every criterion that
matters at UKIP's scale; the only axis where brokers lead (raw throughput) is not
a current constraint. Handler/producer contracts stay implementation-agnostic so
a broker can be adopted later without rewriting handlers.

## 4. Threat model & failure-mode analysis (task 1.5)

### Failure modes

| Failure | Effect | Mitigation (contract) |
|---------|--------|-----------------------|
| API restart mid-accept | job half-enqueued | envelope persisted before ack; unpublished jobs recoverable (spec) |
| Worker crash mid-run | lease held by dead worker | `lease_expires_at` → recovery supervisor requeues |
| Duplicate delivery | double side effect | stable tenant-scoped idempotency key; idempotent handlers |
| Two workers claim one job | double execution | `FOR UPDATE SKIP LOCKED` compare-and-set; at most one claim |
| Poison job | infinite ret/crash loop | `max_attempts` + typed retry → `failed` (dead-letter) + alert |
| Scheduler duplication on API scale-out | duplicate occurrences | schedulers are separate entrypoints; API runs no loop; stable schedule-occurrence key |
| DB outage | no enqueue/claim | fail closed and visible; no broker message treated as authoritative |
| Backlog growth | latency, missed SLO | queue-age metric + alert; independent worker scaling |

### Security / privacy threats

- **Secret leakage in payloads/logs** → payloads carry references, never reusable
  credentials; workers resolve secrets via the governed config path; bounded,
  sanitized error details only.
- **Cross-tenant access** via status/cancel/replay → mandatory `org_id`, role +
  tenant checks on every lifecycle API; dead-letter and error metadata
  tenant-scoped.
- **Unauthorized replay/cancel** → elevated role required; immutable audit event
  per action, preserving original failure + attempt history.
- **Payload retention** → follows the related data-class retention policy
  (EPIC-016), not indefinite.

## 5. Open decisions carried forward

- Large import payloads in PostgreSQL vs. encrypted object storage (design open
  decision) — defer until import payload sizes are measured.
- Initial per-job SLOs and worker concurrency limits — set from the observation
  window (task 5.5/5.6).
- Deployment topology specifics (replica counts, drain window) — Phase 3.
