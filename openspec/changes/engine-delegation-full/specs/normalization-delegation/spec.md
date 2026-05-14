## ADDED Requirements

### Requirement: Normalization rule application delegates to Rust engine for bulk operations
The `/rules/apply` endpoint SHALL delegate bulk value normalization to the Rust `compute_normalization` pipeline when the number of values to normalize exceeds the delegation threshold (default: 100).

#### Scenario: Bulk exact-match rules delegated to engine
- **WHEN** applying exact-match normalization rules to more than 100 entity values
- **AND** the Rust engine is available
- **THEN** the system SHALL batch the values and rules into a single `process_normalization()` call
- **THEN** the normalized values SHALL be written back to the database

#### Scenario: Regex rules stay in Python
- **WHEN** applying regex-based normalization rules
- **THEN** the system SHALL always use the Python path (regex rules require per-row evaluation with Python's `re` module)

#### Scenario: Engine unavailable for bulk normalization
- **WHEN** the engine is unreachable during bulk normalization
- **THEN** the system SHALL fall back to the existing Python row-by-row normalization
- **THEN** a warning SHALL be logged

#### Scenario: Small batch stays in Python
- **WHEN** the number of values to normalize is at or below the threshold
- **THEN** the system SHALL use the Python path without attempting engine delegation

### Requirement: Normalization delegation helper
The system SHALL provide `try_engine_normalization()` in `backend/services/engine_delegation.py`.

#### Scenario: Successful delegation returns normalized values
- **WHEN** the engine returns a `NormalizationResponse`
- **THEN** the helper SHALL return a dict mapping original values to their normalized forms
- **THEN** the caller SHALL use this mapping to update database records

#### Scenario: Helper returns None on failure
- **WHEN** the engine call fails
- **THEN** the helper SHALL return `None`
