## Context

`RawEntity.enrichment_status` is the primary lifecycle signal for the enrichment pipeline. It has accumulated three synonymous terminal values — `"completed"`, `"done"`, `"enriched"` — because different worker versions and adapter integrations wrote different strings. Every downstream consumer (derived_status_service, analytics queries, frontend badge logic) must enumerate all three, creating a fragile N-way string comparison that grows with each new pipeline integration.

`attributes_json` is an untyped JSON blob written by enrichment workers. The keys written (e.g., `enrichment_authors`, `enrichment_author_orcids`, `enrichment_affiliations`, `enrichment_failure`) are undocumented. This makes it impossible to validate correctness in tests, write typed consumers, or safely expose fields via the API.

`validation_status` similarly has no enum — only `"pending"` appears in practice.

## Goals / Non-Goals

**Goals:**
- Single canonical `EnrichmentStatus` enum: `none | pending | processing | completed | failed`
- Single canonical `ValidationStatus` enum: `pending | valid | invalid`
- DB migration at startup that collapses `"done"` and `"enriched"` into `"completed"` (idempotent UPDATE)
- All backend call-sites use the enum constants — no bare string literals for status comparisons
- Documented `attributes_json` key contract: a typed list of known top-level keys that enrichment workers write
- Frontend status filters and badge logic updated to use `"completed"` only
- Test coverage: migration idempotency, no-legacy-values assertion, attribute-key smoke check

**Non-Goals:**
- Changing the column type to a database-level ENUM (SQLite doesn't support ALTER COLUMN; application-layer enforcement is sufficient)
- Validating or migrating the content inside `attributes_json` values (only top-level keys are documented; content remains free-form per key)
- Introducing a separate `attributes` table (out of scope; blob stays)
- Changing `quality_score` computation logic

## Decisions

### D1: Application-layer enum, not DB constraint

**Decision:** Enforce `EnrichmentStatus` at the Pydantic / application layer only. No DB-level CHECK constraint or ENUM column.

**Rationale:** SQLite doesn't support ALTER COLUMN to add CHECK constraints after table creation without rebuilding the table. Adding a CHECK constraint would require a table rebuild migration that is high-risk on existing data. The application layer is the right place to enforce this for an ORM-backed FastAPI app — Pydantic validators at the schema level provide the guarantee before any write reaches the DB.

**Alternative considered:** Alembic migration to rebuild the table. Rejected: too risky for a production table that may have millions of rows; application-layer validation achieves the same safety with zero data movement.

### D2: Startup migration over Alembic revision

**Decision:** Consolidate legacy status values via a raw SQL `UPDATE` in the FastAPI lifespan startup block, alongside the existing column-add migrations.

**Rationale:** The project already uses startup-block migrations for column additions (see `main.py` lifespan). A two-line UPDATE fits that pattern cleanly:
```sql
UPDATE raw_entities SET enrichment_status = 'completed'
WHERE enrichment_status IN ('done', 'enriched');
```
This is idempotent — re-running on a clean database is a no-op. It runs before any request is served, so no in-flight request sees legacy values post-migration.

**Alternative considered:** A one-time Alembic migration script. Rejected: the project has no active Alembic migration chain; introducing one for this small change adds overhead without benefit.

### D3: Import the enum from `backend.schemas`, not `backend.models`

**Decision:** Place `EnrichmentStatus` and `ValidationStatus` in `backend/schemas.py`. All routers, workers, and services import from there.

**Rationale:** `models.py` is SQLAlchemy-only; mixing Pydantic enums there creates an import dependency inversion. `schemas.py` is the natural single source of truth for data contract types. Workers and services already import from schemas for payload types.

### D4: Documented attributes_json contract as a code comment + TypedDict, not a DB schema

**Decision:** Define an `EntityAttributesDict` `TypedDict` in `backend/schemas.py` documenting the known top-level keys. Workers write to a plain `dict`, serialize with `json.dumps`. The TypedDict is documentation + IDE-assist only — not enforced at runtime.

**Rationale:** Runtime enforcement would require deserializing, validating, and re-serializing on every write — expensive and fragile. The real value is making the implicit schema explicit so developers know what keys to expect and tests can assert that no unknown keys are written by the worker.

**Known keys to document:**
- `enrichment_authors: list[str]`
- `enrichment_author_orcids: list[str | None]`
- `enrichment_affiliations: list[str]`
- `enrichment_funding: list[str]`
- `enrichment_mesh_terms: list[str]`
- `enrichment_tldr: str | None`
- `enrichment_influential_citation_count: int | None`
- `enrichment_references_count: int | None`
- `enrichment_license: str | None`
- `enrichment_venue: str | None`
- `enrichment_failure: str` (written on failure path)

## Risks / Trade-offs

- **[Risk] Legacy status values in external imports** — A CSV uploaded by a user might contain a raw `"done"` value in an `enrichment_status` column. Mitigation: the startup migration only targets existing rows; new ingest does not write to `enrichment_status` directly (enrichment_worker.py controls writes). The ingest router never accepts enrichment_status from user input.

- **[Risk] Migration runtime on large tables** — The UPDATE could be slow if there are millions of rows with legacy values. Mitigation: `enrichment_status` is indexed; the WHERE clause uses an IN predicate on an indexed column. For typical UKIP deployments the table is small; for large deployments the UPDATE completes in under a second with the index.

- **[Risk] Test fixtures using legacy values** — Existing tests may create entities with `enrichment_status="done"`. Mitigation: the new test assertion (no-legacy-values check) will catch these. Any fixture using `"done"` must be updated to `"completed"`.

- **[Trade-off] TypedDict is documentation-only** — Workers that skip the TypedDict annotation can still write arbitrary keys. Accepted: the documentation + test smoke check provides a strong enough guardrail without the runtime cost of full validation.

## Migration Plan

1. Add `EnrichmentStatus` and `ValidationStatus` enums to `backend/schemas.py`
2. Add startup UPDATE migration in `backend/main.py` lifespan block
3. Update `backend/services/derived_status_service.py` call-sites
4. Update `backend/enrichment_worker.py` to use enum constants
5. Update `backend/routers/` (analytics, entities) string comparisons
6. Update frontend badge/filter logic
7. Add `EntityAttributesDict` TypedDict to schemas
8. Add tests: migration idempotency, no-legacy-values, attribute-key smoke

**Rollback:** If the enum causes issues, revert the import change in derived_status_service.py and enrichment_worker.py — the underlying column still accepts any string value. The startup UPDATE cannot be rolled back automatically (rows already migrated), but the old code still works with `"completed"` values since `"completed"` was always one of the accepted values.

## Open Questions

*(none — the design is fully specified)*
