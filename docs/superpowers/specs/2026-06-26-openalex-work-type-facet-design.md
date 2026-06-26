# OpenAlex Work-Type Facet — Design

**Date:** 2026-06-26
**Status:** Approved (design)

## Goal

Let users filter entities by **work type** (Artículo, Libro, Tesis/Disertación,
Preprint, Dataset, Otro) and see that type at a glance, sourced from OpenAlex's
authoritative `work.type` controlled vocabulary. Surfaces as a new sidebar facet
plus type badges in the entity table and detail modal.

This answers two related requests: (1) a facet to filter by, and (2) clearer
entity-type specification in the side panel (books vs monographs vs articles).
OpenAlex differentiates these clearly via `work.type`; we don't capture it today.

## Background

- Today the OpenAlex adapter parses `host_venue`/ISSN but **does not store
  `work.type`** (`backend/adapters/enrichment/openalex.py`). The existing
  `entity_type` facet is a coarse ingest-time hint (e.g. `"publication"`), not the
  authoritative work classification.
- A facet system already exists: `GET /entities/facets` +
  `EntityService.get_facets` (`_FACET_FIELDS`) + `FacetPanel.tsx`
  (`FIELD_LABELS`/`FIELD_COLORS`/`FIELD_ORDER`). The new facet is additive and
  follows this pattern.
- `EnrichedRecord` (`backend/schemas_enrichment.py`) is the enrichment result; the
  worker writes `enrichment_*` columns from it (`backend/enrichment_worker.py`).

## Decisions (locked)

- **Granularity:** store the **raw** `work.type`; group into **broad categories**
  for facet/badges. Raw is the single stored value; category is derived on read
  (no double storage, no drift).
- **Facet:** a **new, separate** `work_type` facet — does not change `entity_type`
  semantics.
- **Surfacing:** sidebar facet + badge in the detail modal + badge in the table.
- **Backfill:** an **optional** script (existing entities show "Sin clasificar"
  until run). Mirrors the nif_bayes / #84 backfill pattern.

## Category Model

New module `backend/services/work_type.py` — single source of truth, used by the
facet aggregation, the filter, and (mirrored in TS) the badges.

| Category | Raw OpenAlex `type` values |
|----------|----------------------------|
| **Artículo** | article, review, letter, editorial |
| **Libro** | book, monograph, book-chapter, reference-entry |
| **Tesis/Disertación** | dissertation |
| **Preprint** | preprint |
| **Dataset** | dataset |
| **Otro** | any other non-null value (report, standard, grant, peer-review, paratext, erratum, …) |
| **Sin clasificar** | `null` (not yet captured / not backfilled) |

`work_type.py` exposes: `category_for(raw: str | None) -> str` and
`raw_values_for(category: str) -> list[str] | None` (None ⇒ the IS NULL bucket).
The category↔raw mapping is mirrored in a small TS helper for the badges.

## Components & Changes

### 1. Capture & store
- `backend/schemas_enrichment.py`: `EnrichedRecord` gains
  `work_type: Optional[str] = None`.
- `backend/adapters/enrichment/openalex.py` (`_parse_record`): set
  `work_type=raw_openalex.get("type")` in the `EnrichedRecord(...)` construction.
- `backend/enrichment_worker.py`: write
  `entity.enrichment_work_type = enriched_data.work_type` alongside the other
  `enrichment_*` writes.
- `backend/models.py`: new column
  `enrichment_work_type = Column(String, nullable=True, index=True)` on
  `RawEntity`.
- Alembic migration: add the column + index (single new head).

### 2. Facet (filter)
- `backend/services/entity_service.py`:
  - `_FACET_FIELDS` gains `"work_type": models.RawEntity.enrichment_work_type`.
  - `get_facets` special-cases `work_type`: aggregate raw counts, then fold into
    categories via `work_type.category_for`, returning
    `[{value: "Libro", count: N}, …, {value: "Sin clasificar", count: M}]`.
  - Add `ft_work_type` to the filter signature; when present, translate the
    category to a WHERE clause: `raw_values_for(cat)` → `IN (...)`, or
    `enrichment_work_type IS NULL` for "Sin clasificar".
- `backend/routers/entities.py`: add `ft_work_type: Optional[str]` query param to
  the entities list and facets routes; thread it through.

### 3. Frontend facet
- `frontend/app/components/FacetPanel.tsx`: add `work_type` to `FIELD_LABELS`
  (i18n key `page.import.field.work_type`), `FIELD_COLORS`, `FIELD_ORDER` (after
  `entity_type`), and the `ft_work_type` query-param wiring. No structural change —
  the panel already renders any field in `FIELD_ORDER`.

### 4. Badges
- New TS helper (e.g. `frontend/app/lib/workType.ts`): `categoryFor(raw)` mirroring
  `work_type.py`, returning the display category (i18n key) or null.
- `EntityTableDetailsModal.tsx`: render a type `Badge` near the header when the
  entity has `enrichment_work_type`.
- `EntityTable.tsx` (row rendering): render the same type `Badge` in the row.
- Use the governed `Badge` UI primitive; no raw palette classes.

### 5. Backfill
- `backend/scripts/backfill_work_type.py`: re-query OpenAlex by DOI/OpenAlex id
  (pattern of #84 / `backfill_nif_bayes`), set `enrichment_work_type`. Org-scoped,
  idempotent, injectable adapter for tests, optional throttle.

### 6. i18n
- New keys: `page.import.field.work_type` and the category labels, EN + ES. The
  repo's translation gate requires both locales.

## Data Flow

No new endpoints. Capture rides the existing enrichment write path. The facet
reuses `GET /entities/facets` and the entities list filter; `ft_work_type` maps a
display category to raw values server-side. Badges read `enrichment_work_type`
already returned with the entity and map to a category client-side.

## Null / Edge Handling

- `enrichment_work_type` is nullable. Pre-backfill (and for non-OpenAlex sources)
  it is `null` → facet bucket "Sin clasificar"; badge hidden (or a muted
  "Sin clasificar"). Silent, no errors.
- Unknown/未mapped raw values → "Otro" (never dropped).
- `ft_work_type=Sin clasificar` filters `IS NULL`.

## Testing

**Backend (pytest):**
- `work_type.py`: `category_for` for representative raws + null; `raw_values_for`
  round-trips; unknown raw → "Otro".
- Adapter: `_parse_record` captures `type` into `EnrichedRecord.work_type`.
- `get_facets`: raw counts fold into category buckets incl. "Sin clasificar".
- Filter: `ft_work_type=Libro` returns only book-family rows; `=Sin clasificar`
  returns null rows; invalid category → empty/ignored (define explicitly).
- Backfill: populates `enrichment_work_type` from an injected adapter.

**Frontend (Vitest):**
- FacetPanel shows the "Tipo de obra" facet and fires `ft_work_type` on select.
- Badge renders the right category for a raw value and is hidden/"Sin clasificar"
  when null.

**Gates:** ESLint `--max-warnings=0` on changed files, tsc, translation gate
(EN+ES), Design-System gate (governed `Badge`), single Alembic head.

## Risks

- Low–medium. Additive column + facet following an established pattern. Main care
  points: the category mapping staying in sync between Python and TS (mitigated by
  a single table in this spec + focused tests), and the facet aggregation
  special-casing (covered by tests).

## Deferred (not in this spec)

- Backfilling production data (operational; run the script post-deploy).
- Using `type_crossref` or `type` sub-distinctions beyond the broad categories.
- Analytics/dashboard breakdowns by work type.
