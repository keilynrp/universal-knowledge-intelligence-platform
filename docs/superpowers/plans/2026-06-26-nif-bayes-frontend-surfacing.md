# NIF (Bayes) Frontend Surfacing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface `nif_bayes` + its 95% credible interval (`nif_ci_low`–`nif_ci_high`) alongside the existing NIF in the entity modal's Journal section and the `/analytics/journals` ranking table, with a sortable Bayes column.

**Architecture:** Backend already returns the three fields on the journals read API (PR #90). This plan (1) adds `nif_bayes` to the sort whitelist + column map and makes ordering NULLs-last, then (2) consumes the fields in two existing React components. Pure-additive, null-safe.

**Tech Stack:** Python, FastAPI, SQLAlchemy, pytest (backend); Next.js, React, TypeScript, Vitest + Testing Library (frontend).

**Spec:** `docs/superpowers/specs/2026-06-26-nif-bayes-frontend-surfacing-design.md`

**Branch:** `feat/nif-bayes-frontend` (off `main` @ `83f96af`).

**Sub-skills:** @superpowers:test-driven-development, @superpowers:verification-before-completion

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routers/journals.py` (`_SORT_BY`, line 20) | Modify | Add `"nif_bayes"` to the sort whitelist |
| `backend/services/journal_metrics_service.py` (`_SORT_COLUMNS` line 73; `list_journal_metrics` order_by line 103-104) | Modify | Map `nif_bayes` column + wrap ordering with `nullslast` |
| `backend/tests/test_journals_api.py` | Modify | Backend sort + NULLs-last tests |
| `frontend/app/components/JournalMetricsSection.tsx` | Modify | `JournalMetricResponse` +3 fields; Bayes `Metric` card |
| `frontend/__tests__/JournalMetricsSection.test.tsx` | Modify | Bayes card render + null-absence tests |
| `frontend/app/analytics/journals/JournalsRankingTable.tsx` | Modify | `JournalRow` +3 fields; sortable "NIF (Bayes)" column |
| `frontend/__tests__/JournalsRankingTable.test.tsx` | Modify | Column value+CI, null `—`, onSort tests |

---

### Task 1: Backend — sortable `nif_bayes` with NULLs-last ordering

**Files:**
- Modify: `backend/routers/journals.py:20`
- Modify: `backend/services/journal_metrics_service.py` (`_SORT_COLUMNS` line 73; order_by line 103)
- Test: `backend/tests/test_journals_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_journals_api.py`:

```python
def test_list_sort_by_nif_bayes(db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="A", nif_bayes=0.5))
    db_session.add(JournalMetric(org_id=None, issn_l="B", nif_bayes=2.0))
    db_session.commit()
    rows, total = list_journal_metrics(db_session, None, sort_by="nif_bayes",
                                       order="desc", limit=10, offset=0)
    assert total == 2 and [r.issn_l for r in rows] == ["B", "A"]


def test_list_nif_bayes_nulls_sort_last(db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="HAS", nif_bayes=1.0))
    db_session.add(JournalMetric(org_id=None, issn_l="NULL1", nif_bayes=None))
    db_session.add(JournalMetric(org_id=None, issn_l="NULL2", nif_bayes=None))
    db_session.commit()
    rows, _ = list_journal_metrics(db_session, None, sort_by="nif_bayes",
                                   order="desc", limit=10, offset=0)
    assert rows[0].issn_l == "HAS"          # populated first
    assert rows[-1].nif_bayes is None       # NULLs last


def test_endpoint_accepts_nif_bayes_sort(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="A", nif_bayes=2.0))
    db_session.commit()
    r = client.get("/journals?sort_by=nif_bayes&order=desc", headers=auth_headers)
    assert r.status_code == 200
    assert client.get("/journals?sort_by=bogus", headers=auth_headers).status_code == 422
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journals_api.py -k "nif_bayes" -v`
Expected: FAIL (`KeyError: 'nif_bayes'` in `_SORT_COLUMNS`, and endpoint 422 for `nif_bayes`).

- [ ] **Step 3: Add `nif_bayes` to the whitelist**

In `backend/routers/journals.py:20`:
```python
_SORT_BY = {"nif", "citedness", "apc", "h_index", "nif_bayes"}
```

- [ ] **Step 4: Map the column + apply NULLs-last ordering**

In `backend/services/journal_metrics_service.py`, add to `_SORT_COLUMNS` (after `h_index`):
```python
    "nif_bayes": JournalMetric.nif_bayes,
```
At the top of the file, change the existing `from sqlalchemy import func` import to:
```python
from sqlalchemy import func, nullslast
```
Then change the ordering line in `list_journal_metrics`:
```python
    direction = col.desc() if order == "desc" else col.asc()
    rows = q.order_by(nullslast(direction)).offset(offset).limit(limit).all()
