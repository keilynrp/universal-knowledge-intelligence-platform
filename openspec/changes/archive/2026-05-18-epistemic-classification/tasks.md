## 1. Schema & Configuration

- [x] 1.1 Add Pydantic models for epistemology config (`ParadigmIndicators`, `Paradigm`, `EvidenceLevel`, `EpistemologyConfig`) in `schema_registry.py`
- [x] 1.2 Add optional `epistemology: Optional[EpistemologyConfig]` field to `DomainSchema`
- [x] 1.3 Extend `science.yaml` with `epistemology` section: 3 paradigms (empiricist, constructivist, critical) with term indicators, document_types, journals_affinity + 6-level evidence hierarchy
- [x] 1.4 Verify existing domains without epistemology key still load correctly (unit test)

## 2. Epistemic Classifier Engine

- [x] 2.1 Create `backend/analyzers/epistemic_classifier.py` with `EpistemicClassifier` class
- [x] 2.2 Implement `_score_entity(entity, paradigms)` — term matching in abstract + concepts + document_type + journal, weighted scoring (0.6/0.25/0.15), normalization to sum=1.0
- [x] 2.3 Implement `classify_entity(db, entity, paradigms)` — scores + persists `attributes_json.epistemic_profile`
- [x] 2.4 Implement `classify_batch(db, domain_id, chunk_size=500)` — classifies all enriched entities missing profile, returns stats
- [x] 2.5 Handle edge cases: no abstract or abstract < 50 chars → unclassified; no indicator matches → unclassified
- [x] 2.6 Write unit tests for classifier: term matching, scoring normalization, edge cases, persistence

## 3. Post-Enrichment Hook

- [x] 3.1 Add epistemic auto-classification call in `enrichment_worker.py` after successful enrichment, gated on domain having epistemology config
- [x] 3.2 Import schema registry and classifier; classify only when `registry.get_domain(entity.domain)` has `.epistemology`
- [x] 3.3 Write test: enrichment of science entity triggers classification; enrichment of healthcare entity skips classification

## 4. API Endpoints

- [x] 4.1 Add `POST /analytics/epistemic/{domain_id}/classify` endpoint in `routers/analytics.py` (admin+ role, returns classified/skipped/unclassified counts)
- [x] 4.2 Add `GET /analytics/epistemic/{domain_id}/distribution` endpoint (authenticated, returns total_classified, total_unclassified, paradigm_counts, by_year breakdown)
- [x] 4.3 Validate domain has epistemology config on both endpoints (400 if not)
- [x] 4.4 Write endpoint tests: batch classify, distribution, RBAC (viewer 403 on classify), 400 for unconfigured domain

## 5. OLAP Integration

- [x] 5.1 In `olap.py._load_domain_df()`, extract `paradigm` column from `attributes_json.epistemic_profile.dominant`
- [x] 5.2 Add `paradigm` to valid dimensions in `get_dimensions()` when the domain has epistemology config
- [x] 5.3 Write test: OLAP query with paradigm dimension returns correct grouping

## 6. Frontend — Epistemic Analytics Page

- [x] 6.1 Create `frontend/app/analytics/epistemic/page.tsx` with page shell, loading state, and empty state
- [x] 6.2 Implement paradigm distribution donut chart using Recharts PieChart
- [x] 6.3 Implement temporal evolution area chart (paradigm % by year) using Recharts AreaChart
- [x] 6.4 Add admin-only "Classify Entities" button with loading state and toast feedback
- [x] 6.5 Add empty state for domain without epistemology config (informational message)
- [x] 6.6 Add "Epistemic Analysis" item to sidebar navigation under Analytics section
- [x] 6.7 Add i18n strings (EN + ES) for all epistemic analytics UI text
- [x] 6.8 Write frontend test: renders empty state, renders charts with mock data, admin sees classify button, viewer does not
