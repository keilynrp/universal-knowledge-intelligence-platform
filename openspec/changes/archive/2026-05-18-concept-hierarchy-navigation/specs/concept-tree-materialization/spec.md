## ADDED Requirements

### Requirement: Concept nodes table stores hierarchical concept data
The system SHALL maintain a `concept_nodes` table with columns: id (PK), openalex_id (unique per domain), display_name, level (0-5), parent_id (self-referential FK, nullable), entity_count (integer), domain (string), last_fetched_at (datetime).

#### Scenario: Table schema supports tree structure
- **WHEN** the database migrations run
- **THEN** the `concept_nodes` table exists with a nullable self-referential foreign key `parent_id` pointing to `concept_nodes.id`

#### Scenario: Domain scoping isolates tenant concept graphs
- **WHEN** two domains "science" and "healthcare" each have materialized concepts
- **THEN** querying concept_nodes filtered by domain="science" returns only science-related nodes

### Requirement: Materialization endpoint builds concept subgraph from OpenAlex
The system SHALL expose `POST /analytics/concepts/{domain_id}/materialize` (admin+ role) that fetches ancestor chains for all unique concepts found in enriched entities of that domain, upserts them into `concept_nodes`, and returns a summary of nodes created/updated.

#### Scenario: Successful materialization from enriched entities
- **WHEN** admin calls POST /analytics/concepts/science/materialize
- **AND** the science domain has entities with enrichment_concepts "Machine Learning, Deep Learning"
- **THEN** the system fetches concept ancestors from OpenAlex API
- **THEN** concept_nodes contains entries for "Machine Learning" (level 2), "Artificial Intelligence" (level 1), "Computer Science" (level 0), "Deep Learning" (level 3) with correct parent_id links
- **THEN** response includes `{"nodes_created": N, "nodes_updated": M}`

#### Scenario: Materialization is idempotent
- **WHEN** admin calls POST /analytics/concepts/science/materialize twice
- **THEN** the second call updates `last_fetched_at` and `entity_count` but does not create duplicate nodes (upsert on openalex_id + domain)

#### Scenario: Viewer cannot trigger materialization
- **WHEN** a viewer-role user calls POST /analytics/concepts/science/materialize
- **THEN** the system returns HTTP 403

#### Scenario: Materialization caps at 2000 unique concepts
- **WHEN** the domain has more than 2000 unique leaf concepts in enriched entities
- **THEN** the system processes only the 2000 most frequent concepts and returns a warning in the response

### Requirement: Concept tree retrieval endpoint returns nested hierarchy
The system SHALL expose `GET /analytics/concepts/{domain_id}/tree` (authenticated) that returns the materialized concept hierarchy as nested JSON with entity counts.

#### Scenario: Tree endpoint returns nested structure
- **WHEN** authenticated user calls GET /analytics/concepts/science/tree
- **AND** concept_nodes has "Computer Science" (level 0) → "AI" (level 1) → "ML" (level 2)
- **THEN** response is `{"nodes": [{"id": X, "name": "Computer Science", "level": 0, "entity_count": 50, "children": [{"id": Y, "name": "AI", "level": 1, "entity_count": 30, "children": [...]}]}]}`

#### Scenario: Tree filtered by root level
- **WHEN** user calls GET /analytics/concepts/science/tree?root_level=1
- **THEN** the tree starts from level-1 concepts (omitting level-0 roots)

#### Scenario: Empty tree for domain with no materialized concepts
- **WHEN** user calls GET /analytics/concepts/business/tree
- **AND** no concept_nodes exist for domain "business"
- **THEN** response is `{"nodes": [], "materialized_at": null}`

### Requirement: Concept detail endpoint returns node metadata and entities
The system SHALL expose `GET /analytics/concepts/{domain_id}/{concept_node_id}` (authenticated) that returns the concept's metadata and a paginated list of entities tagged with that concept.

#### Scenario: Detail returns concept metadata and entities
- **WHEN** user calls GET /analytics/concepts/science/42
- **AND** concept_node 42 is "Machine Learning" with 15 entities
- **THEN** response includes `{"id": 42, "name": "Machine Learning", "level": 2, "openalex_id": "C...", "entity_count": 15, "entities": [{"id": 1, "primary_label": "..."}, ...], "page": 1, "total": 15}`

#### Scenario: Pagination on concept detail
- **WHEN** user calls GET /analytics/concepts/science/42?page=2&per_page=10
- **THEN** response returns the second page of entities for that concept

#### Scenario: Not found for invalid concept node
- **WHEN** user calls GET /analytics/concepts/science/99999
- **AND** no concept_node with id 99999 exists
- **THEN** response is HTTP 404

### Requirement: Enrichment persists concept OpenAlex IDs
The system SHALL store OpenAlex concept IDs in `attributes_json.enrichment_concept_ids` (list of strings) during enrichment, alongside the existing `enrichment_concepts` string, to enable direct API lookups without fuzzy matching.

#### Scenario: Concept IDs stored during enrichment
- **WHEN** the enrichment worker processes an entity and OpenAlex returns concepts with IDs
- **THEN** `attributes_json` contains `enrichment_concept_ids: ["C41008148", "C154945302", ...]` matching the order of `enrichment_concepts`

#### Scenario: Legacy entities without concept IDs
- **WHEN** materialization runs and encounters entities with `enrichment_concepts` but no `enrichment_concept_ids`
- **THEN** the system falls back to searching OpenAlex by display_name to resolve IDs

### Requirement: OpenAlex API calls are cached aggressively
The system SHALL cache OpenAlex concept API responses in a local file-based cache (`concept_cache/` directory) keyed by OpenAlex concept ID, with a 7-day TTL.

#### Scenario: Cache hit avoids API call
- **WHEN** materialization needs concept "C41008148"
- **AND** a cache file `concept_cache/C41008148.json` exists and is less than 7 days old
- **THEN** the system reads from cache without making an HTTP request

#### Scenario: Cache miss triggers API call and stores result
- **WHEN** materialization needs concept "C41008148"
- **AND** no cache file exists for that ID
- **THEN** the system calls OpenAlex API, stores the response in `concept_cache/C41008148.json`, and uses it

#### Scenario: Polite pool rate limiting
- **WHEN** multiple concepts need fetching
- **THEN** the system limits concurrent requests to 5 and inserts 100ms delay between batches
