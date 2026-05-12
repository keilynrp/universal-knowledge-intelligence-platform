## ADDED Requirements

### Requirement: CO_AUTHOR edge extraction
The system SHALL generate `CO_AUTHOR` relationship edges between authors who share a common entity, creating pairwise edges during enrichment processing.

#### Scenario: Extract co-authorship from multi-author entity
- **WHEN** an entity's enrichment returns authors ["Alice", "Bob", "Carol"]
- **THEN** the system SHALL create 3 `CO_AUTHOR` edges in `EntityRelationship`: Alice↔Bob, Alice↔Carol, Bob↔Carol, each referencing the entity ID in `notes`

#### Scenario: Increment weight for repeated co-authorship
- **WHEN** two authors co-author a second entity
- **THEN** the system SHALL increment the `weight` field on the existing `CO_AUTHOR` edge by 1.0 rather than creating a duplicate edge

#### Scenario: Cap co-authorship extraction for large author lists
- **WHEN** an entity has more than 15 authors
- **THEN** the system SHALL only create `CO_AUTHOR` edges between the first author and each remaining author (star topology), skipping full pairwise generation

### Requirement: Co-authorship network endpoint
The system SHALL expose `GET /analyzers/coauthorship/{domain_id}` returning the co-authorship graph as nodes and edges.

#### Scenario: Retrieve co-authorship graph
- **WHEN** an authenticated user requests the co-authorship network for a domain
- **THEN** the system SHALL return `nodes` (list of authors with `id`, `label`, `degree`, `total_publications`) and `edges` (list of co-authorship links with `source`, `target`, `weight`)

#### Scenario: Filter by minimum weight
- **WHEN** `min_weight=3` query parameter is provided
- **THEN** the system SHALL only include edges where `weight >= 3` and only include nodes connected by at least one included edge

#### Scenario: Limit graph size
- **WHEN** `limit=50` query parameter is provided
- **THEN** the system SHALL return the top 50 authors by degree centrality and only edges between those authors

#### Scenario: Empty network
- **WHEN** the domain has no `CO_AUTHOR` relationships
- **THEN** the system SHALL return empty `nodes` and `edges` arrays

### Requirement: Degree centrality computation
The system SHALL compute degree centrality for each node in the co-authorship network, defined as the number of distinct co-authors divided by (N-1) where N is the total number of authors in the network.

#### Scenario: Compute centrality for well-connected author
- **WHEN** an author has co-authored with 10 out of 50 total authors in the network
- **THEN** the degree centrality SHALL be 10/49 ≈ 0.204

#### Scenario: Single-author network
- **WHEN** the network contains only one author
- **THEN** the degree centrality SHALL be 0.0

### Requirement: Community detection
The system SHALL detect communities in the co-authorship network using a greedy modularity approach (connected components as a baseline, with Louvain-like greedy merge when components are large).

#### Scenario: Identify research communities
- **WHEN** the co-authorship graph has two disconnected clusters of authors
- **THEN** the system SHALL assign each cluster a distinct `community_id` in the node response

#### Scenario: All authors connected
- **WHEN** all authors are in a single connected component
- **THEN** the system SHALL assign `community_id = 0` to all nodes
