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

**Categories are stable string codes** (locale-independent), localized to display
labels in the frontend (i18n keys `page.work_type.<code>`, EN+ES). The backend
never returns Spanish; it returns codes. The badges + facet labels translate them.

| Category code | Raw OpenAlex `type` values | ES label | EN label |
|---------------|----------------------------|----------|----------|
| `article` | article, review, letter, editorial | Artículo | Article |
| `book` | book, monograph, book-chapter, reference-entry | Libro | Book |
| `thesis` | dissertation | Tesis/Disertación | Thesis |
| `preprint` | preprint | Preprint | Preprint |
| `dataset` | dataset | Dataset | Dataset |
| `other` | any other non-null value (report, standard, grant, peer-review, paratext, erratum, …) | Otro | Other |
| `unclassified` | `null` (not yet captured / not backfilled) | Sin clasificar | Unclassified |

`work_type.py` exposes: `category_for(raw: str | None) -> str` (returns a code;
`None`/unknown handled — `None`→`"unclassified"`, unmapped→`"other"`) and
`raw_values_for(code: str) -> list[str] | None` (`None` ⇒ the IS NULL /
`unclassified` bucket). The code↔raw mapping is mirrored in a small TS helper
(`workType.ts`); a backend test asserts the two category-code sets match to guard
drift.

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
- **Entity response schema (REQUIRED for badges):** `backend/schemas.py` — add
  `enrichment_work_type: Optional[str] = None` to the entity response model
  (`EntityBase`/`Entity`, the one serialized by `GET /entities`). The frontend
  `Entity` TypeScript interface (`frontend/app/components/EntityTable.types.ts`)
  gains the same field. Without these two, the column is never returned and badges
  read `undefined`. (Note: this is a first-class column, NOT an `attributes_json`
  key — do not add it to `EntityAttributesDict`/`KNOWN_ATTRIBUTE_KEYS`.)

### 2. Facet (filter)
- `backend/services/entity_service.py`:
  - `_FACET_FIELDS` gains `"work_type": models.RawEntity.enrichment_work_type`.
  - `get_facets` **special-cases** `work_type` (the generic path won't work — see
    below): run a SQL `GROUP BY enrichment_work_type` **including NULL** (do NOT
    apply the existing `col != None`/`col != ""` filter for this field), then in
    Python fold the raw-value rows into category codes via `category_for` and **sum
    counts per code** — NULL rows roll into `unclassified`. Return
    `[{value: "book", count: N}, …, {value: "unclassified", count: M}]` (codes,
    not labels). This null bypass is REQUIRED: the generic path strips NULLs, which
    would make `unclassified` always 0.
  - Add `ft_work_type` to **both** `get_facets` and `get_list` signatures. When
    present, translate the code to a WHERE clause: `raw_values_for(code)` →
    `enrichment_work_type IN (...)`, or `enrichment_work_type IS NULL` for
    `unclassified`. An unknown code yields an empty result set (define explicitly).
  - Apply the existing cross-filter guard pattern so the work_type facet's own
    counts aren't filtered by `ft_work_type` (`if ft_work_type and field !=
    "work_type": ...`).
- `backend/routers/entities.py`: add `ft_work_type: Optional[str]` query param to
  the entities list AND facets routes; thread it through to the service.

### 3. Frontend facet
- `frontend/app/components/FacetPanel.tsx`: add `work_type` to `FIELD_LABELS`
  (i18n key `page.import.field.work_type`), `FIELD_COLORS`, `FIELD_ORDER` (after
  `entity_type`), and the `ft_work_type` query-param wiring. Two easily-missed
  details:
  - The `fetchFacets` `useCallback` **dependency array must include
    `activeFacets.work_type`** (it hard-codes each facet's active value), else the
    filter won't react to work_type changes.
  - `translateFacetValue` has per-field branches; add a `work_type` branch that
    maps the category **code** (`book`, `article`, …) to the i18n label key
    `page.work_type.<code>`. (Backend returns codes, not display strings.)

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
category code to raw values server-side. Badges read `enrichment_work_type` from
the entity payload — which requires adding the field to the entity response schema
(`schemas.py`) and the TS `Entity` type (see Components §1); it is NOT returned
today — then map the raw value to a category code (`workType.ts`) and localize.

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
- Filter: `ft_work_type=book` returns only book-family rows; `=unclassified`
  returns NULL rows; an unknown code → empty result set. (Filter values are
  category **codes**, never display labels.)
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
