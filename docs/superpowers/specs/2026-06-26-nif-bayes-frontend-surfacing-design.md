# NIF (Bayes) Frontend Surfacing — Design

**Date:** 2026-06-26
**Status:** Approved (design)
**Depends on:** PR #90 (merged, `83f96af`) — `nif_bayes`, `nif_ci_low`, `nif_ci_high` already returned by the journals read API.

## Goal

Surface the Bayesian NIF (`nif_bayes`) and its 95% credible interval
(`nif_ci_low`–`nif_ci_high`) **alongside** the existing field-normalized NIF, in
the entity modal's Journal section and the `/analytics/journals` ranking table.
Carry the same "open proxy, not Clarivate JIF" framing the NIF already uses via
`JournalProvenanceBadge`. Mirrors the original NIF surfacing (PR #82).

Out of scope (deferred, separate specs): dashboard chart visualization of
`nif_bayes` (needs a backend stats aggregation), and the production backfill run.

## Background

`nif_bayes` is an Empirical-Bayes Gamma-Poisson shrinkage of the open-proxy NIF
(OpenAlex 2-yr mean citedness, field-normalized). It pulls noisy small-sample
journals toward their field and reports a credible interval expressing how much
to trust each value. It does **not** replace `normalized_impact_factor`; both are
shown. Until the prod backfill runs, `nif_bayes` is `null` for existing rows, so
every surface must degrade silently to `—` / hidden.

## Surfaces & Changes

### 1. Entity modal — `frontend/app/components/JournalMetricsSection.tsx`

- Extend the `JournalMetricResponse` interface with
  `nif_bayes: number | null`, `nif_ci_low: number | null`,
  `nif_ci_high: number | null`.
- Add one `Metric` card (tone `violet`, placed next to the existing NIF card),
  rendered only when `nif_bayes != null`:
  - **value:** `nif_bayes.toFixed(2)`
  - **label:** `NIF (Bayes)` followed by `<JournalProvenanceBadge />`
  - **description:** `95% CI: {lo}–{hi}` (each `.toFixed(2)`) when both bounds are
    present; otherwise `Shrinkage-adjusted`.
- No change to the existing `idle/loading/found/not_found/error` state machine or
  the `useEffect` fetch (no synchronous setState — keep the react-hooks-lint-safe
  pattern already in the file).

### 2. Ranking table — `frontend/app/analytics/journals/JournalsRankingTable.tsx`

- Extend `JournalRow` with the same three fields.
- Add a sortable **"NIF (Bayes)"** column immediately after the NIF column:
  header is a ghost `Button` carrying `<JournalProvenanceBadge />` + `<SortIcon>`,
  calling `onSort("nif_bayes")`, with `aria-label="Sort by NIF (Bayes)"`.
- Cell: `nif_bayes.toFixed(3)`; below it, the CI range in small
  `var(--ukip-muted)` text (`{lo}–{hi}`, each `.toFixed(2)`) when both bounds
  exist. Render `—` when `nif_bayes` is null.

### 3. Backend sort support (minimal)

- `backend/routers/journals.py`: add `"nif_bayes"` to `_SORT_BY`.
- `backend/services/journal_metrics_service.py`: map `"nif_bayes"` →
  `JournalMetric.nif_bayes` in `_SORT_COLUMNS`, keeping the existing NULLS-last
  ordering behavior used by the other numeric sorts.

## Data Flow

No new endpoints. `GET /journals/{issn}` (modal) and
`GET /journals?sort_by=…&order=…` (table) already return the three fields. The
dashboard page (`analytics/journals/page.tsx`) already round-trips
`sort_by`/`order` through URL search params and re-fetches; clicking the new
column header updates the param. The backend whitelist addition is what lets
`sort_by=nif_bayes` return 200 instead of 422.

## Null / Edge Handling

- All three fields are `number | null`. Pre-backfill, `nif_bayes` is `null` for
  existing journals → table shows `—`, modal hides the Bayes card. Silent, no
  errors.
- Partial CI (one bound null): show the value without the range.

## Testing

**Frontend (Vitest, `frontend/__tests__/`):**
- `JournalsRankingTable.test.tsx`: a row with `nif_bayes` + CI renders value and
  range; a row with `null` renders `—`; clicking the new header invokes
  `onSort("nif_bayes")`.
- `JournalMetricsSection`: the Bayes card renders with its CI when `nif_bayes` is
  present and is absent when null. (Add a suite if none exists for this file.)

**Backend (pytest):**
- Extend the journals-endpoint test: `sort_by=nif_bayes` returns 200 with correct
  ordering; an invalid `sort_by` still returns 422.

**Repo gates:** pre-push (`scripts/pre-push-check.sh`, ESLint `--max-warnings=0`),
Design System gate (governed `ui/` primitives only, no direct palette classes).

## Risks

- Low. Additive fields with null-safe rendering; the only backend change is a
  whitelist entry + column mapping, covered by tests.