```

- [ ] **Step 5: Run — expect PASS**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journals_api.py -v`
Expected: PASS (all, including the pre-existing `test_list_sorted_and_total`).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/journals.py backend/services/journal_metrics_service.py backend/tests/test_journals_api.py
git commit -m "feat(journals): sortable nif_bayes column + NULLs-last ordering"
```

---

### Task 2: Modal — Bayes Metric card in `JournalMetricsSection`

**Files:**
- Modify: `frontend/app/components/JournalMetricsSection.tsx`
- Test: `frontend/__tests__/JournalMetricsSection.test.tsx`

- [ ] **Step 1: Write the failing tests**

Append to `frontend/__tests__/JournalMetricsSection.test.tsx`:

```typescript
test("renders NIF (Bayes) card with credible interval", async () => {
  (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, status: 200, json: async () => ({
    issn_l: "0028-0836", display_name: "Nature", normalized_impact_factor: 1.5,
    two_yr_mean_citedness: 17.4, h_index: 1200, apc_usd: 11690, apc_currency: "USD",
    is_in_doaj: false, nif_field: "Genetics",
    nif_bayes: 1.42, nif_ci_low: 0.80, nif_ci_high: 1.25 }) });
  render(<JournalMetricsSection issnL="0028-0836" />);
  await waitFor(() => expect(screen.getByText(/NIF \(Bayes\)/)).toBeInTheDocument());
  expect(screen.getByText(/1\.42/)).toBeInTheDocument();
  expect(screen.getByText(/95% CI: 0\.80.*1\.25/)).toBeInTheDocument();
});

test("omits Bayes card when nif_bayes is null", async () => {
  (apiFetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, status: 200, json: async () => ({
    issn_l: "X", display_name: "Jrnl", normalized_impact_factor: 1.5,
    nif_bayes: null, nif_ci_low: null, nif_ci_high: null }) });
  render(<JournalMetricsSection issnL="X" />);
  await waitFor(() => expect(screen.getByText(/Jrnl/)).toBeInTheDocument());
  expect(screen.queryByText(/NIF \(Bayes\)/)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd frontend && npx vitest run __tests__/JournalMetricsSection.test.tsx`
Expected: FAIL (no "NIF (Bayes)" text).

- [ ] **Step 3: Extend the interface**

In `JournalMetricsSection.tsx`, add to the `JournalMetricResponse` interface (after `works_count`):
```typescript
  nif_bayes: number | null;
  nif_ci_low: number | null;
  nif_ci_high: number | null;
```

- [ ] **Step 4: Add the Bayes Metric card**

In the metrics grid (`<div className="grid ...">`), immediately after the existing NIF `Metric` block (the `data.normalized_impact_factor != null` block), add:
```tsx
        {data.nif_bayes != null && (
          <Metric
            label={
              <span className="flex items-center gap-1.5">
                NIF (Bayes) <JournalProvenanceBadge />
              </span>
            }
            value={data.nif_bayes.toFixed(2)}
            description={
              data.nif_ci_low != null && data.nif_ci_high != null
                ? `95% CI: ${data.nif_ci_low.toFixed(2)}–${data.nif_ci_high.toFixed(2)}`
                : "Shrinkage-adjusted"
            }
            tone="violet"
          />
        )}
```

- [ ] **Step 5: Run — expect PASS**

Run: `cd frontend && npx vitest run __tests__/JournalMetricsSection.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/components/JournalMetricsSection.tsx frontend/__tests__/JournalMetricsSection.test.tsx
git commit -m "feat(journals): NIF (Bayes) card + credible interval in entity modal"
```

---

### Task 3: Table — sortable "NIF (Bayes)" column in `JournalsRankingTable`

**Files:**
- Modify: `frontend/app/analytics/journals/JournalsRankingTable.tsx`
- Test: `frontend/__tests__/JournalsRankingTable.test.tsx`

- [ ] **Step 1: Write the failing tests**

Append to `frontend/__tests__/JournalsRankingTable.test.tsx`. First extend the shared `rows` fixture object (line 6-8) with Bayes fields by adding a second test-local fixture to avoid disturbing existing tests:

```typescript
const bayesRows = [
  { issn_l: "0028-0836", display_name: "Nature", nif_field: "Genetics",
    normalized_impact_factor: 1.5, two_yr_mean_citedness: 17.4, h_index: 1200,
    apc_usd: 11690, apc_currency: "USD", is_in_doaj: false, works_count: 42,
    nif_bayes: 1.421, nif_ci_low: 0.80, nif_ci_high: 1.25 },
];

test("renders nif_bayes value and credible interval", () => {
  render(<JournalsRankingTable journals={bayesRows} sortBy="nif" order="desc" onSort={() => {}} />);
  expect(screen.getByText("1.421")).toBeInTheDocument();
  expect(screen.getByText(/0\.80.*1\.25/)).toBeInTheDocument();
});

test("renders dash when nif_bayes is null", () => {
  const nullRows = [{ ...bayesRows[0], nif_bayes: null, nif_ci_low: null, nif_ci_high: null }];
  render(<JournalsRankingTable journals={nullRows} sortBy="nif" order="desc" onSort={() => {}} />);
  // The Bayes column cell shows an em dash for the null row.
  expect(screen.getAllByText("—").length).toBeGreaterThan(0);
});

test("clicking the NIF (Bayes) header calls onSort('nif_bayes')", () => {
  const onSort = vi.fn();
  render(<JournalsRankingTable journals={bayesRows} sortBy="nif" order="desc" onSort={onSort} />);
  fireEvent.click(screen.getByRole("button", { name: /Sort by NIF \(Bayes\)/i }));
  expect(onSort).toHaveBeenCalledWith("nif_bayes");
});
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd frontend && npx vitest run __tests__/JournalsRankingTable.test.tsx`
Expected: FAIL (no "1.421", no "Sort by NIF (Bayes)" button).

- [ ] **Step 3: Extend the `JournalRow` interface**

In `JournalsRankingTable.tsx`, add to `JournalRow` (after `works_count`):
```typescript
  nif_bayes: number | null;
  nif_ci_low: number | null;
  nif_ci_high: number | null;
```

- [ ] **Step 4: Add the sortable header**

In `<thead>`, immediately after the NIF `<th>` block (the one whose Button calls `onSort("nif")`), add:
```tsx
              {/* NIF (Bayes) — sortable */}
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ukip-muted)]">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onSort("nif_bayes")}
                  aria-label="Sort by NIF (Bayes)"
                  className="gap-1 px-1 uppercase tracking-wider text-xs font-semibold"
                >
                  NIF (Bayes)
                  <JournalProvenanceBadge />
                  <SortIcon active={sortBy === "nif_bayes"} order={order} />
                </Button>
              </th>
