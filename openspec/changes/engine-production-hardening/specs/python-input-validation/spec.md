## ADDED Requirements

### Requirement: Remove user-supplied API key from AIResolveRequest
The `AIResolveRequest` schema SHALL NOT accept a user-supplied `api_key` field. The system SHALL always use the server-configured OpenAI key.

#### Scenario: Request with api_key field
- **WHEN** a client sends `api_key` in the request body
- **THEN** the field SHALL be ignored (Pydantic model does not define it)

### Requirement: Source allowlist for scientific imports
The scientific import endpoints SHALL validate `source` against the known adapter registry.

#### Scenario: Valid source
- **WHEN** `source` matches a registered adapter (e.g., "openalex", "crossref", "pubmed")
- **THEN** the request SHALL proceed normally

#### Scenario: Invalid source
- **WHEN** `source` does not match any registered adapter
- **THEN** the endpoint SHALL return HTTP 400 before dispatching

### Requirement: Typed config schema for scientific imports
The `config` field in `SearchRequest` and `DoiBatchRequest` SHALL use a typed Pydantic model instead of an untyped dict.

#### Scenario: Known config keys
- **WHEN** config contains only known keys (e.g., `email`, `api_key_name`)
- **THEN** the values SHALL be forwarded to the adapter

#### Scenario: Unknown config keys
- **WHEN** config contains keys not in the schema
- **THEN** they SHALL be rejected by Pydantic validation (HTTP 422)

### Requirement: Domain ID validation in multi-domain endpoints
All domain ID parameters SHALL be validated against `^[a-z][a-z0-9_\-]{0,63}$`.

#### Scenario: Valid domain ID
- **WHEN** a domain_id matches the pattern
- **THEN** the request SHALL proceed

#### Scenario: Invalid domain ID (path traversal attempt)
- **WHEN** a domain_id contains `../` or special characters
- **THEN** the endpoint SHALL return HTTP 422

### Requirement: Values cap before engine delegation
The delegation helpers SHALL enforce a maximum of 50,000 values before forwarding to the engine.

#### Scenario: Values within cap
- **WHEN** the values list has ≤ 50,000 entries
- **THEN** all values SHALL be forwarded to the engine

#### Scenario: Values exceed cap
- **WHEN** the values list has > 50,000 entries
- **THEN** only the first 50,000 SHALL be forwarded
- **THEN** a warning SHALL be logged

### Requirement: Engine health endpoint requires admin role
The `GET /engine/health` and `GET /engine/jobs/{job_id}` endpoints SHALL require admin+ role.

#### Scenario: Admin user
- **WHEN** an admin or super_admin accesses `/engine/health`
- **THEN** the full delegation status SHALL be returned

#### Scenario: Viewer or editor user
- **WHEN** a viewer or editor accesses `/engine/health`
- **THEN** HTTP 403 SHALL be returned
