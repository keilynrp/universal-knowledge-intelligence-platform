## ADDED Requirements

### Requirement: Scientific connector fetches can delegate to Rust engine
The scientific import endpoints SHALL support delegating API fetches (OpenAlex, Crossref, PubMed) to the Rust `compute_connectors` pipeline via an opt-in mechanism.

#### Scenario: Delegation enabled and engine available
- **WHEN** a connector fetch is requested with engine delegation enabled
- **AND** the Rust engine is reachable
- **THEN** the system SHALL call `EngineClient.process_connectors()` with the source, query type, and queries
- **THEN** the returned publications SHALL be converted to the Python `Publication` format

#### Scenario: Delegation enabled but engine unavailable
- **WHEN** engine delegation is enabled but the engine is unreachable
- **THEN** the system SHALL fall back to the Python import adapter
- **THEN** a warning SHALL be logged

#### Scenario: Delegation not enabled
- **WHEN** engine delegation is not explicitly enabled
- **THEN** the system SHALL use the existing Python import adapters

### Requirement: Connector delegation helper
The system SHALL provide `try_engine_connectors()` in `backend/services/engine_delegation.py`.

#### Scenario: Successful delegation converts publications
- **WHEN** the engine returns a `ConnectorResponse` with publications
- **THEN** the helper SHALL convert proto `Publication` messages to Python dicts matching the existing adapter output format
- **THEN** the helper SHALL return the list of publication dicts

#### Scenario: Helper returns None on failure
- **WHEN** the engine call fails
- **THEN** the helper SHALL return `None`

### Requirement: Connector delegation does not duplicate rate limiting
The Rust engine has its own token-bucket rate limiter. The Python adapter has its own rate limiting.

#### Scenario: No double rate limiting
- **WHEN** delegating to the Rust engine
- **THEN** the Python-side rate limiter SHALL NOT be applied (the engine handles its own rate limiting)
- **THEN** only the engine's rate limiter SHALL govern API call frequency
