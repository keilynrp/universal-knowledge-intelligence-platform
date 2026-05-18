## ADDED Requirements

### Requirement: Disambiguation endpoint delegates to Rust engine for large datasets
The `/disambiguate/{field}` endpoint SHALL delegate to the Rust `compute_disambiguation` pipeline when the number of unique values exceeds a configurable threshold (default: 100).

#### Scenario: Value count exceeds threshold and engine is available
- **WHEN** the number of unique values for the field exceeds `ENGINE_DELEGATION_THRESHOLD` (default 100)
- **AND** the Rust engine is reachable
- **THEN** the endpoint SHALL delegate disambiguation to `EngineClient.process_disambiguation()`
- **THEN** the response SHALL be converted to the existing `{"groups": [...], "total_groups": int}` format

#### Scenario: Value count below threshold
- **WHEN** the number of unique values is at or below the threshold
- **THEN** the endpoint SHALL use the Python `_build_disambig_groups` path without attempting engine delegation

#### Scenario: Engine unavailable for large dataset
- **WHEN** the value count exceeds the threshold but the engine is unreachable
- **THEN** the endpoint SHALL fall back to Python `_build_disambig_groups`
- **THEN** a warning SHALL be logged

#### Scenario: Engine returns error for disambiguation
- **WHEN** the engine is reachable but the disambiguation pipeline fails
- **THEN** the endpoint SHALL fall back to Python
- **THEN** the client SHALL receive a successful response

### Requirement: Disambiguation delegation helper
The system SHALL provide `try_engine_disambiguation()` in `backend/services/engine_delegation.py`.

#### Scenario: Successful delegation converts clusters to groups
- **WHEN** the engine returns a `DisambiguationResponse` with clusters
- **THEN** the helper SHALL convert each `DisambiguationCluster` to the existing group format: `{"canonical": str, "variations": [str], "count": int}`
- **THEN** the helper SHALL return the converted groups list

#### Scenario: Helper returns None on failure
- **WHEN** the engine call fails
- **THEN** the helper SHALL return `None`

### Requirement: Configurable delegation threshold
The delegation threshold SHALL be configurable via the `ENGINE_DELEGATION_THRESHOLD` environment variable.

#### Scenario: Custom threshold via environment
- **WHEN** `ENGINE_DELEGATION_THRESHOLD` is set to `500`
- **THEN** disambiguation delegation SHALL only trigger for datasets with more than 500 unique values

#### Scenario: Default threshold
- **WHEN** `ENGINE_DELEGATION_THRESHOLD` is not set
- **THEN** the default threshold of 100 SHALL be used
