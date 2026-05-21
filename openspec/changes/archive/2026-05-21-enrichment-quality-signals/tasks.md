## 1. Data model — failure reason column

- [x] 1.1 Add `enrichment_failure_reason` nullable `String(30)` column to `RawEntity` model in `backend/models.py`
- [x] 1.2 Create Alembic migration for the new column (idempotent `ALTER TABLE IF NOT EXISTS` pattern)
- [x] 1.3 Schema migration handled via Alembic `d3e4f5a6b7c9` (inline ALTER TABLE removed from main.py per project policy enforced by test_sprint86_5)
- [x] 1.4 Add composite index `ix_re_source_status` on `raw_entities(enrichment_source, enrichment_status)` in Alembic migration and startup block

## 2. CircuitBreaker — success_count

- [x] 2.1 Add `_success_count` integer field to `CircuitBreaker.__init__` in `backend/circuit_breaker.py`
- [x] 2.2 Increment `_success_count` inside `CircuitBreaker.call()` on successful completion (after the wrapped call returns without raising)
- [x] 2.3 Expose `success_count` as a `@property` on `CircuitBreaker`
- [x] 2.4 Reset `_success_count` to 0 when circuit transitions from HALF_OPEN to CLOSED

## 3. Enrichment worker — write failure reason

- [x] 3.1 Define `EnrichmentFailureReason` string constants in `backend/enrichment_worker.py` (or `backend/schemas.py`): `no_match`, `api_error`, `rate_limited`, `circuit_open`, `timeout`, `all_sources_failed`
- [x] 3.2 In `enrich_single_record` / failure path: set `entity.enrichment_failure_reason` when setting `enrichment_status = 'failed'`, choosing the most specific reason
- [x] 3.3 Set `enrichment_failure_reason = 'circuit_open'` when all sources are skipped due to open circuit breakers
- [x] 3.4 Set `enrichment_failure_reason = 'no_match'` when all sources return empty/no record
- [x] 3.5 Register all worker circuit breakers in a module-level `_CB_REGISTRY` dict in `enrichment_worker.py` for access by the health endpoint

## 4. REST API — source health and stats endpoints

- [x] 4.1 Add `SourceHealthEntry` and `SourceHealthResponse` Pydantic schemas to `backend/schemas.py`
- [x] 4.2 Add `SourceStatsEntry` and `SourceStatsResponse` Pydantic schemas to `backend/schemas.py`
- [x] 4.3 Implement `GET /enrichment/sources/health` in `backend/routers/enrichment_schedule.py` — reads `_CB_REGISTRY` from `enrichment_worker`, returns state + counters for each source
- [x] 4.4 Implement `GET /enrichment/sources/stats` in `backend/routers/enrichment_schedule.py` — GROUP BY aggregation over `raw_entities(domain, enrichment_source, enrichment_status, enrichment_failure_reason)`, optional `?domain_id=` filter

## 5. Frontend — source health card

- [x] 5.1 Create `frontend/app/components/EnrichmentSourceHealthCard.tsx` — fetches `GET /enrichment/sources/health`, renders per-source rows with state badge (green/red/amber), failure count, success count
- [x] 5.2 Add failure stats section to `EnrichmentSourceHealthCard` — fetches `GET /enrichment/sources/stats`, shows per-domain failure reason breakdown as small bar chart or pill counts
- [x] 5.3 Mount `EnrichmentSourceHealthCard` on analytics dashboard (`frontend/app/analytics/dashboard/page.tsx`) below `EnrichmentSchedulerCard`
- [x] 5.4 Update entity failure diagnostics panel (wherever `enrichment_failure` is rendered) to show the `enrichment_failure_reason` badge using the colour map: `no_match`→grey, `circuit_open`→red, `api_error`→orange, `rate_limited`→amber, `timeout`→yellow, `all_sources_failed`→red, NULL→grey "Unknown"

## 6. Tests

- [x] 6.1 Add tests to `backend/tests/test_circuit_breaker.py` — `success_count` increments on success, resets on HALF_OPEN→CLOSED transition
- [x] 6.2 Create `backend/tests/test_enrichment_quality_signals.py` — test failure reason written when enrichment fails (mock adapters returning no match, API error, circuit open)
- [x] 6.3 Add test: `GET /enrichment/sources/health` returns 200 with all registered sources
- [x] 6.4 Add test: `GET /enrichment/sources/stats` returns 200 with expected shape (total, enriched, failed, failure_reasons)
- [x] 6.5 Add test: `GET /enrichment/sources/stats?domain_id=science` filters correctly
- [x] 6.6 Add test: entity with NULL `enrichment_failure_reason` is handled gracefully in stats (counted in "unknown" bucket or excluded without error)
