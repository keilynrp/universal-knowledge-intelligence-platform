## Context

The `enrichment_worker` is a long-running `asyncio` loop that picks up entities with `enrichment_status = 'pending'` and enriches them one at a time. Once enrichment is complete for a domain, entities stay `completed` indefinitely — there is no mechanism to detect when a domain becomes stale (new entities added since the last enrichment run) or to automatically re-queue them.

The derived-data-status panel (Sprint DC3) surfaces this staleness visually, but closing the gap requires a manual operator action. The platform already has two precedents for background scheduling: `ScheduledImport` (SQL model + asyncio loop, Sprint 61) and `ScheduledReport` (similar pattern). This change follows the same pattern.

**Current enrichment flow:**
```
User triggers bulk enrich → entities set to 'pending' → worker picks up → 'completed'
```
**Target flow:**
```
Scheduler detects stale domain → re-queues eligible entities to 'pending' → worker picks up (unchanged)
```

## Goals / Non-Goals

**Goals:**
- Automatically detect stale domains using `count_by_status` from `entity_base_q`
- Re-queue stale entities by setting `enrichment_status = 'pending'` — zero changes to the worker
- Per-domain policy: staleness threshold (days since last enrichment), min enrichment %, max budget per scheduler run
- REST API for querying scheduler state and per-domain policy
- Manual trigger endpoint for on-demand scheduled runs
- Minimal dashboard panel showing scheduler health

**Non-Goals:**
- Changing the enrichment worker itself (it stays unchanged)
- Distributed scheduling or leader election (single-process; acceptable for UKIP's scale)
- Priority queuing or ordering within a run (FIFO via existing worker is sufficient)
- APScheduler or Celery (pure `asyncio.sleep` loop matches the existing worker pattern)
- Per-entity staleness (granularity is per-domain, not per-entity)

## Decisions

### D1: Pure asyncio loop, not APScheduler

**Decision:** The scheduler is an `asyncio` periodic task using `asyncio.sleep`, started in `main.py`'s `lifespan` block alongside the enrichment worker.

**Rationale:** The enrichment worker already uses this pattern (lines 473–495 of `enrichment_worker.py`). Adding APScheduler would introduce a new dependency and a different concurrency model with no benefit at UKIP's scale. The `asyncio` loop wakes every 60 s, checks whether any domain policy timer has elapsed, and acts — simple and auditable.

**Alternative considered:** APScheduler with `AsyncIOScheduler`. Rejected: extra dependency, cron-expression complexity not needed for interval-based runs.

### D2: DomainEnrichmentPolicy as a SQLAlchemy model (not YAML config)

**Decision:** Per-domain scheduler settings live in a new `domain_enrichment_policies` DB table, editable via REST API at runtime without redeployment.

**Rationale:** Domain configurations already live in DB (organizations, stores). A YAML file would require a restart to change policy. DB allows operators to tune thresholds per-domain via the API while the system is running.

**Alternative considered:** Per-domain YAML config in `backend/domains/`. Rejected: requires file system access and restart; can't be modified via the UI.

### D3: Staleness detection via entity_base_q + count_by_status

**Decision:** The scheduler determines staleness by computing `count_enriched(db, scope) / count_total(db, scope)`. If below `min_enrichment_pct` (default 80%), the domain is stale.

**Rationale:** Re-uses the hardened `entity_base_q` factory — the graph_materializer guard and domain scope are applied automatically. No bespoke query needed.

**Alternative considered:** Timestamp-based staleness (last enrichment run > N days). Included as an **additional** guard (the policy table has a `staleness_threshold_days` column) but not the primary signal, since new un-enriched entities don't change timestamps.

### D4: Re-queue writes directly to the DB (not via the REST API)

**Decision:** The scheduler sets `enrichment_status = 'pending'` via a SQLAlchemy `update()` statement, bounded by the policy `max_budget_per_run`.

**Rationale:** Going through the HTTP layer would require auth token management inside the scheduler. Direct DB writes are simpler, match how the enrichment worker itself operates, and are bounded by the budget to prevent runaway re-queueing.

### D5: Scheduler run log in DB

**Decision:** Each scheduler run writes a row to a new `enrichment_scheduler_runs` table (domain_id, triggered_by, queued_count, started_at, finished_at, notes).

**Rationale:** Operators need to audit what the scheduler did. The runs table enables the `GET /enrichment/schedule/{domain_id}` endpoint to show last run details without in-memory state.

## Risks / Trade-offs

- **[Risk] Scheduler and manual bulk-enrich race**: If an operator manually triggers bulk enrichment while the scheduler is also re-queueing, entities could be double-queued. **Mitigation:** The scheduler only sets entities to `pending` if they are currently `none` or `failed` (not `pending`, `processing`, or `completed`). The worker's atomic claim (`UPDATE WHERE status='pending'`) already handles double-queue safely.

- **[Risk] Policy misconfiguration causes continuous re-queuing**: A `min_enrichment_pct = 100` with flaky enrichment sources means entities repeatedly fail and get re-queued. **Mitigation:** Policy has `max_budget_per_run` (default 100) and respects `enrichment_status = 'failed'` (failed entities require an explicit `force` flag to re-queue, not automatic).

- **[Trade-off] Single-process scheduler**: If the server restarts, the in-flight scheduler loop restarts with no memory of the previous run. **Mitigation:** The `enrichment_scheduler_runs` table preserves history; the next loop iteration will re-detect any still-stale domain.

- **[Trade-off] Coarse-grained staleness detection**: Detection granularity is per-domain, not per-entity age. An entity enriched 1 year ago and a new entity look the same to the threshold check. **Mitigation:** Accepted for now; timestamp-based per-entity staleness is a future enhancement.

## Migration Plan

1. Add `domain_enrichment_policies` and `enrichment_scheduler_runs` tables via idempotent startup migration in `main.py` (matching existing pattern for `failed_attempts` column migration etc.)
2. Create `backend/services/enrichment_scheduler.py`
3. Create `backend/routers/enrichment_schedule.py`
4. Wire scheduler task into `main.py` lifespan block
5. Add dashboard UI panel
6. All additive — no changes to existing enrichment_worker or entity data

**Rollback:** Remove the two new router registrations and the scheduler `asyncio.create_task` call. Tables can remain (they're empty and additive).

## Open Questions

*(none — design is self-contained)*
