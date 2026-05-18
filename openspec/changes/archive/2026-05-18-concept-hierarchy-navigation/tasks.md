## 1. Database & Model

- [x] 1.1 Add ConceptNode model to backend/models.py (id, openalex_id, display_name, level, parent_id FK, entity_count, domain, last_fetched_at)
- [x] 1.2 Add DB migration in lifespan to create concept_nodes table with self-referential FK
- [x] 1.3 Add index on (domain, level) and unique constraint on (openalex_id, domain)

## 2. OpenAlex Concept Fetcher & Cache

- [x] 2.1 Create backend/analyzers/concept_hierarchy.py with async httpx client (polite pool: 5 concurrent, 100ms delay)
- [x] 2.2 Implement file-based cache in concept_cache/ directory (read/write JSON, 7-day TTL check)
- [x] 2.3 Implement fetch_concept_ancestors(concept_id) — walks up ancestor chain via OpenAlex /concepts/{id} endpoint
- [x] 2.4 Implement resolve_concept_id_by_name(display_name) — searches OpenAlex for legacy entities without concept IDs

## 3. Materialization Logic

- [x] 3.1 Implement materialize_domain_concepts(db, domain_id) — collects unique concepts from enriched entities, fetches ancestry, upserts concept_nodes
- [x] 3.2 Add 2000-concept cap with frequency-based selection and warning response
- [x] 3.3 Compute entity_count per node by counting entities whose enrichment_concepts contain that concept name

## 4. Enrichment Worker Enhancement

- [x] 4.1 Modify enrichment worker to persist enrichment_concept_ids (list of OpenAlex IDs) in attributes_json alongside enrichment_concepts
- [x] 4.2 Extract concept IDs from OpenAlex enrichment response in openalex adapter

## 5. Backend API Endpoints

- [x] 5.1 Add POST /analytics/concepts/{domain_id}/materialize endpoint (admin+ role, calls materialize_domain_concepts)
- [x] 5.2 Add GET /analytics/concepts/{domain_id}/tree endpoint (authenticated, returns nested JSON tree with entity counts)
- [x] 5.3 Add GET /analytics/concepts/{domain_id}/{concept_node_id} endpoint (authenticated, returns concept detail + paginated entities)
- [x] 5.4 Register endpoints in backend/routers/analytics.py

## 6. Backend Tests

- [x] 6.1 Test ConceptNode model creation and self-referential FK
- [x] 6.2 Test materialization logic with mocked OpenAlex responses
- [x] 6.3 Test tree endpoint returns correct nested structure
- [x] 6.4 Test concept detail endpoint with pagination
- [x] 6.5 Test RBAC: viewer cannot materialize, all authenticated can read
- [x] 6.6 Test cache hit/miss behavior
- [x] 6.7 Test idempotent materialization (no duplicates on re-run)

## 7. Frontend Page & Navigation

- [x] 7.1 Add "Concept Hierarchy" item to sidebar under Analytics section
- [x] 7.2 Create frontend/app/analytics/concepts/page.tsx with tree/sunburst toggle
- [x] 7.3 Add i18n strings (EN + ES) for all page labels, buttons, and messages

## 8. Frontend Tree View Component

- [x] 8.1 Create ConceptTree component with collapsible nodes (expand/collapse with animation)
- [x] 8.2 Show entity count badges on each node
- [x] 8.3 Default expand level 0-1, collapse level 2+
- [x] 8.4 Implement click-to-navigate to entity table with concept filter

## 9. Frontend Sunburst View

- [x] 9.1 Implement sunburst visualization using Recharts Treemap or custom radial component
- [x] 9.2 Segment size proportional to entity_count, rings = hierarchy levels
- [x] 9.3 Hover tooltip with concept name, level, count, parent
- [x] 9.4 Click segment navigates to filtered entity list

## 10. Frontend Admin Controls

- [x] 10.1 Show "Refresh Hierarchy" button for admin+ users only
- [x] 10.2 Implement materialization call with loading state and success/error toast
- [x] 10.3 Reload tree data after successful materialization

## 11. Frontend Tests

- [x] 11.1 Test page renders empty state when no concepts exist
- [x] 11.2 Test tree view renders with mock concept data
- [x] 11.3 Test toggle between tree and sunburst views
- [x] 11.4 Test admin sees refresh button, viewer does not
