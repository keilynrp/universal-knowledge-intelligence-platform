## 1. Schema Enums and TypedDict

- [x] 1.1 Add `EnrichmentStatus` str-enum to `backend/schemas.py` with values: `none`, `pending`, `processing`, `completed`, `failed`
- [x] 1.2 Add `ValidationStatus` str-enum to `backend/schemas.py` with values: `pending`, `valid`, `invalid`
- [x] 1.3 Add `EntityAttributesDict` TypedDict to `backend/schemas.py` documenting all 11 known `attributes_json` top-level keys
- [x] 1.4 Add `KNOWN_ATTRIBUTE_KEYS: frozenset[str]` constant to `backend/schemas.py` derived from `EntityAttributesDict` field names

## 2. DB Migration

- [x] 2.1 Add idempotent startup migration to `backend/main.py` lifespan block: `UPDATE raw_entities SET enrichment_status='completed' WHERE enrichment_status IN ('done','enriched')`

## 3. Backend Call-site Updates

- [x] 3.1 Update `backend/services/derived_status_service.py` — replace `["completed","done","enriched"]` filter list with `[EnrichmentStatus.completed]`
- [x] 3.2 Update `backend/enrichment_worker.py` — import `EnrichmentStatus` from `backend.schemas` and replace all bare `"completed"`, `"failed"`, `"processing"`, `"pending"`, `"none"` string literals when setting `enrichment_status`
- [x] 3.3 Update `backend/routers/analytics.py` — replace any bare `enrichment_status` string comparisons with enum constants
- [x] 3.4 Update `backend/routers/entities.py` — replace any bare `enrichment_status` string comparisons with enum constants

## 4. Frontend Updates

- [x] 4.1 Audit `frontend/app/` for hardcoded `"done"` or `"enriched"` enrichment status strings and replace with `"completed"`
- [x] 4.2 Verify enrichment status badge/filter components use only the five canonical values

## 5. Tests

- [x] 5.1 Create `backend/tests/test_entity_metadata_contract.py` — test migration idempotency (run twice, second run affects 0 rows)
- [x] 5.2 Add test: no rows with `enrichment_status IN ('done','enriched')` exist after migration
- [x] 5.3 Add test: `EnrichmentStatus` enum exports exactly the five expected values
- [x] 5.4 Add test: `KNOWN_ATTRIBUTE_KEYS` matches `EntityAttributesDict` field names
- [x] 5.5 Add test: enrichment worker sets `enrichment_status = EnrichmentStatus.completed` on success (verify via existing `test_enrichment_worker.py` patterns or new test)
- [x] 5.6 Audit existing test fixtures — update any entity created with `enrichment_status="done"` or `"enriched"` to `"completed"`
