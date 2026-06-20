# Journal Works-Count Column — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show, per journal, how many of the org's works reference it — via a denormalized indexed `enrichment_issn_l` column on `raw_entities`, surfaced as a non-sortable "Works" column in the journals ranking table.

**Architecture:** The enrichment worker already writes `issn_l` into `raw_entities.attributes_json`; we mirror it into an indexed `enrichment_issn_l` column (populated going forward + backfilled by the migration). A portable `GROUP BY` count service feeds a new `works_count` field on `JournalMetricResponse`, which both journal read endpoints attach. The frontend ranking table renders the count.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest (backend); Next.js/React, vitest (frontend).

**Spec:** `docs/superpowers/specs/2026-06-19-journal-works-count-design.md`

**Anchors verified on branch `feat/journal-works-count` (from main 0475adf):**
- Model: `UniversalEntity` (alias `RawEntity`) in `backend/models.py`; `enrichment_*` cols end ~line 51 (`enrichment_failure_reason`); `org_id` at line 27.
- Alembic single head: `c4d5e6f7a8b9`. Migration style: `from __future__ import annotations`, `_has_table`/`_has_column` guard via `sa.inspect(bind)`, `revision`/`down_revision` module vars (see `alembic/versions/c4d5e6f7a8b9_journal_metrics.py`).
- Worker: `backend/enrichment_worker.py:654` `attrs["issn_l"] = full.issn_l` (inside `if full.issn_l:` within the journal `try/except`; `entity` in scope).
- Service: `backend/services/journal_metrics_service.py` (`get_journal_metric`, `list_journal_metrics`, `journal_stats`); imports currently `from sqlalchemy.orm import Session` and `from backend.models import JournalMetric` — MUST add `from sqlalchemy import func` and `RawEntity` to the models import.
- Router: `backend/routers/journals.py` — `list_journals` returns `[JournalMetricResponse.model_validate(r) for r in rows]` (line 50); `get_journal` returns the ORM row (line 63 `return row`).
- Schema: `JournalMetricResponse` in `backend/schemas.py` (Pydantic v2, `from_attributes=True`).
- Frontend: `frontend/app/analytics/journals/JournalsRankingTable.tsx` (`interface JournalRow` ~line 14; `<table>` with `<th>` headers; cells render `journal.<field>`); `frontend/app/analytics/journals/page.tsx` (row type); `frontend/app/components/JournalMetricsSection.tsx` (modal, local `JournalMetricResponse` interface).
- Test env: backend `D:\universal-knowledge-intelligence-platform\.venv\Scripts\python`, run pytest from worktree root, CI gate `pytest backend/tests/`; conftest `db_session`, `client`, `auth_headers`, `session_factory`. Frontend: tests in `frontend/__tests__/`, runner `vitest`; needs `npm ci` in `frontend/`. Governance gate `npm run design-system:check` (governed `ui/` primitives only). Pre-push hook `scripts/pre-push-check.sh` runs ESLint `--max-warnings=0` + tsc + lints + vitest + pytest.

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `backend/models.py` | `enrichment_issn_l` column on RawEntity | Modify |
| `alembic/versions/<rev>_raw_entity_issn_l.py` | add column+index + backfill | Create |
| `backend/enrichment_worker.py` | set `entity.enrichment_issn_l` | Modify |
| `backend/services/journal_metrics_service.py` | `works_count_by_issn` | Modify |
| `backend/schemas.py` | `works_count` on `JournalMetricResponse` | Modify |
| `backend/routers/journals.py` | attach `works_count` (list + single) | Modify |
| `backend/tests/test_journal_works_count.py` | backend tests | Create |
| `frontend/app/analytics/journals/JournalsRankingTable.tsx` | "Works" column | Modify |
| `frontend/app/analytics/journals/page.tsx` | row type `works_count` | Modify |
| `frontend/app/components/JournalMetricsSection.tsx` | modal count line | Modify |
| `frontend/__tests__/JournalsRankingTable.test.tsx` | column test | Modify |

---

# SLICE A — Model + migration (with backfill)

## Task 1: `enrichment_issn_l` column + migration

