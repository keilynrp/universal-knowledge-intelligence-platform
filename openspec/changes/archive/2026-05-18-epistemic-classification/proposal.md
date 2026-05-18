## Why

UKIP completed Fase A of the Domain Analysis RFC (concept hierarchy navigation), giving the platform structured concept trees from OpenAlex. However, the platform still lacks qualitative analysis — it cannot answer "from which epistemological tradition was this work produced?" Fase B adds epistemic classification: assigning paradigm affinity scores (empiricist, constructivist, critical) to enriched entities using text matching on abstracts, concepts, and document types. This bridges the gap between UKIP's strong quantitative metrics (citations, PMI, Cramér's V) and the qualitative intelligence that Hjørland's domain analysis framework demands.

## What Changes

- Extend `DomainSchema` with optional `epistemology` section (paradigms + evidence hierarchy) in domain YAML files
- Configure `science.yaml` with at least 3 paradigms (empiricist, constructivist, critical) each with term indicators, document type affinities, and journal affinities
- New `backend/analyzers/epistemic_classifier.py` — classifies entities by paradigm affinity using term frequency matching against abstract + enrichment_concepts + document_type
- Post-enrichment hook in `enrichment_worker.py` that auto-classifies newly enriched entities and persists `epistemic_profile` in `attributes_json`
- Batch classification endpoint for existing entities (`POST /analytics/epistemic/{domain_id}/classify`)
- Distribution endpoint (`GET /analytics/epistemic/{domain_id}/distribution`) returning paradigm counts, temporal trends, and cross-correlations
- New OLAP dimension `paradigm` so the cube explorer can slice by epistemic tradition
- Frontend widget showing paradigm distribution (bar/donut chart) with temporal drill-down
- Backend tests + frontend tests for the new functionality

## Capabilities

### New Capabilities
- `epistemic-classification-engine`: Text-matching classifier that scores entities against paradigm indicators (terms, document types, journal affinities) and persists epistemic profiles
- `epistemic-analytics-ui`: Frontend analytics page showing paradigm distribution, temporal evolution, and correlation with quantitative metrics

### Modified Capabilities
- `concept-tree-materialization`: Concept hierarchy data is consumed as input signal for epistemic classification (concept overlap with paradigm indicators)

## Impact

- **Backend**: New analyzer module, new endpoints in `routers/analytics.py`, hook in enrichment worker, schema registry extension
- **Frontend**: New analytics sub-page, i18n strings, sidebar nav item
- **Domain YAML**: `science.yaml` extended with `epistemology` section; other domains unaffected (section is optional)
- **OLAP**: New `paradigm` dimension derived from `epistemic_profile` in attributes_json
- **Dependencies**: None new — uses existing numpy for scoring, no external NLP libraries
- **Data model**: No new DB tables — epistemic profiles stored in existing `attributes_json` column on `RawEntity`
