## Context

UKIP stores scientific entities in `raw_entities` with enrichment fields (`enrichment_concepts`, `enrichment_citation_count`, `enrichment_source`) and authority records that link authors to canonical identities. The `EntityRelationship` model supports typed edges (cites, authored-by, belongs-to, related-to). Affiliation data lives in `attributes_json`. The `TopicAnalyzer` already computes concept frequencies and co-occurrence; the `CorrelationAnalyzer` handles field correlation. The frontend has a graph visualizer, analytics dashboard with heatmap, and OLAP explorer. We need to add 4 new bibliometric features that build on this existing infrastructure.

## Goals / Non-Goals

**Goals:**
- Deliver trend topic analysis over temporal windows using existing concept + year data
- Compute h-index and productivity metrics per author using citation counts and authority records
- Enable co-authorship network visualization by adding `CO_AUTHOR` edges during enrichment
- Provide geographic aggregation by extracting country from affiliation strings

**Non-Goals:**
- Replacing Bibliometrix/R for deep bibliometric analysis (Lotka's Law, Bradford's Law, three-fields plot, historiograph)
- Building a full geographic mapping UI (Leaflet/Mapbox integration) — we provide data-level heatmap, not a zoomable map
- Real-time streaming analytics — all computations are batch/on-demand
- Embedding-based topic modeling (BERTopic, LDA) — we use frequency-based trend analysis

## Decisions

### D1: Trend computation via linear regression slope
**Choice**: Compute frequency per concept per year, then use numpy `polyfit(degree=1)` to get the slope. Classify as emerging (slope > threshold), declining (slope < -threshold), or stable.

**Alternatives considered**:
- Moving average: less interpretable, doesn't yield a single "direction" metric
- Mann-Kendall test: statistically rigorous but overkill for a UI feature; numpy polyfit is simpler and sufficient

**Rationale**: Slope is intuitive ("this concept grew by N papers/year"), easy to sort/rank, and numpy is already in the stack.

### D2: H-index from citation counts on authority-linked entities
**Choice**: For each author (by `AuthorityRecord.canonical_label` where `field_name='author'`), collect all linked entities' `enrichment_citation_count`, sort descending, find h where at least h papers have h+ citations.

**Alternatives considered**:
- Query OpenAlex/Scopus for pre-computed h-index: introduces API dependency and rate limits; our data may differ from their corpus
- Store h-index as a column: stale quickly; better to compute on demand with caching

**Rationale**: Pure computation over local data, no external dependency. Cache result per author with TTL to avoid recomputation.

### D3: CO_AUTHOR edges extracted during enrichment
**Choice**: When enrichment returns multiple authors for an entity, generate pairwise `CO_AUTHOR` edges in `EntityRelationship`. Populate during `enrichment_worker` processing of new entities.

**Alternatives considered**:
- Compute co-authorship on the fly from shared entities: expensive at query time for large datasets
- Separate co-authorship table: adds schema complexity; `EntityRelationship` already supports typed edges

**Rationale**: Pre-materialized edges enable fast graph queries and reuse the existing relationship model + graph visualizer.

### D4: Country extraction via regex + lookup table
**Choice**: Parse `attributes_json.affiliation` strings with a country lookup table (200 countries + common abbreviations like "USA", "UK", "PRC"). Fallback to last comma-separated segment which is typically country.

**Alternatives considered**:
- Geocoding API: introduces external dependency, rate limits, cost
- NER extraction: heavy dependency (spaCy), overkill for country names

**Rationale**: Affiliations almost always end with country name. A static lookup table is fast, deterministic, and requires zero external dependencies.

### D5: All new endpoints under existing analytics router
**Choice**: Add endpoints to `backend/routers/analytics.py` rather than creating new routers. Group under `/analyzers/` URL prefix.

**Rationale**: Consistent with existing pattern (`/analyzers/topics/`, `/analyzers/correlation/`). Keeps router count manageable.

## Risks / Trade-offs

- **[Sparse year data]** → Trend analysis requires at least 3 distinct years per concept to be meaningful. Mitigation: filter out concepts with fewer than `min_years` data points (default 3), return warning in response.
- **[Affiliation quality]** → Country extraction accuracy depends on affiliation string quality from enrichment sources. Mitigation: log unmatched affiliations; allow manual country override via authority records.
- **[CO_AUTHOR edge explosion]** → A paper with N authors generates N*(N-1)/2 edges. For N=20 that's 190 edges per entity. Mitigation: cap at `MAX_AUTHORS_FOR_COAUTH=15`; beyond that, only link to first author.
- **[H-index computation cost]** → For domains with thousands of authors, computing all h-indexes is expensive. Mitigation: paginated endpoint with `limit` param; cache results with domain-level invalidation on new imports.
- **[No existing country field]** → Country must be extracted from unstructured affiliation text. Mitigation: store extracted country in a new `country` key within `attributes_json` so extraction runs once per entity.

## Open Questions

- Should trend analysis support custom date fields from `attributes_json` (e.g., `publication_date`) or only the year extracted from enrichment? Start with enrichment year, extend later if needed.
- Should co-authorship edges be bidirectional (A→B and B→A) or single-direction? Decision: single edge per pair (lower ID → higher ID) with `weight` tracking co-publication count.
