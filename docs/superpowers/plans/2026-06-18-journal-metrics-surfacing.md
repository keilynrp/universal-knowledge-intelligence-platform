# Journal Metrics Surfacing (NIF + APC) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the journal Normalized Impact Factor (NIF) and APC — already stored in `journal_metrics` by the enrichment pipeline — through a read-only API, a per-entity modal section, and a journals analytics dashboard.

**Architecture:** A thin read-only router (`backend/routers/journals.py`) over read helpers in `journal_metrics_service.py` exposes single/list/stats endpoints, all org-scoped via `resolve_request_org_id`. The frontend consumes them in two surfaces: a lazy "Journal" section in `EntityTableDetailsModal`, and a new `analytics/journals` dashboard (ranking table + 2 Recharts charts + admin recompute). A shared `JournalProvenanceBadge` labels the NIF honestly as an open proxy everywhere.

**Tech Stack:** FastAPI, SQLAlchemy, pytest (backend); Next.js 16 / React 19 / Tailwind v4, Recharts, vitest (frontend).

**Spec:** `docs/superpowers/specs/2026-06-18-journal-metrics-surfacing-design.md`

**Anchors verified on branch `feat/journal-metrics-frontend` (from main 735ff0a):**
- Model `JournalMetric` (`backend/models.py`): cols `org_id, issn_l, source_id, display_name, two_yr_mean_citedness, h_index, if_metric_kind, apc_usd (Int), apc_currency, apc_source, is_in_doaj, normalized_impact_factor, nif_field, nif_updated_at`.
- Org scoping helpers: `from backend.tenant_access import resolve_request_org_id, scope_query_to_org` — usage `org_id = resolve_request_org_id(db, current_user)` then `scope_query_to_org(query, models.JournalMetric, org_id)` (see `backend/routers/entities.py`).
- `X-Total-Count` pattern: inject `response: Response` and set `response.headers["X-Total-Count"]` (see `entities.py:120`).
- Router mount: append `app.include_router(journals.router)` near `backend/main.py:472` and add `journals` to the routers import block (~line 41).
- Existing write endpoint `POST /journals/normalize` lives in `analytics_ops.py:442` (leave it there).
- Service: `backend/services/journal_metrics_service.py` (currently only `upsert_journal_metric`).
- Frontend: `apiFetch` from `@/lib/api`; modal `frontend/app/components/EntityTableDetailsModal.tsx` (has `parseJsonObject`); auth `useAuth` from `frontend/app/contexts/AuthContext.tsx` (`user.role`); admin gate pattern `const ADMIN_ROLES = new Set(["admin","super_admin"])` (see `EnrichmentSchedulerCard.tsx`); nav array `navSections` in `frontend/app/components/sidebarNav.tsx`; dashboard pattern `frontend/app/analytics/dashboard/page.tsx` (Recharts + `../../components/ui`: `ErrorBanner`, `SkeletonCard`, `useToast`). Frontend tests: `vitest run` from `frontend/`.
- Test env: backend uses `D:\universal-knowledge-intelligence-platform\.venv\Scripts\python`; run pytest from the worktree root; CI gate = `pytest backend/tests/`. conftest `_TABLES_TO_CLEAN` already includes `journal_metrics`.

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `backend/schemas.py` | `JournalMetricResponse`, `JournalStatsResponse`; `issn_l` in `EntityAttributesDict` | Modify |
| `backend/services/journal_metrics_service.py` | read helpers: `get_journal_metric`, `list_journal_metrics`, `journal_stats` | Modify |
| `backend/routers/journals.py` | read-only router: `/journals/stats`, `/journals/{issn_l}`, `/journals` | Create |
| `backend/main.py` | mount router | Modify |
| `backend/tests/test_journals_api.py` | endpoint tests | Create |
| `frontend/app/components/JournalProvenanceBadge.tsx` | shared provenance badge + `formatApc` util | Create |
| `frontend/app/components/JournalMetricsSection.tsx` | modal "Journal" section (lazy fetch) | Create |
| `frontend/app/components/EntityTableDetailsModal.tsx` | render the section | Modify |
| `frontend/app/analytics/journals/page.tsx` | dashboard page | Create |
| `frontend/app/analytics/journals/JournalsRankingTable.tsx` | ranking table | Create |
| `frontend/app/analytics/journals/JournalsCharts.tsx` | APC distribution + NIF-by-field charts | Create |
| `frontend/app/components/sidebarNav.tsx` | nav item | Modify |
| `frontend/app/analytics/journals/*.test.tsx` | vitest component tests | Create |

