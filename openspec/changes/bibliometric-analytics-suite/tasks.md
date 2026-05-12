## 1. Trend Topics

- [x] 1.1 Create `backend/analyzers/trend_analysis.py` — temporal frequency computation (concept × year matrix from `enrichment_concepts`), year extraction from entity data
- [x] 1.2 Implement slope computation via `numpy.polyfit(degree=1)` and trend classification (emerging/declining/stable) with configurable thresholds
- [x] 1.3 Add `GET /analyzers/trends/{domain_id}` endpoint to `backend/routers/analytics.py` with `limit`, `min_year`, `max_year`, `min_years` query params
- [x] 1.4 Write tests for trend analysis — frequency computation, slope classification, min_years filter, empty domain, invalid domain (target: 10+ tests)
- [x] 1.5 Create `frontend/app/analytics/trends/page.tsx` — trend chart (slope bars or sparklines per concept), classification badges, year range filter

## 2. Author Productivity & H-index

- [x] 2.1 Create `backend/analyzers/author_metrics.py` — h-index computation, per-author aggregation (total pubs, total citations, avg citations, pubs per year) from authority records + entity citation counts
- [x] 2.2 Add `GET /analyzers/authors/{domain_id}` endpoint (ranked list, `sort_by` h_index|total_publications|total_citations, `limit` param)
- [x] 2.3 Add `GET /analyzers/authors/{domain_id}/{record_id}` endpoint (single author detail with top-cited entities)
- [x] 2.4 Write tests for author metrics — h-index edge cases (zero citations, all equal, single paper), ranking, detail endpoint, missing domain (target: 12+ tests)
- [x] 2.5 Create frontend author productivity tab — top authors table with h-index/citations, single-author detail view with publications-per-year chart

## 3. Co-authorship Network

- [x] 3.1 Add `CO_AUTHOR` edge generation in enrichment worker — pairwise extraction from multi-author entities, weight increment for repeated co-authorship, cap at 15 authors (star topology fallback)
- [x] 3.2 Add `GET /analyzers/coauthorship/{domain_id}` endpoint — nodes with degree/community_id, edges with weight, `min_weight` and `limit` query params
- [x] 3.3 Implement degree centrality computation (distinct co-authors / (N-1))
- [x] 3.4 Implement community detection — connected components baseline, greedy modularity merge for large components
- [x] 3.5 Write tests for co-authorship — edge extraction, weight increment, cap behavior, centrality math, community detection, empty network (target: 12+ tests)
- [x] 3.6 Update frontend graph visualizer to render `CO_AUTHOR` network — node sizing by degree, edge thickness by weight, community coloring

## 4. Geographic / Country Analysis

- [x] 4.1 Create `backend/analyzers/geographic.py` — country lookup table (ISO 3166 + abbreviations), affiliation string parser, country extraction logic
- [x] 4.2 Add country extraction step in enrichment worker — extract and persist `extracted_country` in `attributes_json` for new entities
- [x] 4.3 Add `GET /analyzers/geographic/{domain_id}` endpoint — per-country aggregation (entity_count, citation_sum, author_count, percentage), sort_by and limit params, "others" bucket
- [x] 4.4 Add `include_collaboration=true` support — international collaboration rate and top country pairs
- [x] 4.5 Extend `GET /dashboard/summary` to include `geographic_heatmap` field
- [x] 4.6 Write tests for geographic analysis — country extraction (standard, abbreviated, unresolvable), aggregation, collaboration rate, dashboard integration (target: 12+ tests)
- [x] 4.7 Create frontend geographic analysis view — country ranking table, heatmap visualization on dashboard, collaboration pairs display

## 5. Integration & Polish

- [x] 5.1 Add sidebar navigation entries for new analytics pages (Trends, Author Productivity, Co-authorship, Geographic)
- [x] 5.2 Add i18n labels (EN + ES) for all new navigation items and page titles
- [x] 5.3 Run full test suite — verify no regressions, target 80%+ coverage on new modules
- [x] 5.4 Backfill country extraction for existing entities via a one-time migration/script
