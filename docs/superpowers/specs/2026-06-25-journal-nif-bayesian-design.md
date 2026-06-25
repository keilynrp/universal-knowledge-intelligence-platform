# Bayesian NIF (hierarchical shrinkage) — Design Spec

**Date:** 2026-06-25
**Status:** Approved (brainstorming)
**Feature:** Add a Bayesian, uncertainty-aware companion to the journal NIF — `nif_bayes` plus a 95% credible interval — that corrects noisy small-sample journal estimates by shrinking them toward their field, *alongside* the existing `normalized_impact_factor` (does not replace it).

## Background & motivation

UKIP's NIF (`normalized_impact_factor`, PR #77/#79) is `two_yr_mean_citedness / median(citedness within the same nif_field bucket)` — a point estimate, normalized in-sample. Two weaknesses:

1. **Each journal's `two_yr_mean_citedness` is a noisy rate** for journals with few papers. A journal with a handful of works in the 2-year window can show a NIF of ~0.05–0.15 that is mostly sampling noise.
2. **The denominator (the per-field median) is itself estimated** from however many journals UKIP happens to have ingested.

An evidence-first POC (2026-06-25, empirical Bayes over the 270 real prod journals, `h_index` as a size proxy) validated the behavior: small/young journals (h≤50) moved an average of **35%**, large/consolidated ones (h≥400) **0.1%**, and the method produced credible intervals (median width ~0.35 NIF). Conclusion: hierarchical shrinkage acts materially and *only* where the estimate is unreliable. (Note: supervised calibration from human confirm/reject feedback was ruled out — every feedback table is empty in prod.)