---

# SLICE A — Backend read-path

## Task 1: `JournalMetricResponse` + `JournalStatsResponse` schemas + `issn_l` contract fix

**Files:**
- Modify: `backend/schemas.py`
- Test: `backend/tests/test_journals_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_journals_api.py
from backend.schemas import JournalMetricResponse, EntityAttributesDict


def test_journal_metric_response_shape():
    r = JournalMetricResponse(
        issn_l="0028-0836", display_name="Nat", source_id="S77",
        two_yr_mean_citedness=17.4, h_index=1200, normalized_impact_factor=1.5,
        nif_field="Genetics", apc_usd=11690, apc_currency="USD", apc_source="openalex",
        is_in_doaj=False, if_metric_kind="openalex_2yr_mean_citedness", nif_updated_at=None,
    )
    assert r.apc_usd == 11690 and r.nif_field == "Genetics"


def test_issn_l_documented_in_attributes_contract():
    assert "issn_l" in EntityAttributesDict.__annotations__
```

- [ ] **Step 2: Run to verify it fails**

Run: `D:\universal-knowledge-intelligence-platform\.venv\Scripts\python -m pytest backend/tests/test_journals_api.py -v`
Expected: FAIL (ImportError / `issn_l` missing).

- [ ] **Step 3: Implement**

In `backend/schemas.py`, add `issn_l: str` to `EntityAttributesDict` (keeps the metadata-contract test green once the journal path runs). Then add:

```python
class JournalMetricResponse(BaseModel):
    issn_l: str
    display_name: Optional[str] = None
    source_id: Optional[str] = None
    two_yr_mean_citedness: Optional[float] = None
    h_index: Optional[int] = None
    normalized_impact_factor: Optional[float] = None
    nif_field: Optional[str] = None
    apc_usd: Optional[int] = None          # whole currency units, not float
    apc_currency: Optional[str] = None
    apc_source: Optional[str] = None
    is_in_doaj: Optional[bool] = None
    if_metric_kind: Optional[str] = None
    nif_updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JournalApcBucket(BaseModel):
    currency: Optional[str] = None
    count: int
    min: Optional[int] = None
    max: Optional[int] = None
    median: Optional[float] = None


class JournalNifByField(BaseModel):
    nif_field: Optional[str] = None
    journal_count: int
    mean_nif: float


class JournalStatsResponse(BaseModel):
    apc_distribution: list[JournalApcBucket]
    open_access_share: dict   # {"in_doaj": int, "total": int, "pct": float}
    nif_by_field: list[JournalNifByField]
```

Verify `datetime`, `ConfigDict`, `Optional`, `BaseModel` are imported in `schemas.py` (add if missing).

- [ ] **Step 4: Run to verify pass**

Run: `D:\universal-knowledge-intelligence-platform\.venv\Scripts\python -m pytest backend/tests/test_journals_api.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/schemas.py backend/tests/test_journals_api.py
git commit -m "feat(journals): response schemas + issn_l attributes contract"
```

## Task 2: Read helpers in `journal_metrics_service.py`

**Files:**
- Modify: `backend/services/journal_metrics_service.py`
- Test: `backend/tests/test_journals_api.py`

- [ ] **Step 1: Write failing tests** (append)

