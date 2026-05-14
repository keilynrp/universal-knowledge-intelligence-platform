## ADDED Requirements

### Requirement: Bulk disambiguation pipeline
The engine SHALL provide a `compute_disambiguation` pipeline that accepts a field name and entity values, clusters them by fuzzy similarity, and returns disambiguation groups.

#### Scenario: Cluster similar entity values
- **WHEN** the pipeline receives field_name="author" and a list of entity values
- **THEN** it SHALL return clusters of similar values, each cluster containing the canonical form and all variant forms with their similarity scores

#### Scenario: Token-sort-ratio grouping
- **WHEN** comparing entity values for clustering
- **THEN** the engine SHALL use token-sort-ratio with a configurable similarity threshold (default 0.85) to determine cluster membership

#### Scenario: Large dataset performance
- **WHEN** the pipeline receives more than 10,000 entity values
- **THEN** it SHALL complete within 30 seconds using blocking indexing strategies (sorted neighborhood, prefix blocking) to avoid O(n^2) pairwise comparison

### Requirement: Disambiguation result format
The engine SHALL return disambiguation results as clusters with a canonical value, variant list, and confidence scores.

#### Scenario: Cluster output structure
- **WHEN** a cluster is formed from values ["J. Smith", "Smith, J.", "John Smith"]
- **THEN** the result SHALL include canonical_value (highest frequency or longest form), variants with similarity scores, and a cluster_id

### Requirement: Disambiguation Python fallback
The Python disambiguation endpoint SHALL delegate to the engine when available and fall back to local fuzzy matching when it is not.

#### Scenario: Engine available
- **WHEN** the engine is healthy and a disambiguation request arrives
- **THEN** the backend SHALL delegate to `compute_disambiguation` pipeline

#### Scenario: Engine unavailable
- **WHEN** the engine is not reachable
- **THEN** the backend SHALL use the existing Python disambiguation logic
