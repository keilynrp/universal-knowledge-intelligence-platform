## Context

The enrichment pipeline uses eight external sources (WoS, Scopus, OpenAlex, Crossref, PubMed, S2, DBLP, Scholar). Each is guarded by an in-process `CircuitBreaker` instance with failure count and state (CLOSED/OPEN/HALF_OPEN). When an entity enrichment fails, the worker sets `enrichment_status = 'failed'` but stores no machine-readable reason — only an optional `enrichment_failure` blob inside `attributes_json`. Operators and the scheduler see `failed` entities but cannot distinguish between "API is down for all sources" vs "no matching record exists" vs "rate limited."

The circuit breakers already track `failure_count` (property) and state; they lack a `success_count` counter and are not reachable from the API layer.

## Goals / Non-Goals

**Goals:**
- Add a `enrichment_failure_reason` column to `raw_entities` so the worker can store a short failure category at write time
- Expose circuit breaker states + in-process source counters via `GET /enrichment/sources/health`
- Provide aggregate per-domain/per-source quality stats via `GET /enrichment/sources/stats` (SQL aggregation, no new storage)
- Frontend panel showing source health and failure breakdown on the analytics dashboard

**Non-Goals:**
- Persistent time-series storage of source health (in-process counters reset on restart — acceptable for operational visibility)
- Alerting or webhooks on circuit state changes (separate concern)
- Changing enrichment worker retry logic or circuit breaker thresholds
- Per-entity latency tracking

## Decisions

### D1: failure_reason stored as a short string enum on the entity row

**Decision:** Add `enrichment_failure_reason VARCHAR(30)` directly on `raw_entities`, set when `enrichment_status` transitions to `failed`.

**Rationale:** Queries like "how many failures per reason per domain" become trivial SQL GROUP BY. Embedding in `attributes_json` would require JSON extraction, which is slow and non-indexable. The column is nullable — pre-existing `failed` rows keep NULL (shown as "unknown" in UI).

**Alternative considered:** Store in a separate `enrichment_failure_log` table. Rejected: joins add complexity; one-to-one relationship with entity status makes the column simpler.

**Failure reason values:**
- `no_match` — all sources searched, none returned a usable record
- `api_error` — one or more sources returned an HTTP 4xx/5xx non-rate-limit error
- `rate_limited` — source returned 429 and circuit is still closed
- `circuit_open` — circuit breaker was OPEN, source skipped without calling
- `timeout` — request exceeded configured timeout
- `all_sources_failed` — every source attempted, all failed for mixed reasons

### D2: Circuit breaker counters tracked in-process, exposed via singleton registry

**Decision:** Add a `success_count` integer counter to `CircuitBreaker`. Register all worker circuit breakers in a module-level dict `_CB_REGISTRY` in `enrichment_worker.py`. The health endpoint reads this dict directly — no DB, no IPC.

**Rationale:** The enrichment worker already runs as a single asyncio task in the same process as the FastAPI server. Reading in-process state is O(1), consistent, and needs no persistence layer. State resets on restart — documented as expected behaviour for an operational snapshot.

**Alternative considered:** Persisting circuit state to Redis. Rejected: adds a dependency; in-process counters are sufficient for a health dashboard.

### D3: Stats endpoint uses live SQL aggregation, no pre-computed table

**Decision:** `GET /enrichment/sources/stats` runs a single GROUP BY query over `raw_entities(domain, enrichment_source, enrichment_status, enrichment_failure_reason)` at request time.

**Rationale:** The analytics dashboard already executes similar aggregations (enrichment %, concept counts). At UKIP's scale (<1M entities) a GROUP BY over indexed columns returns in <100ms. Materialising to a separate table would add write-time coupling to the enrichment worker.

**Alternative considered:** Pre-compute into a `enrichment_quality_snapshots` table on each scheduler run. Rejected: the scheduler runs every 60s, so the table would be stale anyway. Live query gives fresher data with less complexity.

## Risks / Trade-offs

- **[Risk] Counter drift on concurrent requests**: `success_count` and `failure_count` on `CircuitBreaker` are updated from the enrichment worker asyncio task but read from HTTP handler threads. Python GIL protects simple integer increments on CPython; safe in practice. Mitigation: use thread-safe integer increment if moving to multi-process in future.
- **[Risk] NULL failure_reason on pre-existing failed entities**: Rows that failed before this migration will show `failure_reason = NULL`. Mitigation: UI shows "unknown" for NULL; no backfill needed.
- **[Trade-off] Stats query latency grows with entity count**: GROUP BY over raw_entities scales linearly. Mitigation: the existing indexes on `(domain, enrichment_status)` cover the query; add a composite index on `(enrichment_source, enrichment_status)` as part of this change.

## Migration Plan

1. Add `enrichment_failure_reason` column via Alembic migration + idempotent startup `ALTER TABLE IF NOT EXISTS` (nullable, no default — existing rows keep NULL)
2. Add `success_count` to `CircuitBreaker` class (backward-compatible, default 0)
3. Update `enrichment_worker.py` to set `failure_reason` and increment `success_count`
4. Add two endpoints to `enrichment_schedule.py` (or a new `enrichment_sources.py` router)
5. Add `EnrichmentSourceHealthCard` frontend component and mount on dashboard
6. Add composite DB index on `raw_entities(enrichment_source, enrichment_status)`

**Rollback:** Drop the new endpoints and revert the column add migration. The column is nullable — no data loss if left in place.

## Open Questions

*(none — design is self-contained)*
