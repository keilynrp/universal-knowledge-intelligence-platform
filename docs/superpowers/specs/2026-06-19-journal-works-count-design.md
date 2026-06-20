# Journal Works-Count Column — Design Spec

**Date:** 2026-06-19
**Status:** Approved (brainstorming)
**Feature:** Show, per journal, how many works in the catalog reference it (deferred follow-up from the journal-metrics-surfacing work, PR #82).

## Problem

The journals ranking table (`/analytics/journals`) shows NIF, citedness, h-index, APC, OA — but not how many of the org's works actually use each journal. That count is valuable context (a journal backing 500 works vs 1). It was deferred because `issn_l` lives only inside `raw_entities.attributes_json` (a TEXT blob), and extracting it in SQL is non-portable across the prod (Postgres) / test (SQLite) split.

## Approach (locked)

**Denormalize `issn_l` into an indexed column** on `raw_entities`, populated by the enrichment worker going forward and backfilled for existing rows via the migration. Counting is then a portable, indexed `GROUP BY` — no JSON SQL, no per-request blob parsing, scales to any catalog size. Live count (no cache).

## Non-goals (YAGNI)

- **Sorting the ranking by works-count** — the column is displayed but NOT sortable in v1 (sorting on the COUNT needs a subquery/join into the sortable path). Sort options stay `nif|citedness|apc|h_index`.
- FX→USD APC conversion (separate deferred follow-up).

---

## Architecture & components

### 1. Model — `backend/models.py`
Add to `UniversalEntity` (RawEntity), alongside the other `enrichment_*` columns (~line 45):
```python
enrichment_issn_l = Column(String, nullable=True, index=True)
```
Mirrors the `issn_l` the worker already writes into `attributes_json`; indexed for the GROUP BY.

### 2. Migration — `alembic/versions/<rev>_raw_entity_issn_l.py`
- `down_revision = "c4d5e6f7a8b9"` (current single head).
- `upgrade()`: `op.add_column("raw_entities", Column("enrichment_issn_l", String, nullable=True))` + `op.create_index("ix_raw_entities_enrichment_issn_l", "raw_entities", ["enrichment_issn_l"])`. Idempotent guard (`_has_column` via `sa.inspect`) consistent with the repo's migration style.
- **Backfill (portable, Python-side):** within `upgrade()`, use `op.get_bind()` to `SELECT id, attributes_json FROM raw_entities WHERE attributes_json LIKE '%issn_l%'` (cheap pre-filter), `json.loads` each, and `UPDATE raw_entities SET enrichment_issn_l = :v WHERE id = :id` when an `issn_l` key is present. Batch the updates. Skips rows whose JSON is null/unparseable. Works identically on SQLite and Postgres.
- `downgrade()`: drop index + column.

### 3. Worker — `backend/enrichment_worker.py`
At line 654, where it already sets `attrs["issn_l"] = full.issn_l`, also set the column:
```python
attrs["issn_l"] = full.issn_l
entity.enrichment_issn_l = full.issn_l
```
This is inside the journal try/except block, so a failure here still can't abort the work's enrichment.

### 4. Count service — `backend/services/journal_metrics_service.py`
> New imports required at the top of this file: `from sqlalchemy import func` and add `RawEntity` to the `from backend.models import ...` line (currently only `JournalMetric` is imported).
```python
def works_count_by_issn(db, org_id, issns=None) -> dict[str, int]:
    q = (db.query(RawEntity.enrichment_issn_l, func.count(RawEntity.id))
           .filter(RawEntity.enrichment_issn_l.isnot(None))
           .filter(RawEntity.org_id == org_id))
    if issns:
        q = q.filter(RawEntity.enrichment_issn_l.in_(issns))
    return {issn: cnt for issn, cnt in q.group_by(RawEntity.enrichment_issn_l).all()}
```
Org-scoped via `RawEntity.org_id == org_id` (the same value the journal_metrics row and its source entities were written with — consistent scoping; `== None` emits `IS NULL`). Optional `issns` filter so the list endpoint only counts the journals on the current page.

### 5. Schema & API
- `JournalMetricResponse` (`backend/schemas.py`): add `works_count: Optional[int] = None`. (It is NOT an ORM column, so it's populated after `model_validate`.)
- `GET /journals` (`backend/routers/journals.py`): after building the page rows, call `works_count_by_issn(db, org_id, issns=[r.issn_l for r in rows])`, then for each response set `resp.works_count = counts.get(r.issn_l, 0)`.
- `GET /journals/{issn_l}`: the current handler does `return row` (raw ORM row → FastAPI serializes via `response_model`), which gives no chance to attach `works_count`. **Change it to build the model explicitly:** `resp = schemas.JournalMetricResponse.model_validate(row); resp.works_count = works_count_by_issn(db, org_id, issns=[issn_l]).get(issn_l, 0); return resp`. (Otherwise `works_count` silently serializes as `null`.)
- `/journals/stats` is unchanged.

### 6. Frontend
- `JournalsRankingTable.tsx`: add a non-sortable **"Works"** column rendering `works_count` (0/number; "—" when null). Extend the `JournalRow` type with `works_count: number | null`.
- `app/analytics/journals/page.tsx`: extend its row type with `works_count`.
- `JournalMetricsSection.tsx` (modal): show "N works in your catalog" from `works_count` (small, optional line — the single endpoint already returns it).

## Data flow
1. Worker enriches a work → sets `entity.enrichment_issn_l` (+ existing `attributes_json.issn_l`).
2. Migration backfills existing rows so counts are correct immediately on deploy.
3. `GET /journals` → list rows + `works_count_by_issn` for the page → response carries `works_count`.
4. Ranking table renders the "Works" column; modal optionally shows the count.

## Error handling
- Migration backfill skips null/unparseable `attributes_json` (no hard failure).
- Count service returns `{}` when no rows; missing issn → `works_count` defaults to 0 in the router.
- Worker column-set is inside the existing journal try/except (non-essential; never aborts work enrichment).

## Testing
- **Backend (pytest):** migration adds column+index and backfills from `attributes_json`; `works_count_by_issn` returns correct counts and is org-isolated (org A's entities don't count toward org B); `GET /journals` includes `works_count` per row (page-scoped); `GET /journals/{issn_l}` includes `works_count`; worker sets `enrichment_issn_l`.
- **Frontend (vitest):** ranking table renders the Works count; modal shows the count line.
- **Gates:** pre-push hook (ESLint `--max-warnings=0`, tsc, governance, vitest, pytest) must pass; governed `ui/` primitives only.

## Build order
A. Model + migration (with backfill) → B. worker column-set → C. count service + API wiring → D. frontend column (+ modal line). Each slice independently testable. **Deploy needs `alembic upgrade head`** (this feature DOES add a migration).