```python
from backend.models import JournalMetric
from backend.services.journal_metrics_service import (
    get_journal_metric, list_journal_metrics, journal_stats,
)


def _seed(db, issn, nif=None, cited=None, apc=None, cur=None, doaj=None, field=None, org=None):
    db.add(JournalMetric(org_id=org, issn_l=issn, normalized_impact_factor=nif,
                         two_yr_mean_citedness=cited, apc_usd=apc, apc_currency=cur,
                         is_in_doaj=doaj, nif_field=field))


def test_get_journal_metric_scoped(db_session):
    _seed(db_session, "A", org=None); db_session.commit()
    assert get_journal_metric(db_session, None, "A").issn_l == "A"
    assert get_journal_metric(db_session, None, "ZZZ") is None


def test_list_sorted_and_total(db_session):
    _seed(db_session, "A", nif=0.5); _seed(db_session, "B", nif=2.0); db_session.commit()
    rows, total = list_journal_metrics(db_session, None, sort_by="nif", order="desc", limit=10, offset=0)
    assert total == 2 and [r.issn_l for r in rows] == ["B", "A"]


def test_list_org_isolation(db_session):
    _seed(db_session, "A", org=1); _seed(db_session, "B", org=2); db_session.commit()
    rows, total = list_journal_metrics(db_session, 1, sort_by="nif", order="desc", limit=10, offset=0)
    assert total == 1 and rows[0].issn_l == "A"


def test_stats_aggregates(db_session):
    _seed(db_session, "A", cited=2, apc=1000, cur="USD", doaj=True, field="AI", nif=0.5)
    _seed(db_session, "B", cited=6, apc=3000, cur="USD", doaj=False, field="AI", nif=1.5)
    _seed(db_session, "C", apc=900, cur="EUR", doaj=True, field="Genetics", nif=1.0)
    db_session.commit()
    s = journal_stats(db_session, None)
    usd = next(b for b in s["apc_distribution"] if b["currency"] == "USD")
    assert usd["count"] == 2 and usd["min"] == 1000 and usd["max"] == 3000 and usd["median"] == 2000.0
    assert s["open_access_share"] == {"in_doaj": 2, "total": 3, "pct": round(2/3*100, 1)}
    ai = next(f for f in s["nif_by_field"] if f["nif_field"] == "AI")
    assert ai["journal_count"] == 2 and ai["mean_nif"] == 1.0
```

- [ ] **Step 2: Run to verify fail** — `pytest backend/tests/test_journals_api.py -v` → FAIL (ImportError).

- [ ] **Step 3: Implement** (append to the service)

```python
from statistics import median as _median
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from backend.models import JournalMetric

_SORT_COLUMNS = {
    "nif": JournalMetric.normalized_impact_factor,
    "citedness": JournalMetric.two_yr_mean_citedness,
    "apc": JournalMetric.apc_usd,
    "h_index": JournalMetric.h_index,
}


def _scoped(db: Session, org_id: Optional[int]):
    q = db.query(JournalMetric)
    return q.filter(JournalMetric.org_id == org_id)


def get_journal_metric(db: Session, org_id: Optional[int], issn_l: str) -> Optional[JournalMetric]:
    return _scoped(db, org_id).filter(JournalMetric.issn_l == issn_l).first()


def list_journal_metrics(db, org_id, sort_by="nif", order="desc", limit=50, offset=0,
                         field: Optional[str] = None) -> Tuple[list, int]:
    col = _SORT_COLUMNS[sort_by]  # caller validates sort_by; KeyError → 422 upstream
    q = _scoped(db, org_id)
    if field:
        q = q.filter(JournalMetric.nif_field == field)
    total = q.count()
    direction = col.desc() if order == "desc" else col.asc()
    # NULLs last for desc by putting them after; SQLite orders NULLs first by default.
    rows = q.order_by(direction).offset(offset).limit(limit).all()
    return rows, total


def journal_stats(db, org_id) -> dict:
    rows = _scoped(db, org_id).all()
    # APC distribution by currency (Python-side; SQLite lacks MEDIAN)
    by_cur: dict = {}
    for r in rows:
        if r.apc_usd is None:
            continue
        by_cur.setdefault(r.apc_currency, []).append(r.apc_usd)
    apc_distribution = [
        {"currency": cur, "count": len(v), "min": min(v), "max": max(v),
         "median": float(_median(v))}
        for cur, v in sorted(by_cur.items(), key=lambda kv: (kv[0] is None, kv[0]))
    ]
    total = len(rows)
    in_doaj = sum(1 for r in rows if r.is_in_doaj)
    open_access_share = {"in_doaj": in_doaj, "total": total,
                         "pct": round(in_doaj / total * 100, 1) if total else 0.0}
    by_field: dict = {}
    for r in rows:
        if r.normalized_impact_factor is None:
            continue
        by_field.setdefault(r.nif_field, []).append(r.normalized_impact_factor)
    nif_by_field = sorted(
        [{"nif_field": f, "journal_count": len(v), "mean_nif": round(sum(v) / len(v), 4)}
         for f, v in by_field.items()],
        key=lambda d: d["mean_nif"], reverse=True,
    )
    return {"apc_distribution": apc_distribution,
            "open_access_share": open_access_share, "nif_by_field": nif_by_field}
```

