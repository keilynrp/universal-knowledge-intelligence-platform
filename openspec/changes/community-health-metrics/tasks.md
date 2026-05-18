## 1. Schema Extension

- [x] 1.1 Add `DiscourseConfig`, `HealthMetricDef`, `AuthoritySources`, `ChannelTier`, `CommunicationChannels`, `ValidationPractice` Pydantic models to `backend/schema_registry.py`
- [x] 1.2 Add `discourse_community: Optional[DiscourseConfig] = None` field to `DomainSchema`
- [x] 1.3 Add `discourse_community` section to `backend/domains/science.yaml` with authority sources, channel tiers, and 5 health metric declarations
- [x] 1.4 Write test: science domain loads with discourse_community config; other domains load with None

## 2. Gini Coefficient

- [x] 2.1 Create `backend/analyzers/domain_health.py` with `_extract_authors(entities)` helper that parses author lists from `attributes_json`
- [x] 2.2 Implement `_gini_coefficient(counts: list[int]) -> float` using sorted cumulative share formula
- [x] 2.3 Write tests: balanced authors → low Gini; concentrated → high Gini; single author → 0.0

## 3. International Collaboration Rate

- [x] 3.1 Implement `_extract_countries(entity) -> list[str]` helper parsing country data from attributes_json
- [x] 3.2 Implement `_international_collaboration_rate(entities) -> Optional[float]` returning fraction of multi-country entities
- [x] 3.3 Write tests: mixed corpus → correct rate; no country data → None

## 4. Open Access Rate

- [x] 4.1 Implement `_open_access_rate(entities) -> Optional[float]` computing fraction of OA entities
- [x] 4.2 Write tests: partial OA → correct rate; no OA data → None

## 5. Epistemic Diversity (Shannon Entropy)

- [x] 5.1 Implement `_epistemic_diversity(entities, paradigm_count: int) -> Optional[float]` computing normalized Shannon entropy from epistemic_profile.dominant
- [x] 5.2 Write tests: uniform distribution → ~1.0; single paradigm → low; no profiles → None

## 6. Newcomer Rate

- [x] 6.1 Implement `_newcomer_rate(entities, year: int) -> Optional[float]` computing fraction of first-time authors in a given year
- [x] 6.2 Write tests: year with many first-timers → high rate; established community → low rate

## 7. Unified Health Metrics Engine

- [x] 7.1 Implement `compute_health_metrics(db, domain_id) -> dict` that runs all 5 metrics with aggregate values and interpretation labels
- [x] 7.2 Add temporal breakdown: compute metrics per year, include `by_year` array with `low_sample` flag for years with <5 entities
- [x] 7.3 Add small sample guards: return null for <3 entities, add `low_sample` warning for <20
- [x] 7.4 Write integration test: full metrics computation with sample data

## 8. API Endpoints

- [x] 8.1 Add `_require_discourse_community(domain_id)` helper to `routers/analytics.py` (returns 400 if domain lacks config)
- [x] 8.2 Add `GET /analytics/domain-health/{domain_id}` endpoint returning all metrics
- [x] 8.3 Add `GET /analytics/domain-health/compare` endpoint accepting `domains` query param for cross-domain comparison
- [x] 8.4 Write endpoint tests: success, unconfigured domain → 400, compare endpoint, RBAC (all authenticated users can access)

## 9. Frontend Dashboard

- [x] 9.1 Create `frontend/app/analytics/domain-health/page.tsx` with loading/empty/no-config/data states
- [x] 9.2 Implement metric indicator cards with value, interpretation label, and color-coded indicator (green/amber/red)
- [x] 9.3 Add temporal trend line chart using Recharts (LineChart with toggleable metric series)
- [x] 9.4 Add cross-domain comparison dropdown and side-by-side metric display
- [x] 9.5 Add "Domain Health" nav item to sidebar with appropriate icon

## 10. Internationalization & Tests

- [x] 10.1 Add EN + ES i18n strings for all domain health UI elements (metric names, labels, interpretations, empty states) under `domain_health` namespace
- [x] 10.2 Write frontend test: renders empty state, renders metrics with data, viewer can access
