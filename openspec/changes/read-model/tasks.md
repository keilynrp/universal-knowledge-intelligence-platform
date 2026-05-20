## 1. Create entity_query module

- [x] 1.1 Create `backend/services/entity_query.py` with `entity_base_q(db, scope, org_id=None)` factory applying the three mandatory guards
- [x] 1.2 Add `count_total(db, scope, org_id=None) -> int` helper
- [x] 1.3 Add `count_by_status(db, scope, status, org_id=None) -> int` helper
- [x] 1.4 Add `count_enriched(db, scope, org_id=None) -> int` convenience wrapper

## 2. Refactor derived_status_service.py

- [x] 2.1 Import `entity_base_q` in `derived_status_service.py`
- [x] 2.2 Replace all 7 inline `db.query(RawEntity).filter(source != "graph_materializer")` blocks with `entity_base_q(db, scope)` calls
- [x] 2.3 Verify no `"graph_materializer"` string remains in `derived_status_service.py`

## 3. Refactor entities router

- [x] 3.1 Import `entity_base_q` and count helpers in `backend/routers/entities.py`
- [x] 3.2 Replace inline entity base queries in enrich-stats and domain-stats endpoints with `entity_base_q` / count helpers

## 4. Refactor analytics router

- [x] 4.1 Import `entity_base_q` in `backend/routers/analytics.py`
- [x] 4.2 Replace inline entity base queries in `/dashboard/summary` and `/stats` handlers with `entity_base_q` calls

## 5. Refactor disambiguation router

- [x] 5.1 Import `entity_base_q` in `backend/routers/disambiguation.py`
- [x] 5.2 Replace inline entity base queries for field-grouping queries with `entity_base_q` calls

## 6. Tests

- [x] 6.1 Create `backend/tests/test_entity_query.py` — test `entity_base_q` excludes graph_materializer rows
- [x] 6.2 Add test: `entity_base_q` with scope `"domain:X"` filters to domain X only
- [x] 6.3 Add test: `count_total` returns 0 for empty domain
- [x] 6.4 Add test: `count_by_status` counts only entities with the given status
- [x] 6.5 Add test: `count_enriched` equals `count_by_status(..., EnrichmentStatus.completed)`
- [x] 6.6 Add test: importing `entity_query` has no side effects (no DB connection required)
