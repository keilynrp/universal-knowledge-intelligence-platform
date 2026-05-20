## 1. Backend Status Service

- [x] 1.1 Create `backend/services/derived_status_service.py` with `DerivedResourceStatus` schema (six resources, seven status values as constants)
- [x] 1.2 Implement `DerivedStatusService.compute("enrichment", scope, db)` — entity count vs enrichment_status counts
- [x] 1.3 Implement `DerivedStatusService.compute("graph", scope, db)` — entity count vs EntityRelationship row counts
- [x] 1.4 Implement `DerivedStatusService.compute("semantic_keyword_signals", scope, db)` — entity count vs non-null enrichment_concepts count
- [x] 1.5 Implement `DerivedStatusService.compute("rag_index", scope, db)` — ChromaDB collection count with `unknown` fallback on connection error
- [x] 1.6 Implement `DerivedStatusService.compute("executive_dashboard_snapshot", scope, db)` — analytics cache freshness check
- [x] 1.7 Implement `DerivedStatusService.compute("report_readiness", scope, db)` — completed Report row count
- [x] 1.8 Implement `DerivedStatusService.compute_all(scope, db)` — calls all six, returns full bundle dict

## 2. Backend Router and Caching

- [x] 2.1 Create `backend/routers/derived_status.py` with `GET /derived-status/{domain_id}` endpoint
- [x] 2.2 Add 30-second TTL in-memory cache keyed by `(domain_id, org_id)` using `cachetools.TTLCache` or `functools.lru_cache` with TTL
- [x] 2.3 Add domain existence check — return HTTP 404 for unknown non-"all" domain IDs
- [x] 2.4 Require authentication (`Depends(get_current_user)`) on the endpoint
- [x] 2.5 Register `derived_status` router in `backend/main.py`

## 3. Staleness Propagation Hooks

- [x] 3.1 Add cache invalidation call in `backend/enrichment_worker.py` after a batch of entities is marked `completed`
- [x] 3.2 Add cache invalidation call in `backend/services/graph_materializer.py` after domain graph build completes

## 4. Frontend Status Panel Component

- [x] 4.1 Create `frontend/app/components/DerivedStatusPanel.tsx` with fetch + interval polling logic
- [x] 4.2 Implement adaptive polling: 30s when any resource is `pending`/`processing`, 5 min otherwise
- [x] 4.3 Render six resource rows with colored status badges using the canonical color mapping
- [x] 4.4 Show `source_count`, `derived_count`, and `updated_at` (relative time) per row
- [x] 4.5 Implement "Rebuild" button — POST to `rebuild_endpoint`, optimistic pending state, error revert
- [x] 4.6 Map resource keys to human-readable display labels

## 5. Frontend Integration

- [x] 5.1 Embed `DerivedStatusPanel` in `frontend/app/analytics/dashboard/page.tsx` below the KPI summary row (skip when `isAllScope`)
- [x] 5.2 Embed `DerivedStatusPanel` in `frontend/app/page.tsx` inside a collapsible "Data Readiness" section (skip when `isAllScope`)

## 6. Backend Tests

- [x] 6.1 Create `backend/tests/test_derived_status.py` with empty-domain fixture — all six resources return `missing`
- [x] 6.2 Test `enrichment` returns `ready` when all entities have `enrichment_status = "completed"`
- [x] 6.3 Test `enrichment` returns `stale` when partial enrichment
- [x] 6.4 Test `rag_index` returns `unknown` when ChromaDB client raises connection error (mocked)
- [x] 6.5 Test `GET /derived-status/{domain_id}` returns HTTP 200 with all six resource keys
- [x] 6.6 Test cache hit — second call within TTL returns same `computed_at` timestamp
- [x] 6.7 Test `GET /derived-status/nonexistent` returns HTTP 404