> Note: tests use `org_id=None` and the `== org_id` filter generates correct `IS NULL` SQL (same pattern as `upsert_journal_metric`).

- [ ] **Step 4: Run to verify pass** — `pytest backend/tests/test_journals_api.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/journal_metrics_service.py backend/tests/test_journals_api.py
git commit -m "feat(journals): read helpers (get/list/stats) with org scoping"
```

## Task 3: `journals.py` router (3 endpoints)

**Files:**
- Create: `backend/routers/journals.py`
- Test: `backend/tests/test_journals_api.py`

- [ ] **Step 1: Write failing tests** (append; use `client` + `auth_headers` conftest fixtures)

```python
def test_get_single_404(client, auth_headers):
    assert client.get("/journals/NOPE", headers=auth_headers).status_code == 404


def test_get_single_ok(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="0028-0836", normalized_impact_factor=1.5))
    db_session.commit()
    r = client.get("/journals/0028-0836", headers=auth_headers)
    assert r.status_code == 200 and r.json()["normalized_impact_factor"] == 1.5


def test_list_pagination_header_and_sort_validation(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="A", normalized_impact_factor=2.0))
    db_session.commit()
    r = client.get("/journals?sort_by=nif&order=desc&limit=10", headers=auth_headers)
    assert r.status_code == 200 and r.headers["X-Total-Count"] == "1"
    assert client.get("/journals?sort_by=bogus", headers=auth_headers).status_code == 422


def test_stats_route_not_shadowed(client, auth_headers):
    # /journals/stats must resolve to the aggregate, not be parsed as issn_l="stats"
    r = client.get("/journals/stats", headers=auth_headers)
    assert r.status_code == 200 and "apc_distribution" in r.json()


def test_journals_requires_auth(client):
    assert client.get("/journals/stats").status_code in (401, 403)
```

- [ ] **Step 2: Run to verify fail** — FAIL (404s, route missing).

- [ ] **Step 3: Implement** `backend/routers/journals.py`

