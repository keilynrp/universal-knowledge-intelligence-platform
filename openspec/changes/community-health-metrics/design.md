## Context

UKIP's Domain Analysis RFC defines three epistemic layers over `DomainSchema`. Fase A (concept hierarchy) and Fase B (epistemic classification) are complete. Fase C adds the final synthesis layer: community health metrics that quantify structural dynamics of knowledge domains.

The platform already has the raw data needed:
- **Authors**: extracted during OpenAlex enrichment, stored in `attributes_json.authors`
- **Countries**: extracted as `attributes_json.country` or `attributes_json.countries`
- **Open Access status**: `attributes_json.is_open_access` from OpenAlex
- **Epistemic profiles**: `attributes_json.epistemic_profile.dominant` from Fase B
- **Publication years**: `RawEntity.year` column
- **Authority records**: Sprint 15-16 identity resolution (ORCID, VIAF, OpenAlex)

## Goals / Non-Goals

**Goals:**
- Compute 5 community health metrics from existing enrichment data (no new external API calls)
- Provide temporal breakdown (per-year) for trend analysis
- Enable cross-domain comparison (side-by-side metrics for 2+ domains)
- Extend `DomainSchema` with optional `discourse_community` configuration
- Frontend dashboard with indicator cards, sparkline trends, and comparison view

**Non-Goals:**
- Co-authorship network visualization (already exists in `coauthorship.py`)
- New external data fetching or enrichment adapters
- Real-time streaming metrics — batch computation is sufficient
- Configurable metric thresholds in YAML (hardcoded interpretation bands are fine for v1)
- BIBFRAME/WEMI integration (Fase D, future)

## Decisions

### D1: Pure computation over existing data (no new tables)

**Decision:** All metrics are computed on-the-fly from `RawEntity` data. No new database tables or materialized views.

**Rationale:** The dataset sizes per domain (typically <50k entities) make real-time aggregation fast enough (<2s). Adding tables would require migrations and cache invalidation logic. If performance becomes an issue, we can add caching later.

**Alternative considered:** Materialized `DomainHealthSnapshot` table updated on each enrichment — rejected as premature optimization.

### D2: Metric computation in a single analyzer module

**Decision:** All 5 metrics in `backend/analyzers/domain_health.py` with a unified `compute_health_metrics(db, domain_id)` entry point returning all metrics at once.

**Rationale:** Metrics share the same data scan (entities + attributes). A single pass is more efficient than 5 separate queries. The analyzer returns a structured dict with metric values, temporal series, and interpretation labels.

### D3: Gini coefficient via sorted cumulative share

**Decision:** Standard Gini computation: sort author publication counts ascending, compute cumulative share vs. equal-distribution line, normalize to [0, 1].

**Formula:** `G = (2 * sum(i * y_i)) / (n * sum(y_i)) - (n + 1) / n` where `y_i` are sorted counts.

**Rationale:** Simple, well-understood, no external dependencies beyond numpy.

### D4: Shannon entropy for epistemic diversity

**Decision:** `H = -sum(p_i * log2(p_i))` over paradigm proportions from classified entities. Normalize to `H / log2(k)` where `k` = number of paradigms, yielding [0, 1] range.

**Rationale:** Standard information-theoretic measure. Normalized entropy allows cross-domain comparison regardless of paradigm count.

### D5: Newcomer detection via first-appearance year

**Decision:** For each unique author string, find their earliest publication year in the domain. Authors whose earliest year equals the target year are "newcomers" for that year.

**Rationale:** Simple and deterministic. Does not require authority resolution — works on raw author strings. Authority-resolved identities (ORCID) would improve accuracy but are not required.

### D6: International collaboration via country co-occurrence

**Decision:** An entity is "internationally collaborative" if it has authors from 2+ distinct countries. The rate is `count(multi-country entities) / count(entities with country data)`.

**Rationale:** Country data comes from OpenAlex enrichment (`attributes_json.countries` or institution affiliations). Entities without country data are excluded from the denominator.

### D7: Frontend as a dedicated page with gauge indicators

**Decision:** New page at `/analytics/domain-health` with:
- 5 metric cards with current value, interpretation label (e.g., "Moderate concentration"), and sparkline trend
- Temporal chart (line/area) showing metric evolution over years
- Domain comparison dropdown to overlay metrics from another domain

**Rationale:** Consistent with existing analytics pages (epistemic, topics, OLAP). Gauge/card pattern is familiar and scannable.

## Risks / Trade-offs

- **[Author string matching is imprecise]** → Gini and newcomer metrics use raw author strings, not resolved identities. Mitigated: results are directionally correct; future enhancement can use ORCID-resolved authors when available.
- **[Missing country data]** → Not all entities have country information from OpenAlex. Mitigated: collaboration rate only counts entities with country data in denominator; UI shows data coverage percentage.
- **[Epistemic diversity requires Fase B]** → Shannon entropy depends on epistemic classification. Mitigated: metric gracefully returns null/N/A when no epistemic profiles exist; other 4 metrics still compute.
- **[Small corpus bias]** → Gini and entropy are unstable with very few entities (<20). Mitigated: show warning when sample size is below threshold; don't render trend for years with <5 entities.