**Files:**
- Modify: `backend/models.py`
- Create: `alembic/versions/c5e6f7a8b9c0_raw_entity_issn_l.py`
- Test: `backend/tests/test_journal_works_count.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_journal_works_count.py
import json
import pathlib
import re

from backend.models import RawEntity


def test_raw_entity_has_enrichment_issn_l(db_session):
    e = RawEntity(primary_label="W", enrichment_issn_l="0028-0836")
    db_session.add(e); db_session.commit()
    assert db_session.query(RawEntity).filter_by(enrichment_issn_l="0028-0836").count() == 1


def test_single_alembic_head_after_migration():
    versions = pathlib.Path("alembic/versions")
    revs, downs = set(), set()
    for f in versions.glob("*.py"):
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)', t, re.M):
            revs.add(m.group(1))
        for m in re.finditer(r'down_revision[^=]*=\s*["\(]?["\']?([^"\'\),\s]+)', t, re.M):
            downs.add(m.group(1))
    heads = revs - downs
    assert heads == {"c5e6f7a8b9c0"}, f"expected single head c5e6f7a8b9c0, got {heads}"
```

- [ ] **Step 2: Run → FAIL** (`AttributeError` enrichment_issn_l / head mismatch).
Run: `D:\universal-knowledge-intelligence-platform\.venv\Scripts\python -m pytest backend/tests/test_journal_works_count.py -v`

- [ ] **Step 3a: Model** — in `backend/models.py`, add to `UniversalEntity` next to the other `enrichment_*` columns:
```python
    enrichment_issn_l = Column(String, nullable=True, index=True)
```

- [ ] **Step 3b: Migration** — create `alembic/versions/c5e6f7a8b9c0_raw_entity_issn_l.py`:
```python
"""raw_entities.enrichment_issn_l for per-journal works count

Revision ID: c5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "c5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None

_TABLE = "raw_entities"
_COL = "enrichment_issn_l"
_IX = "ix_raw_entities_enrichment_issn_l"


def _has_column(bind, table: str, col: str) -> bool:
    return any(c["name"] == col for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, _TABLE, _COL):
        op.add_column(_TABLE, sa.Column(_COL, sa.String(), nullable=True))
        op.create_index(_IX, _TABLE, [_COL])

    # Backfill from attributes_json (portable; parse in Python).
    rows = bind.execute(sa.text(
        "SELECT id, attributes_json FROM raw_entities "
        "WHERE attributes_json LIKE '%issn_l%'"
    )).fetchall()
    for row_id, raw in rows:
        if not raw:
            continue
        try:
            issn = json.loads(raw).get("issn_l")
        except (ValueError, TypeError):
            continue
        if issn:
            bind.execute(
                sa.text("UPDATE raw_entities SET enrichment_issn_l = :v WHERE id = :id"),
                {"v": issn, "id": row_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, _TABLE, _COL):
        op.drop_index(_IX, table_name=_TABLE)
        op.drop_column(_TABLE, _COL)
```

- [ ] **Step 4: Run → PASS.** Then verify the migration applies + backfills against in-memory SQLite (env.py needs Postgres, so do NOT run `alembic upgrade head`; instead apply `upgrade()` directly like the journal_metrics migration was validated):
```python
# scratch check (run via python -c or a throwaway script, do not commit):
# create engine sqlite://, create raw_entities with attributes_json containing issn_l,
# run upgrade(), assert enrichment_issn_l populated, run downgrade().
```
Confirm `D:\universal-knowledge-intelligence-platform\.venv\Scripts\python -m alembic heads` shows single head `c5e6f7a8b9c0`.

- [ ] **Step 5: Commit**
```bash
git add backend/models.py alembic/versions/c5e6f7a8b9c0_raw_entity_issn_l.py backend/tests/test_journal_works_count.py
git commit -m "feat(journals): enrichment_issn_l column + backfill migration"
```

> Backfill verification detail: write a small test (in the same test file) that imports the migration module, runs `upgrade()` against an in-memory SQLite engine pre-seeded with a `raw_entities` row whose `attributes_json` is `{"issn_l": "X"}`, and asserts the column is populated — mirroring how `c4d5e6f7a8b9` was validated. Keep it portable.

---

# SLICE B — Worker sets the column

## Task 2: Worker writes `enrichment_issn_l`

**Files:**
- Modify: `backend/enrichment_worker.py` (line ~654)
- Test: `backend/tests/test_journal_works_count.py`

- [ ] **Step 1: Write the failing test** — drive the real `enrich_single_record` like `test_journal_metrics_worker.py` does (read that file for the monkeypatch pattern: patch `_ACTIVE_CASCADE=["openalex"]`, `adapter_openalex.search_by_title` → `[enriched]`, `adapter_openalex.fetch_source_metrics` → a `JournalMetrics`). After enrichment, assert `entity.enrichment_issn_l == "0028-0836"`.

