## Why

The enrichment scheduler can now detect and re-queue stale domains automatically, but operators have no visibility into *why* entities remain in `failed` state or which external sources are misbehaving. Eight circuit breakers protect the enrichment worker from cascading API failures (WoS, Scopus, OpenAlex, Crossref, PubMed, S2, DBLP, Scholar) but their states are invisible — operators discover a source is tripped only by noticing stale enrichment data after the fact. Closing this gap allows operators to diagnose enrichment bottlenecks in minutes rather than hours.

## What Changes

- Add `enrichment_failure_reason` column to `raw_entities` to store a machine-readable failure category (`no_match`, `api_error`, `rate_limited`, `circuit_open`, `timeout`) when enrichment status becomes `failed`
- Expose a new `GET /enrichment/sources/health` endpoint returning real-time circuit breaker states and in-process counters (success, failure, consecutive failures) for all 8 sources
- Add aggregate failure analytics endpoint `GET /enrichment/sources/stats` returning per-domain, per-source breakdown of enriched/failed counts and failure reason distribution
- Frontend: add a "Source Health" panel to the analytics dashboard (below the scheduler card) showing circuit state badges and key rate metrics

## Capabilities

### New Capabilities

- `enrichment-source-health`: Circuit breaker state API and per-source success/failure counter — real-time health of each external enrichment provider
- `enrichment-failure-analytics`: Failure reason classification stored on entities, aggregate stats endpoint for per-domain/per-source quality signals

### Modified Capabilities

- `enrichment-failure-details`: Extend per-entity failure diagnostics to include the new `enrichment_failure_reason` field alongside the existing `attributes_json` failure object

## Impact

- `backend/models.py` — new `enrichment_failure_reason` column on `RawEntity`
- `backend/enrichment_worker.py` — write failure reason when setting `enrichment_status = 'failed'`
- `backend/circuit_breaker.py` — expose in-process counters (already has `failure_count` property; add `success_count`)
- `backend/routers/enrichment_schedule.py` — two new endpoints under `/enrichment/sources/`
- `frontend/app/components/EnrichmentSourceHealthCard.tsx` — new dashboard component
- No changes to enrichment worker logic, scheduler, or entity query service