```python
"""Read-only journal-metrics endpoints (NIF + APC surfacing)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import get_current_user
from backend.database import get_db
from backend.tenant_access import resolve_request_org_id
from backend.services.journal_metrics_service import (
    get_journal_metric, list_journal_metrics, journal_stats,
)

router = APIRouter(tags=["journals"])

_SORT_BY = {"nif", "citedness", "apc", "h_index"}
_ORDER = {"asc", "desc"}


# NOTE: /stats MUST be declared before /{issn_l} or FastAPI binds issn_l="stats".
@router.get("/journals/stats", response_model=schemas.JournalStatsResponse)
def get_journal_stats(db: Session = Depends(get_db),
                      user: models.User = Depends(get_current_user)):
    org_id = resolve_request_org_id(db, user)
    return journal_stats(db, org_id)


@router.get("/journals")
def list_journals(response: Response,
                  sort_by: str = Query("nif"),
                  order: str = Query("desc"),
                  field: Optional[str] = Query(None),
                  limit: int = Query(50, ge=1, le=200),
                  offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    if sort_by not in _SORT_BY:
        raise HTTPException(422, f"sort_by must be one of {sorted(_SORT_BY)}")
    if order not in _ORDER:
        raise HTTPException(422, "order must be 'asc' or 'desc'")
    org_id = resolve_request_org_id(db, user)
    rows, total = list_journal_metrics(db, org_id, sort_by, order, limit, offset, field)
    response.headers["X-Total-Count"] = str(total)
    return [schemas.JournalMetricResponse.model_validate(r) for r in rows]


@router.get("/journals/{issn_l}", response_model=schemas.JournalMetricResponse)
def get_journal(issn_l: str, db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    org_id = resolve_request_org_id(db, user)
    row = get_journal_metric(db, org_id, issn_l)
    if row is None:
        raise HTTPException(404, "journal not found")
    return row
```

- [ ] **Step 4: Mount the router** — in `backend/main.py`, add `journals` to the routers import block (~line 41) and `app.include_router(journals.router)` near line 472.

- [ ] **Step 5: Run to verify pass** — `pytest backend/tests/test_journals_api.py -v` → all PASS. Confirm `test_stats_route_not_shadowed` passes (ordering correct).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/journals.py backend/main.py backend/tests/test_journals_api.py
git commit -m "feat(journals): read-only router (single/list/stats), org-scoped"
```

## Task 4: Backend slice verification

- [ ] **Step 1:** `D:\universal-knowledge-intelligence-platform\.venv\Scripts\python -m pytest backend/tests/test_journals_api.py backend/tests/ -k "journal or metadata_contract or entities" -q` → all green (no regression; `issn_l` contract change didn't break the metadata-contract test).
- [ ] **Step 2: Commit** (if any cleanup) — otherwise proceed.

---

# SLICE B — Entity detail modal surface

## Task 5: Shared `JournalProvenanceBadge` + `formatApc`

**Files:**
- Create: `frontend/app/components/JournalProvenanceBadge.tsx`
- Test: `frontend/app/components/JournalProvenanceBadge.test.tsx`

Read first: an existing small component + a `*.test.tsx` (run `git ls-files "frontend/**/*.test.tsx" | head`) to match the vitest + testing-library pattern and the governed UI imports.

- [ ] **Step 1: Write failing test**

```tsx
import { render, screen } from "@testing-library/react";
import { JournalProvenanceBadge, formatApc } from "./JournalProvenanceBadge";

test("badge shows open-proxy provenance text", () => {
  render(<JournalProvenanceBadge />);
  expect(screen.getByText(/open proxy/i)).toBeInTheDocument();
});

test("formatApc renders amount with currency, or em dash when null", () => {
  expect(formatApc(1500, "USD")).toBe("1,500 USD");
  expect(formatApc(null, null)).toBe("—");
});
```

- [ ] **Step 2: Run to verify fail** — `cd frontend && npx vitest run app/components/JournalProvenanceBadge.test.tsx` → FAIL.

- [ ] **Step 3: Implement** a small badge (tooltip/`title`) reading: "Open proxy: OpenAlex 2-yr mean citedness, field-normalized — not Clarivate JIF." Plus `export function formatApc(amount: number | null, currency: string | null): string`. Use governed components/utility classes — NO hardcoded palette hex/`bg-[...]`; reuse tokens/classes seen in sibling components (read `frontend/app/components/ui` for a Badge/Chip if one exists; otherwise a semantic `<span className="...">` with token classes).

- [ ] **Step 4: Run to verify pass** — both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/components/JournalProvenanceBadge.tsx frontend/app/components/JournalProvenanceBadge.test.tsx
git commit -m "feat(journals-ui): shared provenance badge + formatApc util"
```