```python
def test_worker_sets_enrichment_issn_l(db_session, monkeypatch):
    from backend import enrichment_worker
    from backend.schemas_enrichment import EnrichedRecord, JournalMetrics
    entity = RawEntity(primary_label="Some Paper", domain="science", enrichment_status="pending")
    db_session.add(entity); db_session.commit()
    enriched = EnrichedRecord(title="Some Paper", citation_count=1,
                              journal=JournalMetrics(issn_l="0028-0836", source_id="S77"))
    monkeypatch.setattr(enrichment_worker, "_ACTIVE_CASCADE", ["openalex"])
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "search_by_title",
                        lambda query, limit=1: [enriched])
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "fetch_source_metrics",
                        lambda sid: JournalMetrics(issn_l="0028-0836", source_id=sid,
                                                   two_yr_mean_citedness=1.0, is_in_doaj=False))
    enrichment_worker.enrich_single_record(db_session, entity)
    db_session.refresh(entity)
    assert entity.enrichment_issn_l == "0028-0836"
```

- [ ] **Step 2: Run → FAIL** (column stays None).
- [ ] **Step 3: Implement** — in `backend/enrichment_worker.py`, at line 654 inside the `if full.issn_l:` block:
```python
                        attrs["issn_l"] = full.issn_l
                        entity.enrichment_issn_l = full.issn_l
```
- [ ] **Step 4: Run → PASS.** Also run `... -k "enrich or journal" -q` for no regression.
- [ ] **Step 5: Commit** — `feat(journals): worker denormalizes issn_l onto entity`.

---

# SLICE C — Count service + API wiring

## Task 3: `works_count_by_issn` service

**Files:**
- Modify: `backend/services/journal_metrics_service.py`
- Test: `backend/tests/test_journal_works_count.py`

- [ ] **Step 1: Write the failing tests**
```python
from backend.models import JournalMetric  # noqa
from backend.services.journal_metrics_service import works_count_by_issn


def test_works_count_by_issn_org_scoped(db_session):
    db_session.add(RawEntity(primary_label="a", org_id=1, enrichment_issn_l="X"))
    db_session.add(RawEntity(primary_label="b", org_id=1, enrichment_issn_l="X"))
    db_session.add(RawEntity(primary_label="c", org_id=1, enrichment_issn_l="Y"))
    db_session.add(RawEntity(primary_label="d", org_id=2, enrichment_issn_l="X"))  # other org
    db_session.commit()
    counts = works_count_by_issn(db_session, 1)
    assert counts == {"X": 2, "Y": 1}


def test_works_count_filtered_by_issns(db_session):
    db_session.add(RawEntity(primary_label="a", org_id=None, enrichment_issn_l="X"))
    db_session.add(RawEntity(primary_label="b", org_id=None, enrichment_issn_l="Z"))
    db_session.commit()
    assert works_count_by_issn(db_session, None, issns=["X"]) == {"X": 1}
```

- [ ] **Step 2: Run → FAIL** (ImportError).
- [ ] **Step 3: Implement** — add imports `from sqlalchemy import func` and `RawEntity` to the `from backend.models import ...` line; then:
```python
def works_count_by_issn(db: Session, org_id: Optional[int],
                        issns: Optional[list[str]] = None) -> dict[str, int]:
    q = (db.query(RawEntity.enrichment_issn_l, func.count(RawEntity.id))
           .filter(RawEntity.enrichment_issn_l.isnot(None))
           .filter(RawEntity.org_id == org_id))
    if issns:
        q = q.filter(RawEntity.enrichment_issn_l.in_(issns))
    return {issn: cnt for issn, cnt in q.group_by(RawEntity.enrichment_issn_l).all()}
```
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `feat(journals): works_count_by_issn org-scoped count service`.

## Task 4: `works_count` on schema + both endpoints

**Files:**
- Modify: `backend/schemas.py`, `backend/routers/journals.py`
- Test: `backend/tests/test_journal_works_count.py`

- [ ] **Step 1: Write the failing tests** (HTTP-level, using `client`+`auth_headers`)
```python
def test_list_includes_works_count(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="0028-0836", normalized_impact_factor=1.5))
    db_session.add(RawEntity(primary_label="w1", org_id=None, enrichment_issn_l="0028-0836"))
    db_session.add(RawEntity(primary_label="w2", org_id=None, enrichment_issn_l="0028-0836"))
    db_session.commit()
    r = client.get("/journals", headers=auth_headers)
    assert r.status_code == 200
    row = next(j for j in r.json() if j["issn_l"] == "0028-0836")
    assert row["works_count"] == 2


def test_single_includes_works_count(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="0028-0836"))
    db_session.add(RawEntity(primary_label="w1", org_id=None, enrichment_issn_l="0028-0836"))
    db_session.commit()
    r = client.get("/journals/0028-0836", headers=auth_headers)
    assert r.status_code == 200 and r.json()["works_count"] == 1
```

