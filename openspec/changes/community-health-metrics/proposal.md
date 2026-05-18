## Why

UKIP has strong quantitative analytics (citation counts, co-occurrence PMI, Cramer's V, OLAP cube) and recently added epistemic classification (paradigm affinity scoring per entity). However, it lacks **community-level health indicators** that reveal structural dynamics of the knowledge domain — authorship concentration, collaboration patterns, openness, epistemic diversity, and newcomer influx. These metrics are essential for the "Capa 3 — Comunidad discursiva" layer described in the Domain Analysis RFC (Hjorland & Albrechtsen alignment), completing the three-layer epistemic enrichment of `DomainSchema`.

## What Changes

- New `discourse_community` optional section in `DomainSchema` (YAML-driven configuration)
- New `backend/analyzers/domain_health.py` module computing 5 health metrics:
  - **Gini coefficient** of authorship concentration (0=distributed, 1=concentrated)
  - **International collaboration rate** (fraction of multi-country co-authorships)
  - **Open Access rate** (fraction of OA publications)
  - **Epistemic diversity** (Shannon entropy over paradigm distribution from Fase B)
  - **Newcomer rate** (fraction of first-time authors per year)
- New analytics endpoints for domain health metrics with temporal breakdown
- New frontend dashboard ("Domain Health") with gauge/indicator cards, temporal trends, and cross-domain comparison
- Sidebar navigation entry for the new dashboard
- i18n strings (EN + ES) for all new UI elements

## Capabilities

### New Capabilities
- `domain-health-engine`: Backend computation engine for 5 community health metrics (Gini, collaboration, OA, diversity, newcomers) with temporal breakdown and caching
- `domain-health-dashboard`: Frontend dashboard with health indicator cards, sparkline trends, cross-domain comparison, and drill-down views

### Modified Capabilities
- `epistemic-classification-engine`: Consume `epistemic_profile.dominant` paradigm distribution as input for Shannon entropy calculation (read-only dependency, no spec changes needed)

## Impact

- **Backend**: `schema_registry.py` extended with `DiscourseConfig` Pydantic model; new `domain_health.py` analyzer; new endpoints in `routers/analytics.py`; `domains/science.yaml` extended with `discourse_community` section
- **Frontend**: New page at `analytics/domain-health/`; sidebar update; i18n additions
- **Dependencies**: No new external libraries — uses existing numpy for Gini/Shannon calculations and existing enrichment data (authors, countries, OA status, epistemic profiles)
- **Data sources consumed**: `RawEntity.attributes_json` (authors, country, is_open_access, epistemic_profile), existing enrichment data from OpenAlex adapter
