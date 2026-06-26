# OpenAlex Work-Type Facet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture OpenAlex `work.type` during enrichment, store it on `raw_entities`, and expose it as a grouped "work type" sidebar facet plus type badges in the entity table and detail modal.

**Architecture:** A raw `enrichment_work_type` column captured on the existing enrichment write path; a single Python module (`work_type.py`) maps raw values → stable category codes (article/book/thesis/preprint/dataset/other/unclassified), mirrored by a TS helper; the existing facet system (`get_facets`/`FacetPanel`) gains a `work_type` field with a NULL-aware category-folding special case; badges read a new entity-payload field.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, pytest (backend); Next.js, React, TypeScript, Vitest (frontend).

**Spec:** `docs/superpowers/specs/2026-06-26-openalex-work-type-facet-design.md`

**Branch:** `feat/work-type-facet` (off `main` @ `e110beb`).

**Python env:** `.venv/Scripts/python`. **Frontend:** run from `frontend/`.

**Category codes (single source of truth):**
| code | raw OpenAlex `type` values |
|------|----------------------------|
| `article` | article, review, letter, editorial |
| `book` | book, monograph, book-chapter, reference-entry |
| `thesis` | dissertation |
| `preprint` | preprint |
| `dataset` | dataset |
| `other` | any other non-null value |
| `unclassified` | NULL |

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/services/work_type.py` | Create | raw↔code mapping + SQLAlchemy filter builder |
| `backend/tests/test_work_type.py` | Create | mapping + filter tests |
| `backend/schemas_enrichment.py` | Modify | `EnrichedRecord.work_type` field |
| `backend/adapters/enrichment/openalex.py` | Modify | capture `type` in `_parse_record` (~line 285) |
| `backend/enrichment_worker.py` | Modify | write `enrichment_work_type` (~line 582) |
| `backend/models.py` | Modify | `RawEntity.enrichment_work_type` column |
| `backend/schemas.py` | Modify | `EntityBase.enrichment_work_type` (line 77-88) |
| `backend/migrations/versions/*` | Create | add column + index |
| `backend/services/entity_service.py` | Modify | `_FACET_FIELDS`, `get_facets` special-case, `get_list` filter, `ft_work_type` params |
| `backend/routers/entities.py` | Modify | `ft_work_type` query param on list + facets routes |
| `backend/scripts/backfill_work_type.py` | Create | optional backfill |
| `frontend/app/lib/workType.ts` | Create | TS mirror of category mapping |
| `frontend/app/components/EntityTable.types.ts` | Modify | `Entity.enrichment_work_type` |
| `frontend/app/components/FacetPanel.tsx` | Modify | facet field + wiring + translate branch |
| `frontend/app/components/EntityTable.tsx` | Modify | row type badge |
| `frontend/app/components/EntityTableDetailsModal.tsx` | Modify | header type badge |
| `frontend/app/i18n/translations.ts` | Modify | EN+ES keys |
| backend/frontend test files | Create/Modify | per task |

---

### Task 1: `work_type` category module

**Files:**
- Create: `backend/services/work_type.py`
- Test: `backend/tests/test_work_type.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_work_type.py`:

```python
from backend.services import work_type as wt


def test_category_for_known_and_groups():
    assert wt.category_for("article") == "article"
    assert wt.category_for("review") == "article"
    assert wt.category_for("book") == "book"
    assert wt.category_for("monograph") == "book"
    assert wt.category_for("book-chapter") == "book"
    assert wt.category_for("dissertation") == "thesis"
    assert wt.category_for("preprint") == "preprint"
    assert wt.category_for("dataset") == "dataset"


def test_category_for_null_and_unknown():
    assert wt.category_for(None) == "unclassified"
    assert wt.category_for("standard") == "other"        # non-null, unmapped
    assert wt.category_for("REPORT") == "other"
    assert wt.category_for("  Article ") == "article"     # normalized


def test_category_codes_complete():
    assert wt.CATEGORY_CODES == [
        "article", "book", "thesis", "preprint", "dataset", "other", "unclassified",
    ]
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/Scripts/python -m pytest backend/tests/test_work_type.py -q`
Expected: ImportError / module not found.

- [ ] **Step 3: Implement the module**

Create `backend/services/work_type.py`:

```python
"""Map OpenAlex raw `work.type` values to stable, locale-independent category
codes used by the work-type facet, filter, and badges. Single source of truth;
mirrored by frontend/app/lib/workType.ts (kept in sync by test_work_type_parity)."""
from typing import Optional

from sqlalchemy import and_, func

# Stable display order of category codes (frontend localizes them).
CATEGORY_CODES = ["article", "book", "thesis", "preprint", "dataset", "other", "unclassified"]

# Explicit raw->code mapping. Keys are lowercase OpenAlex `type` values.
_RAW_TO_CODE = {
    "article": "article", "review": "article", "letter": "article", "editorial": "article",
    "book": "book", "monograph": "book", "book-chapter": "book", "reference-entry": "book",
    "dissertation": "thesis",
    "preprint": "preprint",
    "dataset": "dataset",
}
_KNOWN_RAWS = set(_RAW_TO_CODE)  # all explicitly-mapped raw values (lowercase)


def category_for(raw: Optional[str]) -> str:
    """Return the category code for a raw OpenAlex type. None -> 'unclassified',
    unmapped non-null -> 'other'."""
    if raw is None:
        return "unclassified"
    return _RAW_TO_CODE.get(raw.strip().lower(), "other")


def work_type_filter(col, code: str):
    """Return a SQLAlchemy boolean expression selecting rows in `code`, or None if
    `code` is not a known category. `col` is RawEntity.enrichment_work_type."""
    if code == "unclassified":
        return col.is_(None)
    if code == "other":
        return and_(col.isnot(None), func.lower(col).notin_(_KNOWN_RAWS))
    raws = [r for r, c in _RAW_TO_CODE.items() if c == code]
    if not raws:
        return None
    return func.lower(col).in_(raws)
```

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/Scripts/python -m pytest backend/tests/test_work_type.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/work_type.py backend/tests/test_work_type.py
git commit -m "feat(entities): work_type category mapping module"
```

---

### Task 2: Capture & store `work.type`

**Files:**
- Modify: `backend/schemas_enrichment.py` (`EnrichedRecord`, after `venue`/`journal` fields ~line 70)
- Modify: `backend/adapters/enrichment/openalex.py` (`_parse_record` return, ~line 285)
- Modify: `backend/enrichment_worker.py` (~line 582)
- Modify: `backend/models.py` (`RawEntity`)
- Modify: `backend/schemas.py` (`EntityBase`, line 84-88)
- Create: Alembic migration
- Modify: `frontend/app/components/EntityTable.types.ts` (`Entity`)
- Test: `backend/tests/test_work_type_capture.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_work_type_capture.py`:

```python
from backend.adapters.enrichment.openalex import OpenAlexAdapter


def test_parse_record_captures_work_type():
    raw = {
        "id": "https://openalex.org/W1", "display_name": "A Book",
        "type": "book", "publication_year": 2020,
        "authorships": [], "primary_location": {},
    }
    rec = OpenAlexAdapter()._parse_record(raw)
    assert rec.work_type == "book"


def test_entity_response_schema_has_work_type():
    from backend.schemas import EntityBase
    assert "enrichment_work_type" in EntityBase.model_fields
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/Scripts/python -m pytest backend/tests/test_work_type_capture.py -q`
Expected: FAIL (`work_type` attr missing / field missing).

- [ ] **Step 3: Add the `EnrichedRecord` field**

In `backend/schemas_enrichment.py`, inside `EnrichedRecord`, add (near `venue`):
```python
    work_type: Optional[str] = Field(default=None, description="OpenAlex raw work type (article, book, ...)")
```

- [ ] **Step 4: Capture in the adapter**

In `backend/adapters/enrichment/openalex.py` `_parse_record`, add to the `EnrichedRecord(...)` construction (alongside `journal=journal,`):
```python
            work_type=raw_openalex.get("type"),
```
(OpenAlex `/works` returns `type` by default; the existing queries use no `select=`, so it is present.)

- [ ] **Step 5: Add the model column**

In `backend/models.py`, on `RawEntity`, add near the other `enrichment_*` columns:
```python
    enrichment_work_type = Column(String, nullable=True, index=True)
```

- [ ] **Step 6: Write it in the worker**

In `backend/enrichment_worker.py`, in the `if enriched_data:` block (~line 582, next to `entity.enrichment_doi = ...`):
```python
            entity.enrichment_work_type = enriched_data.work_type
```

- [ ] **Step 7: Add to the entity response schema**

In `backend/schemas.py`, in `EntityBase` (after `enrichment_status`, ~line 88):
```python
    enrichment_work_type: Optional[str] = None
```
(`Entity(EntityBase)` uses `from_attributes=True`, so the ORM column is now serialized by `GET /entities`. Do NOT add it to `EntityAttributesDict`/`KNOWN_ATTRIBUTE_KEYS` — it is a first-class column.)

- [ ] **Step 8: Add to the TS Entity type**

In `frontend/app/components/EntityTable.types.ts`, in the `Entity` interface, add:
```typescript
  enrichment_work_type?: string | null;
```

- [ ] **Step 9: Create the migration**

Find the current head: `.venv/Scripts/python -m alembic heads`. Create a new revision whose `down_revision` is that head:

```python
"""add enrichment_work_type to raw_entities"""
from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"          # use any unused id
down_revision = "<CURRENT_HEAD>"    # from `alembic heads`
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("raw_entities") as batch:
        batch.add_column(sa.Column("enrichment_work_type", sa.String(), nullable=True))
    op.create_index("ix_raw_entities_enrichment_work_type", "raw_entities", ["enrichment_work_type"])


def downgrade() -> None:
    op.drop_index("ix_raw_entities_enrichment_work_type", table_name="raw_entities")
    with op.batch_alter_table("raw_entities") as batch:
        batch.drop_column("enrichment_work_type")
```

- [ ] **Step 10: Run — expect PASS + single head**

Run: `.venv/Scripts/python -m pytest backend/tests/test_work_type_capture.py -q`
Then: `.venv/Scripts/python -m alembic heads` → exactly one head.
Expected: PASS, single head.

- [ ] **Step 11: Commit**

```bash
git add backend/schemas_enrichment.py backend/adapters/enrichment/openalex.py backend/models.py backend/enrichment_worker.py backend/schemas.py backend/migrations frontend/app/components/EntityTable.types.ts backend/tests/test_work_type_capture.py
git commit -m "feat(entities): capture OpenAlex work.type into enrichment_work_type"
```

---

### Task 3: Backend facet + filter

**Files:**
- Modify: `backend/services/entity_service.py` (`_FACET_FIELDS`, `get_facets` ~line 26-92, `get_list` ~line 94-137)
- Modify: `backend/routers/entities.py` (list + facets routes)
- Test: `backend/tests/test_work_type_facet.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_work_type_facet.py`:

```python
from backend.models import RawEntity
from backend.services.entity_service import EntityService


def _seed(db, wt, n=1):
    for _ in range(n):
        db.add(RawEntity(primary_label="x", enrichment_work_type=wt))


def test_facets_fold_into_codes_with_nulls(db_session):
    _seed(db_session, "book", 2); _seed(db_session, "monograph", 1)  # -> book:3
    _seed(db_session, "article", 1)
    _seed(db_session, "standard", 1)                                  # -> other:1
    _seed(db_session, None, 2)                                        # -> unclassified:2
    db_session.commit()
    facets = EntityService.get_facets(db_session, "work_type")
    buckets = {d["value"]: d["count"] for d in facets["work_type"]}
    assert buckets["book"] == 3 and buckets["article"] == 1
    assert buckets["other"] == 1 and buckets["unclassified"] == 2


def test_list_filter_by_work_type_code(db_session):
    _seed(db_session, "book"); _seed(db_session, "monograph"); _seed(db_session, "article")
    _seed(db_session, None)
    db_session.commit()
    rows, total = EntityService.get_list(
        db_session, search=None, min_quality=None, sort_by="id", order="asc",
        skip=0, limit=100, ft_entity_type=None, ft_domain=None,
        ft_validation_status=None, ft_enrichment_status=None, ft_source=None,
        concept=None, ft_work_type="book",
    )
    assert total == 2  # book + monograph
    rows_u, total_u = EntityService.get_list(
        db_session, search=None, min_quality=None, sort_by="id", order="asc",
        skip=0, limit=100, ft_entity_type=None, ft_domain=None,
        ft_validation_status=None, ft_enrichment_status=None, ft_source=None,
        concept=None, ft_work_type="unclassified",
    )
    assert total_u == 1  # the NULL row
```

> NOTE: match the real `get_list` signature when wiring the call — read `entity_service.py:94` and pass args positionally/by-keyword exactly as defined. Add `ft_work_type` as a new keyword-with-default at the END of both `get_facets` and `get_list` signatures so existing callers are unaffected.

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/Scripts/python -m pytest backend/tests/test_work_type_facet.py -q`
Expected: FAIL (TypeError unexpected `ft_work_type` / KeyError).

- [ ] **Step 3: Wire the facet field + import**

In `backend/services/entity_service.py`, add at top: `from backend.services import work_type as work_type_mod` and `from collections import Counter`. Add to `_FACET_FIELDS`:
```python
        "work_type":          models.RawEntity.enrichment_work_type,
```

- [ ] **Step 4: `get_facets` — param + null-aware special case**

Add `ft_work_type: Optional[str] = None,` to the `get_facets` signature (end). In the cross-filter block (after the `ft_source` guard), add:
```python
            if ft_work_type and field != "work_type":
                expr = work_type_mod.work_type_filter(models.RawEntity.enrichment_work_type, ft_work_type)
                if expr is not None:
                    query = query.filter(expr)
```
Then, immediately BEFORE the generic `rows = (query.filter(col != None, col != "")...)` block, insert:
```python
            if field == "work_type":
                raw_rows = query.group_by(col).all()  # includes NULLs (no strip)
                buckets = Counter()
                for raw_val, cnt in raw_rows:
                    buckets[work_type_mod.category_for(raw_val)] += cnt
                result[field] = sorted(
                    ({"value": code, "count": n} for code, n in buckets.items()),
                    key=lambda d: -d["count"],
                )
                continue
```

- [ ] **Step 5: `get_list` — param + filter**

Add `ft_work_type: Optional[str] = None,` to the `get_list` signature (end). In its filter block (after `ft_source`), add:
```python
        if ft_work_type:
            expr = work_type_mod.work_type_filter(models.RawEntity.enrichment_work_type, ft_work_type)
            query = query.filter(expr) if expr is not None else query.filter(sa.false())
```
(Add `import sqlalchemy as sa` at top if not present, or use `from sqlalchemy import false`.)

- [ ] **Step 6: Router params + default facet fields (REQUIRED)**

In `backend/routers/entities.py`:
- Add `ft_work_type: Optional[str] = Query(default=None)` to BOTH the entities-list route and the `/entities/facets` route, and pass `ft_work_type=ft_work_type` into the corresponding `EntityService.get_list(...)` / `get_facets(...)` calls.
- **Add `work_type` to the facets route's default `fields` string** (currently
  `fields: str = Query(default="entity_type,domain,validation_status,enrichment_status,source")`):
  ```python
  fields: str = Query(default="entity_type,domain,validation_status,enrichment_status,source,work_type")
  ```
  Without this the facet never appears in the response — `FacetPanel` sends no
  `fields` param, so the route default is what's used.

- [ ] **Step 7: Run — expect PASS**

Run: `.venv/Scripts/python -m pytest backend/tests/test_work_type_facet.py backend/tests/test_work_type.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/services/entity_service.py backend/routers/entities.py backend/tests/test_work_type_facet.py
git commit -m "feat(entities): work_type facet + ft_work_type filter (NULL-aware category folding)"
```

---

### Task 4: Frontend facet panel + i18n

**Files:**
- Create: `frontend/app/lib/workType.ts`
- Modify: `frontend/app/components/FacetPanel.tsx`
- Modify: `frontend/app/i18n/translations.ts`
- Test: `frontend/__tests__/FacetPanel.test.tsx` (create if absent)

- [ ] **Step 1: Create the TS mapping mirror**

Create `frontend/app/lib/workType.ts`:
```typescript
// Mirror of backend/services/work_type.py. Keep in sync.
const RAW_TO_CODE: Record<string, string> = {
  article: "article", review: "article", letter: "article", editorial: "article",
  book: "book", monograph: "book", "book-chapter": "book", "reference-entry": "book",
  dissertation: "thesis", preprint: "preprint", dataset: "dataset",
};

export const WORK_TYPE_CODES = [
  "article", "book", "thesis", "preprint", "dataset", "other", "unclassified",
] as const;

export function categoryFor(raw: string | null | undefined): string {
  if (raw == null) return "unclassified";
  return RAW_TO_CODE[raw.trim().toLowerCase()] ?? "other";
}
```

- [ ] **Step 2: Write the failing FacetPanel test**

Read the existing FacetPanel test pattern first (or another `frontend/__tests__/*.test.tsx`). Add a test asserting the panel renders a "work_type"/"Tipo de obra" facet when `facetsData` includes it and fires `onFacetChange("work_type", "book")` on click. (Mirror the existing facet-render test in this repo; if none, render `<FacetPanel>` with `facetsData={{ work_type: [{value:"book",count:3}] }}` and assert the localized label + a click handler call.)

- [ ] **Step 3: Run — expect FAIL**

Run: `cd frontend && npx vitest run __tests__/FacetPanel.test.tsx`
Expected: FAIL.

- [ ] **Step 4: Wire the facet into FacetPanel**

In `frontend/app/components/FacetPanel.tsx`:
- `FIELD_LABELS`: add `work_type: "page.import.field.work_type",`
- `FIELD_COLORS`: add `work_type: "text-fuchsia-700 dark:text-fuchsia-200",` (use an existing token-style class consistent with the others)
- `FIELD_ORDER`: insert `"work_type"` after `"entity_type"`
- In `fetchFacets`, add `if (activeFacets.work_type) queryParams.append("ft_work_type", activeFacets.work_type);` and add `activeFacets.work_type` to the `useCallback` dependency array.
- In `translateFacetValue`, add a branch: `if (field === "work_type") return t(\`page.work_type.${value}\`);` (the backend returns codes).

- [ ] **Step 5: Add i18n keys (EN + ES)**

In `frontend/app/i18n/translations.ts`, add under both locales:
- `page.import.field.work_type`: EN "Work type" / ES "Tipo de obra"
- `page.work_type.article` … `page.work_type.unclassified`:
  EN: Article / Book / Thesis / Preprint / Dataset / Other / Unclassified
  ES: Artículo / Libro / Tesis / Preprint / Dataset / Otro / Sin clasificar

- [ ] **Step 6: Run — expect PASS**

Run: `cd frontend && npx vitest run __tests__/FacetPanel.test.tsx`
Then ESLint on touched files: `cd frontend && npx eslint app/components/FacetPanel.tsx app/lib/workType.ts __tests__/FacetPanel.test.tsx --max-warnings=0`
Expected: PASS, lint clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/lib/workType.ts frontend/app/components/FacetPanel.tsx frontend/app/i18n/translations.ts frontend/__tests__/FacetPanel.test.tsx
git commit -m "feat(entities): work type facet in side panel + i18n"
```

---

### Task 5: Type badges (table + modal)

**Files:**
- Modify: `frontend/app/components/EntityTable.tsx` (row rendering)
- Modify: `frontend/app/components/EntityTableDetailsModal.tsx` (header)
- Test: extend `frontend/__tests__` for whichever component has a suite

- [ ] **Step 1: Write the failing test**

Add a test (mirror existing component tests) asserting that, given an entity with `enrichment_work_type: "book"`, a badge with the localized "Book"/"Libro" label renders; and that no type badge renders when `enrichment_work_type` is null/undefined.

- [ ] **Step 2: Run — expect FAIL**

Run: `cd frontend && npx vitest run <the test file>`
Expected: FAIL.

- [ ] **Step 3: Render the badge**

Using the governed `Badge` UI primitive and `categoryFor` from `@/app/lib/workType` + `t(\`page.work_type.${code}\`)`:
- In `EntityTableDetailsModal.tsx`, render a small `Badge` near the title/header when `entity.enrichment_work_type` is present (hide when null).
- In `EntityTable.tsx` row, render the same badge in the row (hide when null).
Do NOT use raw palette classes — use `Badge` variants.

- [ ] **Step 4: Run — expect PASS**

Run: `cd frontend && npx vitest run <the test file>`
Then ESLint on touched files `--max-warnings=0`.
Expected: PASS, lint clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/components/EntityTable.tsx frontend/app/components/EntityTableDetailsModal.tsx frontend/__tests__
git commit -m "feat(entities): work type badge in table row + detail modal"
```

---

### Task 6: Optional backfill script

**Files:**
- Create: `backend/scripts/backfill_work_type.py`
- Test: `backend/tests/test_work_type_backfill.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_work_type_backfill.py`:
```python
from backend.models import RawEntity
from backend.scripts.backfill_work_type import run_backfill


def test_backfill_populates_work_type(db_session):
    db_session.add(RawEntity(primary_label="p", enrichment_doi="10.1/x"))
    db_session.commit()

    class _FakeAdapter:
        def search_by_doi(self, doi):
            class R: work_type = "book"
            return R()

    n = run_backfill(db_session, org_id=None, adapter=_FakeAdapter())
    assert n == 1
    assert db_session.query(RawEntity).one().enrichment_work_type == "book"
```

- [ ] **Step 2: Run — expect FAIL** (module missing)

Run: `.venv/Scripts/python -m pytest backend/tests/test_work_type_backfill.py -q`

- [ ] **Step 3: Implement** (pattern of `backend/scripts/backfill_nif_bayes.py`)

Create `backend/scripts/backfill_work_type.py`: iterate `RawEntity` rows with a DOI (and `enrichment_work_type IS NULL`), call `adapter.search_by_doi(doi)`, set `enrichment_work_type = rec.work_type` when present; org-scoped; injectable `adapter` (default `OpenAlexAdapter()`); optional `delay`; `db.commit()`; return count updated. Include a `main()` with `--org-id`/`--delay` argparse like `backfill_nif_bayes.py`.

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/Scripts/python -m pytest backend/tests/test_work_type_backfill.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/backfill_work_type.py backend/tests/test_work_type_backfill.py
git commit -m "feat(entities): optional backfill_work_type script"
```

---

### Task 7: Full verification

- [ ] **Step 1: Backend — work_type surface + entities**

Run: `.venv/Scripts/python -m pytest backend/tests/ -k "work_type or entity or facet or enrichment" -q`
Expected: green.

- [ ] **Step 2: Full backend suite + single head**

Run: `.venv/Scripts/python -m pytest backend/tests/ -q`
Then: `.venv/Scripts/python -m alembic heads` (exactly one).
Expected: green, single head. Per @superpowers:verification-before-completion, do not declare done until this passes.

- [ ] **Step 3: Frontend suite + strict lint + types**

Run: `cd frontend && npm run test && npx eslint . --max-warnings=0 && npx tsc --noEmit`
Expected: all green. ESLint `--max-warnings=0` is the strict pre-push gate.

- [ ] **Step 4: Finish**

Use @superpowers:finishing-a-development-branch. Push + open PR only when the user asks.
> Repo notes: `git push` may hang on Git Credential Manager — the `scripts/pre-push-check.sh` pre-push hook runs gates first; `main` has no branch protection. The translation gate requires EN+ES parity; the Design-System gate requires governed `ui/` primitives.

---

## Deferred (NOT in this plan)
- Running the prod backfill (`python -m backend.scripts.backfill_work_type`) after deploy.
- Analytics/dashboard breakdowns by work type; `type_crossref` sub-distinctions.