- [ ] **Step 2: Run → FAIL** (`works_count` missing / null).
- [ ] **Step 3a: Schema** — in `backend/schemas.py` `JournalMetricResponse`, add `works_count: Optional[int] = None` (before `model_config`).
- [ ] **Step 3b: Router** — `backend/routers/journals.py`:
  - import `works_count_by_issn` alongside the other service imports.
  - `list_journals`: replace the return with:
    ```python
    items = [schemas.JournalMetricResponse.model_validate(r) for r in rows]
    counts = works_count_by_issn(db, org_id, issns=[r.issn_l for r in rows])
    for it in items:
        it.works_count = counts.get(it.issn_l, 0)
    return items
    ```
  - `get_journal`: replace `return row` with:
    ```python
    resp = schemas.JournalMetricResponse.model_validate(row)
    resp.works_count = works_count_by_issn(db, org_id, issns=[issn_l]).get(issn_l, 0)
    return resp
    ```
- [ ] **Step 4: Run → PASS.** Then `... -k journal -q` for no regression (existing journal tests must stay green; `works_count` defaults to 0 where no entities).
- [ ] **Step 5: Commit** — `feat(journals): expose works_count on journal read endpoints`.

---

# SLICE D — Frontend "Works" column

## Task 5: Ranking table column (+ modal line)

**Files:**
- Modify: `frontend/app/analytics/journals/JournalsRankingTable.tsx`, `frontend/app/analytics/journals/page.tsx`, `frontend/app/components/JournalMetricsSection.tsx`
- Test: `frontend/__tests__/JournalsRankingTable.test.tsx`

Read first: `JournalsRankingTable.tsx` (its `JournalRow` interface + the `<th>`/cell pattern), and the existing `__tests__/JournalsRankingTable.test.tsx`.

- [ ] **Step 1: Update the failing test** — add `works_count` to the test fixture row and assert the table renders it:
```tsx
// in the existing rows fixture add: works_count: 42
test("renders the works count", () => {
  render(<JournalsRankingTable journals={rows} sortBy="nif" order="desc" onSort={() => {}} />);
  expect(screen.getByText("42")).toBeInTheDocument();
});
```
- [ ] **Step 2: Run → FAIL** — `cd frontend && npx vitest run __tests__/JournalsRankingTable.test.tsx`.
- [ ] **Step 3: Implement**
  - `JournalsRankingTable.tsx`: add `works_count: number | null;` to `interface JournalRow`; add a **non-sortable** "Works" `<th>` (plain header, matching the non-sortable Subfield/OA header style — NOT a `<button>`) and a cell rendering `journal.works_count ?? "—"`. Governed token classes only.
  - `page.tsx`: add `works_count: number | null;` to its journal row type so the data flows through.
  - `JournalMetricsSection.tsx`: add `works_count?: number | null` to its local `JournalMetricResponse` interface and render a small line like `{data.works_count} works in your catalog` when present (governed classes).
- [ ] **Step 4: Verify**
  - `npx vitest run __tests__/JournalsRankingTable.test.tsx` → pass; `npx vitest run` → full suite green.
  - `npm run design-system:check` → passes. `npx tsc --noEmit` → clean. `npx eslint --max-warnings=0` on the 3 changed files → clean.
- [ ] **Step 5: Commit** — `feat(journals-ui): works count column + modal line`.

---

## Task 6: Full verification

- [ ] **Step 1: Backend** — `D:\universal-knowledge-intelligence-platform\.venv\Scripts\python -m pytest backend/tests/ -k "journal or enrich or metadata_contract" -q` → green; confirm single Alembic head `c5e6f7a8b9c0`.
- [ ] **Step 2: Frontend** — `cd frontend && npx vitest run` + `npm run design-system:check` + `npx tsc --noEmit` → all clean.
- [ ] **Step 3: Preview (optional)** — if practical, start the dev server and confirm the Works column renders on `/analytics/journals`.
- [ ] **Step 4:** Rely on the pre-push hook (`scripts/pre-push-check.sh`) to gate the push.

---

## Deploy note
This feature **adds a migration** (`c5e6f7a8b9c0`) → after merge, run `alembic upgrade head` on prod Postgres. The backfill runs inside the migration, so counts are correct immediately.

## Deferred (YAGNI)
- Sorting the ranking by works-count (needs the COUNT in the sortable query path).
- FX→USD APC conversion (separate follow-up).