This is the *methodology* of Bayesian hierarchical modeling (à la Google Meridian's calibration/uncertainty philosophy), adapted to a knowledge-graph problem — **not** an integration of Meridian itself.

## Approach (locked)

**Closed-form Empirical Bayes, Gamma-Poisson conjugate**, in a new analyzer module that is a sibling of `journal_normalization.py`. Per `nif_field` bucket, estimate a Gamma prior over journal citation rates; per journal, compute the conjugate Gamma posterior from its implied citation count and 2-year paper count; write the shrunk NIF and its credible interval to new columns. Pure `numpy`/`scipy` (both already in `requirements.txt` — scipy 1.17.1, numpy 2.4.2). Deterministic, testable, no MCMC, no new dependency. Wired into the existing admin recompute path.

The true sampling size `n` is the **OpenAlex 2-year works count**, captured into a new column during the existing source fetch.

## Non-goals (YAGNI)

- **Frontend surfacing** (entity modal + `/analytics/journals` dashboard) — deferred follow-up, mirroring how NIF shipped (backend #77 → frontend #82).
- **NumPyro / MCMC / full Bayes** — overkill for ~270 well-separated-by-field rows.
- **Modeling uncertainty of the field denominator itself** — the Empirical-Bayes prior is plugged in as fixed; the journal-level posterior carries the uncertainty.
- **Cross-field partial pooling** beyond the small-field global-prior fallback.
- **Replacing `normalized_impact_factor`** — `nif_bayes` is a sibling metric on its own scale.

---

## Architecture & components

### 1. Model — `backend/models.py` (`JournalMetric`)
Add, alongside the existing metric columns:
```python
works_2yr            = Column(Integer, nullable=True)   # OpenAlex 2yr paper count (the model's n)
nif_bayes            = Column(Float, nullable=True, index=True)
nif_ci_low           = Column(Float, nullable=True)
nif_ci_high          = Column(Float, nullable=True)
nif_bayes_updated_at = Column(DateTime, nullable=True)
```
`works_2yr` is the statistical sample size; the four `nif_bayes*` columns are the output, written by the new batch. All nullable so a never-computed row is distinguishable (consistent with the existing `updated_at` convention).

### 2. Migration — `alembic/versions/<rev>_journal_nif_bayes.py`
- `down_revision = "c5e6f7a8b9c0"` — current single working head of the main chain (the works-count `raw_entity_issn_l` migration). Verify with `alembic heads` at implementation; a separate orphan `0001` baseline also reports as a head (pre-existing, unrelated).
- `upgrade()`: `op.add_column` ×5 with idempotent `_has_column` guards (via `sa.inspect`) consistent with repo migration style; `op.create_index("ix_journal_metrics_nif_bayes", "journal_metrics", ["nif_bayes"])`.
- `downgrade()`: drop index + columns.
- Tests that assert the expected Alembic head get bumped to the new revision (pattern from #83).

### 3. Ingestion capture — `backend/adapters/enrichment/openalex.py`
In `fetch_source_metrics` (~line 141), the full OpenAlex source `body` is already in scope. Extract the 2-year works count from `counts_by_year`:
```python
"works_2yr": _works_last_2_complete_years(body.get("counts_by_year") or []),
```
New helper `_works_last_2_complete_years(counts)`: sum `works_count` over the two most recent **complete** calendar years present (exclude the current partial year). Returns `None` when the data is absent/empty. Add `works_2yr: Optional[int] = None` to the `JournalMetrics` object (`backend/schemas_enrichment.py`).

**Cache note:** `_SOURCE_CACHE` stores the parsed `data` dict; pre-existing entries won't carry `works_2yr` → `.get("works_2yr")` defaults `None`, and the `--refresh` flag (#89) re-fetches. No cache-version bump needed.

### 4. Upsert — `backend/services/journal_metrics_service.py`
In the JournalMetric upsert (the block around line 36 that copies `two_yr_mean_citedness`), persist the new size field when present:
```python
if jm.works_2yr is not None:
    row.works_2yr = jm.works_2yr
```
The `nif_bayes*` columns are written only by the batch (§5), never by the upsert.

### 5. Bayesian batch — `backend/analyzers/journal_normalization_bayes.py` (new)
`normalize_impact_factors_bayes(db: Session, org_id: Optional[int]) -> int`. Sibling of `normalize_impact_factors`.

**Eligibility:** journals with `two_yr_mean_citedness` AND `works_2yr` not null. Rows missing `works_2yr` are skipped → `nif_bayes` stays null (graceful degradation; renders without a band until re-enriched).

**Bucketing** mirrors `normalize_impact_factors` exactly: group by `r.nif_field or "all"` (journals with null `nif_field` fall into a shared `"all"` bucket rather than being skipped), so the two metrics partition journals identically.

**Per bucket:**
1. For each journal: `n_j = works_2yr`; implied citations `C_j = round(rate_j * n_j)` where `rate_j = two_yr_mean_citedness`.
2. **Gamma prior `(α, β)` by method of moments**, with the Poisson sampling component removed from the between-journal variance so the prior reflects *true* between-journal dispersion, not noise:
   - Prior mean (pooled rate): `m = Σ_j C_j / Σ_j n_j`.
   - Each journal rate `rate_j = C_j/n_j` has Poisson sampling variance ≈ `m / n_j`. The raw `Var_j(rate_j)` therefore overstates the prior variance; subtract the mean sampling component:
     `v = max( Var_j(rate_j) − mean_j(m / n_j), ε )`.
     (This is exactly the POC's `tau2 = max(var_y − mean_s2, ε)`; a naive `np.var(rates)` would overstate `v` and under-shrink.)
   - `α = m²/v`, `β = m/v`, with guards (`m > 0`; `v` floored at `ε`).
3. **Small buckets** (`len < K`, default `K = 5` → e.g. Materials n=1, Mathematics n=2, Chemistry n=3) use a **global prior** pooled over all eligible journals instead of an unstable 1–2-point prior.

**Per journal (conjugate update):**
- Posterior `Gamma(α + C_j, β + n_j)`.
- `rate_post = (α + C_j) / (β + n_j)`.
- 95% CI = `scipy.stats.gamma.ppf([0.025, 0.975], a=α + C_j, scale=1.0/(β + n_j))`.
- **Field reference** = prior mean `α/β` (so `nif_bayes = 1.0` means "field-average", matching NIF's semantics).
- `nif_bayes = rate_post / ref`; `nif_ci_low/high = CI_bounds / ref`.
- Write the four columns + `nif_bayes_updated_at`. Return count updated.

**Modeling assumption (documented):** OpenAlex exposes the *rate* (`2yr_mean_citedness`), not raw citation counts. We reconstruct `C = round(rate × works_2yr)` and treat the metric as generated by `works_2yr` independent Poisson papers. This is an approximation — `counts_by_year` works-per-year need not exactly equal OpenAlex's internal 2yr denominator, and the rate is rounded. Acceptable and standard for shrinkage; stated explicitly.

**Comparability note:** `nif_bayes` uses the Gamma-prior-mean denominator; `normalized_impact_factor` uses the in-DB median. Both center ~1.0 = field average but are **not** identical in absolute value. They are sibling metrics, not a replacement.

### 6. Backfill — `backend/scripts/backfill_nif_bayes.py` (new, management entrypoint)
`python -m backend.scripts.backfill_nif_bayes [--org-id N] [--refresh]`. Re-fetches `fetch_source_metrics` per `source_id` (with `--refresh` to clear the OpenAlex cache, #89), persists `works_2yr`, then runs `normalize_impact_factors_bayes`. Org-scoped, idempotent, honoring the 429/503 retry+throttle from #87 to avoid hammering OpenAlex. Needed so the existing ~270 journals get `works_2yr` (and therefore `nif_bayes`) without waiting for re-enrichment.

### 7. Recompute wiring — `backend/routers/analytics_ops.py`
At line 452, immediately after `updated = normalize_impact_factors(db, org_id=org_id)`:
```python
updated_bayes = normalize_impact_factors_bayes(db, org_id=org_id)
```
Return both counters in the response: `{"updated": updated, "updated_bayes": updated_bayes}`. One admin recompute produces both metrics.

### 8. Schema & API — `backend/schemas.py`, `backend/routers/journals.py`
- `JournalMetricResponse`: add `nif_bayes`, `nif_ci_low`, `nif_ci_high: Optional[float] = None` (ORM columns → populated by `model_validate`).
- Journal read endpoints + the dashboard ranking include the three fields. Labeled as an open proxy *with uncertainty*, consistent with the existing "NOT Clarivate JIF" framing.

## Data flow

```
OpenAlex source body ──fetch_source_metrics──▶ JournalMetrics{... works_2yr}
        │                                              │
        │                                      upsert (journal_metrics_service)
        ▼                                              ▼
  counts_by_year                          journal_metrics row {two_yr_mean_citedness, works_2yr}
                                                       │
                          admin recompute / backfill ──▶ normalize_impact_factors      → normalized_impact_factor
                                                     └──▶ normalize_impact_factors_bayes → nif_bayes, nif_ci_low/high
                                                                                              │
                                                                          GET /journals (JournalMetricResponse)
```

## Error handling & edge cases

- **Missing `works_2yr`** → journal skipped by the batch; `nif_bayes` null; API returns null (frontend renders no band).
- **`C_j = 0`** (citedness 0) → posterior `Gamma(α, β + n_j)` pulled toward the field prior; `nif_ci_low` ≥ 0 by construction (Gamma support is positive). No negative-CI clipping needed.
- **Degenerate bucket variance** (`v ≤ ε`, all journals near-identical) → fall back to global prior; if global also degenerate, skip shrinkage (write `nif_bayes = nif`-equivalent point with a wide default CI is NOT done — instead leave null and log).
- **Single-journal / tiny field** → global-prior fallback (K threshold).
- **`two_yr_mean_citedness` null** → not eligible (already excluded).

## Testing (pytest; conftest `_TABLES_TO_CLEAN` already includes `journal_metrics`)

- **EB math, unit:** known `(rate, n)` inputs → asserted posterior mean, CI bounds, and shrinkage direction; including the small-bucket → global-prior path.
- **`_works_last_2_complete_years`:** full data, missing years, current partial year excluded, empty/None → None.
- **Degradation:** `works_2yr` null → `nif_bayes` stays null after batch.
- **`C = round(rate × n)`** reconstruction and the `C_j = 0` case (CI low ≥ 0).
- **Comparability:** field-average journal → `nif_bayes ≈ 1.0`.
- **Migration:** expected-head assertion bumped to the new revision; up/down round-trip.
- **Endpoint:** `nif_bayes`/CI present in `GET /journals`; recompute returns both counters.

## Open items for implementation

- Confirm the exact `counts_by_year` shape returned by the OpenAlex sources endpoint (field names `year` / `works_count`) against a live/sample payload before finalizing `_works_last_2_complete_years`.
- Confirm `K` (small-bucket threshold) and `ε` guards against the real field-size distribution (POC: 19 fields, sizes 1–39).
