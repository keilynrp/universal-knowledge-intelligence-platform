## ADDED Requirements

### Requirement: Analytics endpoints delegate to Rust engine
The analytics endpoints (`/analyzers/topics`, `/analyzers/cooccurrence`, `/analyzers/clusters`, `/analyzers/correlation`) SHALL attempt to delegate computation to the Rust engine via `EngineClient.process_analytics()` before falling back to the Python `TopicAnalyzer` / `CorrelationAnalyzer`.

#### Scenario: Engine available and responds successfully
- **WHEN** the Rust engine is reachable and returns a valid analytics response
- **THEN** the endpoint SHALL return the engine's result converted to the existing API response format
- **THEN** the result SHALL be cached in `_analytics_cache` with the same TTL as Python results

#### Scenario: Engine unavailable
- **WHEN** the Rust engine is not configured or unreachable
- **THEN** the endpoint SHALL fall back to the Python `TopicAnalyzer` / `CorrelationAnalyzer`
- **THEN** no error SHALL be visible to the client

#### Scenario: Engine returns an error
- **WHEN** the Rust engine is reachable but returns a processing error
- **THEN** the endpoint SHALL log a warning and fall back to Python
- **THEN** the client SHALL receive a successful response from the Python path

#### Scenario: Cached result exists
- **WHEN** a cached result exists for the request parameters
- **THEN** the cached result SHALL be returned without attempting engine delegation
- **THEN** no gRPC call SHALL be made

### Requirement: Analytics delegation helper
The system SHALL provide a shared helper `try_engine_analytics()` in `backend/services/engine_delegation.py` that encapsulates the engine call, response conversion, and error handling.

#### Scenario: Helper returns converted result on success
- **WHEN** the engine returns a valid `AnalyticsResponse`
- **THEN** the helper SHALL convert the proto response to the Python dict format matching the existing API contract
- **THEN** the helper SHALL return the converted dict

#### Scenario: Helper returns None on failure
- **WHEN** the engine call fails for any reason (network, timeout, processing error)
- **THEN** the helper SHALL return `None`
- **THEN** the helper SHALL log a warning with the failure reason

### Requirement: Analytics response format parity
The delegated engine response SHALL match the existing Python response format field-for-field for each analytics mode.

#### Scenario: Topics response format
- **WHEN** the engine returns a topics result
- **THEN** the response SHALL contain a list of `{"concept": str, "count": int}` entries sorted by count descending

#### Scenario: Cooccurrence response format
- **WHEN** the engine returns a cooccurrence result
- **THEN** the response SHALL contain a list of `{"concept_a": str, "concept_b": str, "pmi": float}` entries

#### Scenario: Clusters response format
- **WHEN** the engine returns a clusters result
- **THEN** the response SHALL contain a list of `{"cluster_id": int, "seed": str, "members": [str]}` entries

#### Scenario: Correlation response format
- **WHEN** the engine returns a correlation result
- **THEN** the response SHALL contain a list of `{"field_a": str, "field_b": str, "cramers_v": float, "strength": str}` entries