## Task 6: `JournalMetricsSection` + wire into modal

**Files:**
- Create: `frontend/app/components/JournalMetricsSection.tsx`
- Modify: `frontend/app/components/EntityTableDetailsModal.tsx`
- Test: `frontend/app/components/JournalMetricsSection.test.tsx`

Read first: `EntityTableDetailsModal.tsx` (`parseJsonObject`, how the entity + its `attributes_json` are available, where enrichment fields render) and `@/lib/api` (`apiFetch`).

- [ ] **Step 1: Write failing tests** (mock `apiFetch`)

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { JournalMetricsSection } from "./JournalMetricsSection";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));
import { apiFetch } from "@/lib/api";

test("does not fetch when issn_l absent", () => {
  render(<JournalMetricsSection issnL={null} />);
  expect(apiFetch).not.toHaveBeenCalled();
  expect(screen.queryByText(/journal/i)).not.toBeInTheDocument();
});

test("renders NIF + APC when journal found", async () => {
  (apiFetch as any).mockResolvedValue({ ok: true, status: 200, json: async () => ({
    issn_l: "0028-0836", display_name: "Nature", normalized_impact_factor: 1.5,
    two_yr_mean_citedness: 17.4, h_index: 1200, apc_usd: 11690, apc_currency: "USD",
    is_in_doaj: false, nif_field: "Genetics" }) });
  render(<JournalMetricsSection issnL="0028-0836" />);
  await waitFor(() => expect(screen.getByText(/Nature/)).toBeInTheDocument());
  expect(screen.getByText(/1\.5/)).toBeInTheDocument();
});

