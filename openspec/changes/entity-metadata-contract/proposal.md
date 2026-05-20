## Why

The `enrichment_status` field on `RawEntity` has three synonymous terminal values (`"completed"`, `"done"`, `"enriched"`) that accumulated across different worker versions, forcing every consumer — derived_status_service.py, analytics routers, frontend filters — to enumerate all three. The `attributes_json` blob has no documented schema, making it impossible to validate what enrichment workers write or what the API safely exposes. This creates silent data drift and fragile conditional logic that grows harder to maintain with each new pipeline stage.

## What Changes

- **Canonicalize `enrichment_status`** to a 5-value enum: `none | pending | processing | completed | failed`. All existing rows with `"done"` or `"enriched"` are migrated to `"completed"` via a DB migration at startup.
- **Add `EnrichmentStatus` and `ValidationStatus` Pydantic enums** to `backend/schemas.py` so every schema and router can import the constants instead of bare strings.
- **Document the `attributes_json` contract** — a fixed set of known top-level keys that enrichment workers may write (e.g., `enrichment_authors`, `enrichment_author_orcids`, `enrichment_affiliations`, `enrichment_failure`) with their types; unknown keys are still allowed but warned in tests.
- **Update all call-sites** — `derived_status_service.py`, `enrichment_worker.py`, analytics and entity routers, frontend status filters — to use the canonical enum values.
- Add a **lint / test assertion** that no `RawEntity` row in test fixtures uses the legacy synonyms after migration.

## Capabilities

### New Capabilities

- `enrichment-status-enum`: Canonical `EnrichmentStatus` enum (schema + DB migration) with a single source of truth for the five legal values; includes startup migration and updated call-sites across backend and frontend.
- `entity-attribute-schema`: Documented contract for `attributes_json` top-level keys written by enrichment workers, with typed field list and a test assertion for unknown key detection.

### Modified Capabilities

*(none — no existing spec-level requirements are changing)*

## Impact

- **`backend/schemas.py`** — add `EnrichmentStatus`, `ValidationStatus` enums; update `EntityBase` field type
- **`backend/models.py`** — no column type change; enum enforced at application layer only
- **`backend/main.py`** — startup migration: `UPDATE raw_entities SET enrichment_status='completed' WHERE enrichment_status IN ('done','enriched')`
- **`backend/services/derived_status_service.py`** — replace `["completed","done","enriched"]` with `[EnrichmentStatus.completed]`
- **`backend/enrichment_worker.py`** — use `EnrichmentStatus` constants when setting status
- **`backend/routers/analytics.py`, `entities.py`** — any hardcoded status string comparisons
- **`frontend/app/`** — any hardcoded `"completed"` / `"done"` / `"enriched"` string checks in filters or badges
- **`backend/tests/`** — add migration idempotency test + attribute-schema assertion helper
