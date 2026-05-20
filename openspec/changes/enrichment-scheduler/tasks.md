## 1. Database models and migration

- [x] 1.1 Add `DomainEnrichmentPolicy` model to `backend/models.py` (domain_id, enabled, min_enrichment_pct, max_budget_per_run, staleness_threshold_days, created_at, updated_at)
- [x] 1.2 Add `EnrichmentSchedulerRun` model to `backend/models.py` (domain_id, triggered_by, queued_count, started_at, finished_at, notes)
- [x] 1.3 Add idempotent startup migration for both tables in `backend/main.py` lifespan block (ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS pattern)

## 2. Enrichment scheduler service

- [x] 2.1 Create `backend/services/enrichment_scheduler.py` with `EnrichmentScheduler` class holding scheduler state (last_run_at, next_run_at, interval_seconds, running flag)
- [x] 2.2 Implement `_check_domain(db, domain_id, policy)` — calls `count_total` and `count_by_status` via `entity_base_q`, returns staleness report dict
- [x] 2.3 Implement `_requeue_domain(db, domain_id, policy)` — issues UPDATE WHERE enrichment_status IN ('none','failed') LIMIT max_budget_per_run, returns queued_count
- [x] 2.4 Implement `_record_run(db, domain_id, triggered_by, queued_count, notes)` — inserts EnrichmentSchedulerRun row
- [x] 2.5 Implement `run_once(db)` — iterates all enabled DomainEnrichmentPolicy rows, calls _check_domain + _requeue_domain + _record_run for each stale domain, logs summary
- [x] 2.6 Implement `start_loop()` — async function with `while True: await asyncio.sleep(interval_seconds); run_once(db)` pattern matching `enrichment_worker.py`

## 3. Wire scheduler into application startup

- [x] 3.1 Import `EnrichmentScheduler` in `backend/main.py`
- [x] 3.2 Instantiate a module-level `_enrichment_scheduler = EnrichmentScheduler()` in `main.py`
- [x] 3.3 Add `asyncio.create_task(enrichment_scheduler.start_loop())` in lifespan block, guarded by `UKIP_SKIP_STARTUP_SIDE_EFFECTS` check (same pattern as enrichment worker)

## 4. REST API router

- [x] 4.1 Create `backend/routers/enrichment_schedule.py` with APIRouter
- [x] 4.2 Implement `GET /enrichment/schedule` — returns global scheduler state from `_enrichment_scheduler` instance
- [x] 4.3 Implement `GET /enrichment/schedule/{domain_id}` — returns per-domain staleness report using `_check_domain` + latest EnrichmentSchedulerRun
- [x] 4.4 Implement `GET /enrichment/schedule/{domain_id}/runs` — queries EnrichmentSchedulerRun ordered by started_at desc, limit param (default 20, max 100)
- [x] 4.5 Implement `POST /enrichment/schedule/{domain_id}/trigger` — calls `_requeue_domain` + `_record_run` with triggered_by='manual', requires admin+ role
- [x] 4.6 Implement `PUT /enrichment/schedule/{domain_id}/policy` — upserts DomainEnrichmentPolicy row, requires admin+ role, returns 201 on create / 200 on update
- [x] 4.7 Register `enrichment_schedule` router in `backend/main.py`

## 5. Pydantic schemas

- [x] 5.1 Add `DomainEnrichmentPolicySchema` (response) and `DomainEnrichmentPolicyUpdate` (request) to `backend/schemas.py` with field constraints (min_enrichment_pct 0–100, max_budget_per_run 1–10000, staleness_threshold_days 1–3650)
- [x] 5.2 Add `EnrichmentSchedulerRunSchema` (response) to `backend/schemas.py`
- [x] 5.3 Add `SchedulerStateResponse` and `DomainStalenessReport` to `backend/schemas.py`

## 6. Frontend — scheduler health card

- [x] 6.1 Create `frontend/app/components/EnrichmentSchedulerCard.tsx` — fetches `GET /enrichment/schedule` and renders global state (enabled badge, interval, last run, next run)
- [x] 6.2 Add per-domain staleness table inside EnrichmentSchedulerCard — fetches `GET /enrichment/schedule/{domain_id}` for each domain in the schedule response, shows enrichment %, stale badge
- [x] 6.3 Add "Run Now" button per domain row — calls `POST /enrichment/schedule/{domain_id}/trigger`, shows loading state + queued-count toast on success, hidden for non-admin roles
- [x] 6.4 Add "Edit Policy" button per domain row — opens modal with form fields (min_enrichment_pct, max_budget_per_run, staleness_threshold_days, enabled toggle), calls PUT on submit, admin only
- [x] 6.5 Mount `EnrichmentSchedulerCard` on the analytics dashboard page (`frontend/app/analytics/dashboard/page.tsx`) below the derived-status resource cards

## 7. Tests

- [x] 7.1 Create `backend/tests/test_enrichment_scheduler.py` — test `_check_domain` correctly identifies stale vs healthy domains using test DB entities
- [x] 7.2 Add test: `_requeue_domain` sets exactly min(stale_count, budget) entities to 'pending'
- [x] 7.3 Add test: `_requeue_domain` does not touch 'completed', 'pending', or 'processing' entities
- [x] 7.4 Add test: `GET /enrichment/schedule` returns 200 with expected fields
- [x] 7.5 Add test: `GET /enrichment/schedule/{domain_id}` returns staleness report
- [x] 7.6 Add test: `POST /enrichment/schedule/{domain_id}/trigger` requires admin role (403 for viewer)
- [x] 7.7 Add test: `PUT /enrichment/schedule/{domain_id}/policy` creates on first call (201), updates on second (200)
- [x] 7.8 Add test: policy with `enabled=false` causes scheduler to skip that domain in `run_once`
