## Why

The derived-data-status panel can show a domain as **stale** (enriched entities are fewer than expected), but closing that gap requires a human to manually trigger bulk enrichment. There is no mechanism that automatically detects and heals stale domains — leaving the platform dependent on operator attention to maintain data freshness.

## What Changes

- **New**: `DomainEnrichmentPolicy` model — per-domain enrichment configuration (staleness threshold, min enrichment %, max re-queue budget per run, enabled flag)
- **New**: `EnrichmentScheduler` service — async background task that runs on a configurable interval, scans domains using `entity_base_q` + `count_by_status`, and re-queues stale entities by setting their `enrichment_status` back to `pending`
- **New**: `GET /enrichment/schedule` — returns scheduler state (enabled, interval, last run, next run, domains checked)
- **New**: `GET /enrichment/schedule/{domain_id}` — per-domain staleness report (current %, threshold, last auto-run, queue depth)
- **New**: `POST /enrichment/schedule/{domain_id}/trigger` — manually trigger a scheduled run for one domain (admin+)
- **New**: `PUT /enrichment/schedule/{domain_id}/policy` — update the enrichment policy for a domain (admin+)
- **New**: Derived-status dashboard panel addition — shows scheduler status and next run time alongside the existing derived-status cards

## Capabilities

### New Capabilities

- `enrichment-scheduler-service`: Background scheduler service with domain staleness detection, re-queue logic, and configurable per-domain policies
- `enrichment-schedule-api`: REST endpoints for querying scheduler state, viewing per-domain policies, and manually triggering runs
- `enrichment-schedule-ui`: Dashboard panel showing scheduler status and next run, wired into the existing derived-status page

### Modified Capabilities

- `enrichment-progress-tracking`: The scheduler re-queues entities using the existing `pending` status path, so the existing progress-tracking toast will automatically display scheduler-triggered runs — no spec-level requirement changes needed

## Impact

- **Backend**: New `DomainEnrichmentPolicy` table (migration), new `EnrichmentScheduler` service (`backend/services/enrichment_scheduler.py`), new router (`backend/routers/enrichment_schedule.py`), startup wiring in `main.py`
- **Frontend**: New panel component on the derived-status dashboard (`frontend/app/analytics/dashboard/`)
- **Dependencies**: APScheduler already available via enrichment_worker pattern; alternatively pure `asyncio` periodic task (no new dep needed)
- **Existing enrichment_worker**: Zero changes — the scheduler only sets `enrichment_status = pending`; the worker's existing pick-up loop handles the rest
- **entity_base_q**: Used throughout — scheduler uses `count_by_status` and `entity_base_q` to detect and scope stale entities, consistent with the read-model contract