test("404 shows subtle not-yet-enriched note", async () => {
  (apiFetch as any).mockResolvedValue({ ok: false, status: 404, json: async () => ({}) });
  render(<JournalMetricsSection issnL="X" />);
  await waitFor(() => expect(screen.getByText(/not yet/i)).toBeInTheDocument());
});
```

- [ ] **Step 2: Run to verify fail.**

- [ ] **Step 3: Implement** `JournalMetricsSection.tsx`: props `{ issnL: string | null }`. If `issnL` null → render nothing. Else `useEffect` → `apiFetch(\`/journals/\${encodeURIComponent(issnL)}\`)`; states loading (skeleton)/404 (subtle note)/data. Render NIF (+ `<JournalProvenanceBadge/>`), citedness, h-index, APC via `formatApc` + "Open Access" chip when `is_in_doaj`, and the `nif_field` subfield. Governed classes only.

- [ ] **Step 4: Wire into modal** — in `EntityTableDetailsModal.tsx`, parse `issn_l` from the entity attributes (reuse `parseJsonObject`) and render `<JournalMetricsSection issnL={issnL} />` in the body alongside the other enrichment sections.

- [ ] **Step 5: Run to verify pass** — section tests PASS; `cd frontend && npx vitest run` (no regression).

- [ ] **Step 6: Commit**

```bash
git add frontend/app/components/JournalMetricsSection.tsx frontend/app/components/JournalMetricsSection.test.tsx frontend/app/components/EntityTableDetailsModal.tsx
git commit -m "feat(journals-ui): lazy Journal section in entity detail modal"
```

---

# SLICE C — Journals analytics dashboard

## Task 7: `JournalsRankingTable`

**Files:**
- Create: `frontend/app/analytics/journals/JournalsRankingTable.tsx`
- Test: `frontend/app/analytics/journals/JournalsRankingTable.test.tsx`

Read first: `frontend/app/analytics/dashboard/page.tsx` for the governed table/`ui` imports and URL-state pattern (`useSearchParams`).

- [ ] **Step 1: Write failing test** — renders rows from a passed `journals` prop; clicking a sortable header calls the `onSort` callback with the column key. (Keep data-fetching in the page, table is presentational → easy to test.)
- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** a presentational table: props `{ journals, sortBy, order, onSort }`. Columns: journal (`display_name`), subfield (`nif_field`), NIF (+ `JournalProvenanceBadge` in the header), citedness, h-index, APC (`formatApc`), OA chip. Governed classes; no hardcoded palette.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** `feat(journals-ui): ranking table component`.

## Task 8: `JournalsCharts` (APC distribution + NIF by discipline)

**Files:**
- Create: `frontend/app/analytics/journals/JournalsCharts.tsx`
- Test: `frontend/app/analytics/journals/JournalsCharts.test.tsx`

Read first: the Recharts usage in `analytics/dashboard/page.tsx`.

- [ ] **Step 1: Write failing test** — given a `stats` prop (`apc_distribution`, `open_access_share`, `nif_by_field`), renders chart containers + the OA-share label (assert on text/roles, not pixels; Recharts renders SVG — assert the section headings + the OA percent text render).
- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** presentational charts: a bar chart for `nif_by_field` (mean_nif per subfield) and a bar/summary for `apc_distribution` per currency, plus the OA-share figure. Recharts; governed classes.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** `feat(journals-ui): APC + NIF-by-discipline charts`.

## Task 9: Dashboard page + admin button + nav

**Files:**
- Create: `frontend/app/analytics/journals/page.tsx`
- Modify: `frontend/app/components/sidebarNav.tsx`
- Test: `frontend/app/analytics/journals/page.test.tsx`

Read first: `EnrichmentSchedulerCard.tsx` (admin gate `ADMIN_ROLES`/`useAuth`), `sidebarNav.tsx` (item shape), `analytics/dashboard/page.tsx` (page skeleton, `useToast`, `ErrorBanner`, `SkeletonCard`).

- [ ] **Step 1: Write failing tests** (mock `apiFetch` + `useAuth`):
  - admin button hidden for `viewer`, visible for `admin`;
  - clicking "Recompute NIF" calls `apiFetch("/journals/normalize", {method:"POST"})` and toasts the updated count;
  - page fetches `/journals` and `/journals/stats` on mount and renders the table + charts.
- [ ] **Step 2: Run to verify fail.**
- [ ] **Step 3: Implement** the page: fetch list + stats (parallel) via `apiFetch`; render `JournalsRankingTable` + `JournalsCharts`; URL-state for sort/page; admin-only "Recompute NIF" button (`ADMIN_ROLES.has(user.role)`) → `POST /journals/normalize` then refetch + success toast. Add a nav item `{ href: "/analytics/journals", label: ... }` to the appropriate section in `sidebarNav.tsx`, and (optional) a CTA card on the analytics landing.
- [ ] **Step 4: Run to verify pass** — page tests PASS; `cd frontend && npx vitest run` (no regression).
- [ ] **Step 5: Commit** `feat(journals-ui): journals analytics dashboard + nav + admin recompute`.

---

## Task 10: Full verification

- [ ] **Step 1: Backend** — `D:\universal-knowledge-intelligence-platform\.venv\Scripts\python -m pytest backend/tests/ -q` → all pass.
- [ ] **Step 2: Frontend** — `cd frontend && npx vitest run` → all pass; `npx eslint .` and `npx tsc --noEmit` (or repo scripts) → clean; respect the Design System governance gate (no new hardcoded palette classes — reuse governed components).
- [ ] **Step 3: Preview verification** — start the dev server (preview tools): open an enriched entity → Journal section shows NIF/APC + provenance; visit `/analytics/journals` → ranking sorts, charts render, admin button gated; check responsive + both themes if applicable. Capture a screenshot as proof.
- [ ] **Step 4: Commit** any fixes from verification.

---

## Open items / deferred (YAGNI for v1)

- Per-journal work-count column (needs JOIN over `raw_entities.attributes_json->issn_l`).
- FX→USD conversion for DOAJ APC (charts group by currency to avoid mixing).
- Analytics-landing CTA is optional; nav item is the required entry point.
