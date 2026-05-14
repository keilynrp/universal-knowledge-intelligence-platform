## ADDED Requirements

### Requirement: Topic modeling pipeline
The engine SHALL provide a `compute_topics` pipeline that accepts entity data for a domain and produces top topics, co-occurrence pairs with PMI scores, and topic clusters.

#### Scenario: Extract top topics
- **WHEN** the pipeline receives a domain_id and a limit parameter
- **THEN** it SHALL return the top N topics ranked by frequency, derived from the enrichment_concepts field of entities in that domain

#### Scenario: Compute co-occurrence with PMI
- **WHEN** the pipeline receives a domain_id with mode="cooccurrence"
- **THEN** it SHALL return concept pairs with their pointwise mutual information (PMI) scores, filtering out pairs below a minimum co-occurrence threshold

#### Scenario: Greedy topic clustering
- **WHEN** the pipeline receives a domain_id with mode="clusters"
- **THEN** it SHALL group concepts into clusters using greedy seed assignment (highest-frequency concept as seed, assign co-occurring concepts), matching the behavior of `TopicAnalyzer.topic_clusters()`

### Requirement: Correlation analysis pipeline
The engine SHALL provide a `compute_correlation` pipeline that computes Cramer's V between categorical entity fields for a given domain.

#### Scenario: Compute field correlations
- **WHEN** the pipeline receives a domain_id and optional field filters
- **THEN** it SHALL return field pairs with their Cramer's V statistic and strength classification (strong >= 0.5, moderate >= 0.2, weak < 0.2)

#### Scenario: Skip high-cardinality fields
- **WHEN** a field has cardinality exceeding 50 unique values
- **THEN** the engine SHALL skip that field in correlation analysis, matching the `_MAX_CARDINALITY` guard in the Python implementation

#### Scenario: Skip internal fields
- **WHEN** a field is in the skip list (id, created_at, updated_at, attributes_json, etc.)
- **THEN** the engine SHALL exclude it from correlation analysis

### Requirement: Analytics Python fallback
The Python `backend/analyzers/` modules SHALL delegate to engine compute pipelines when available, falling back to local numpy/Python implementations when the engine is not reachable.

#### Scenario: Engine available for topic analysis
- **WHEN** `EngineClient.health()` returns True and the frontend requests `/analyzers/topics/{domain_id}`
- **THEN** the backend SHALL delegate to `EngineClient.process_sync(pipeline="compute_topics", ...)` and map the response

#### Scenario: Engine unavailable for correlation
- **WHEN** the engine is not reachable
- **THEN** the backend SHALL use `CorrelationAnalyzer` locally without error