```

- [ ] **Step 5: Add the cell**

In `<tbody>`, immediately after the NIF `<td>` (the `normalized_impact_factor` cell), add:
```tsx
                <td className="px-4 py-3 text-sm text-[var(--ukip-text)]">
                  {journal.nif_bayes != null ? (
                    <span className="flex flex-col">
                      <span>{journal.nif_bayes.toFixed(3)}</span>
                      {journal.nif_ci_low != null && journal.nif_ci_high != null && (
                        <span className="text-xs text-[var(--ukip-muted)]">
                          {journal.nif_ci_low.toFixed(2)}{"–"}{journal.nif_ci_high.toFixed(2)}
                        </span>
                      )}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
```

- [ ] **Step 6: Run — expect PASS**

Run: `cd frontend && npx vitest run __tests__/JournalsRankingTable.test.tsx`
Expected: PASS.

> Note: the CI text is split across two adjacent text nodes (`0.80`, `–`, `1.25`). The test matcher `/0\.80.*1\.25/` works because Testing Library's default text normalization concatenates within the parent `<span>`. If the matcher fails on node boundaries, switch to `screen.getByText((_, el) => el?.textContent === "0.80–1.25")`.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/analytics/journals/JournalsRankingTable.tsx frontend/__tests__/JournalsRankingTable.test.tsx
git commit -m "feat(journals): sortable NIF (Bayes) column + credible interval in ranking table"
```

---

### Task 4: Full verification

- [ ] **Step 1: Frontend suite + lint (the pre-push gate)**

Run: `cd frontend && npm run test && npx eslint . --max-warnings=0 && npx tsc --noEmit`
Expected: all green. ESLint `--max-warnings=0` is the strictest gate (matches `scripts/pre-push-check.sh`); it catches react-hooks issues that tsc/vitest miss.

- [ ] **Step 2: Backend journals surface**

Run: `.venv/Scripts/python -m pytest backend/tests/ -k "journal" -q`
Expected: green (watch `test_journals_api.py` and `test_journal_normalization*`).

- [ ] **Step 3: Full backend suite**

Run: `.venv/Scripts/python -m pytest backend/tests/ -q`
Expected: green. Per @superpowers:verification-before-completion, do not declare done until this passes.

- [ ] **Step 4: Finish the branch**

Use @superpowers:finishing-a-development-branch. Push + open PR only when the user asks.
> Repo note: `git push` may hang on Git Credential Manager; the `scripts/pre-push-check.sh` pre-push hook runs ESLint/tsc/scoped-pytest gates first. `main` has no branch protection.

---

## Deferred follow-ups (NOT in this plan)

- **Dashboard chart** visualization of `nif_bayes` (needs a backend stats aggregation in `journal_stats` / `JournalsCharts.tsx`).
- **Prod backfill** run (`python -m backend.scripts.backfill_nif_bayes --refresh`) so `nif_bayes` is non-null in production — until then these surfaces correctly show `—` / hide the card.
