## Why

UKIP's enrichment concepts are stored as flat comma-separated strings (`enrichment_concepts`). Users cannot navigate from a broad concept like "Artificial Intelligence" down to "Machine Learning" → "Deep Learning", nor can they see how their corpus maps onto a structured knowledge taxonomy. This limits analytical depth: topic modeling and OLAP treat every concept as an isolated label, missing the hierarchical relationships that OpenAlex already provides (concepts have `level` 0-5 and `ancestors`). Implementing concept hierarchy navigation is the foundation layer (Fase A) of the Domain Analysis RFC, and a prerequisite for epistemic classification (Fase B) and domain health metrics (Fase C).

## What Changes

- Extend `DomainSchema` with an optional `concept_relations` configuration block
- New `concept_hierarchy.py` analyzer that fetches and caches concept ancestor/descendant relationships from the OpenAlex Concepts API
- Materialize a local concept subgraph scoped to each tenant's corpus (only concepts that appear in their entities)
- New backend endpoints for concept tree retrieval and concept detail lookup
- Persist concept `level` (0-5) alongside concept names during enrichment
- New frontend page with interactive tree/sunburst visualization of the corpus concept hierarchy
- Concept node counts (how many entities map to each concept) at every tree level

## Capabilities

### New Capabilities
- `concept-tree-materialization`: Backend analyzer that builds and caches a hierarchical concept graph from OpenAlex, scoped to the tenant's enriched entities
- `concept-hierarchy-ui`: Frontend interactive tree/sunburst visualization with drill-down navigation, entity counts per node, and links to filtered entity views

### Modified Capabilities

## Impact

- **Backend**: New analyzer module (`backend/analyzers/concept_hierarchy.py`), new endpoints in `backend/routers/analytics.py`, minor change to enrichment worker to persist concept levels
- **Frontend**: New page under `/analytics/concepts`, new visualization component
- **Schema**: `DomainSchema` in `schema_registry.py` gets optional `concept_relations` field; `science.yaml` updated with default config
- **External API**: OpenAlex Concepts API (`/concepts/{id}`) — free, polite-pool, cached aggressively
- **Dependencies**: No new libraries — uses existing `httpx` for API calls, existing frontend charting
