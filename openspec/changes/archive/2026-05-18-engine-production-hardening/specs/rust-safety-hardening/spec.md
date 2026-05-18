## ADDED Requirements

### Requirement: SQL column whitelist in analytics field queries
The `load_field_data` function SHALL validate field names against a hardcoded whitelist of known RawEntity columns before constructing SQL queries.

#### Scenario: Valid column requested
- **WHEN** a field filter matches a column in the whitelist
- **THEN** the query SHALL execute normally

#### Scenario: Unknown column requested
- **WHEN** a field filter does NOT match any column in the whitelist
- **THEN** the pipeline SHALL return `PipelineError::Validation` with the invalid column name
- **THEN** no SQL query SHALL be executed

### Requirement: No panic on mismatched column lengths in Cramér's V
The `cramers_v` function SHALL return an error instead of panicking when input arrays have different lengths.

#### Scenario: Arrays have equal length
- **WHEN** `x.len() == y.len()`
- **THEN** computation SHALL proceed normally

#### Scenario: Arrays have different lengths
- **WHEN** `x.len() != y.len()`
- **THEN** the function SHALL return `Err(PipelineError::Internal("mismatched column lengths"))`
- **THEN** the process SHALL NOT panic

### Requirement: No unreachable!() on user-controlled mode values
All `match` arms on pipeline mode strings SHALL return errors for unknown modes instead of using `unreachable!()`.

#### Scenario: Unknown analytics mode
- **WHEN** `AnalyticsPipeline::process` receives an unknown mode
- **THEN** it SHALL return `PipelineError::Validation` with the unknown mode name

#### Scenario: Unknown normalization mode
- **WHEN** `NormalizationPipeline::process` receives an unknown mode
- **THEN** it SHALL return `PipelineError::Validation` with the unknown mode name

### Requirement: Bounded input sizes for engine pipelines
All engine pipelines SHALL enforce maximum input sizes in their `validate()` methods.

#### Scenario: Connector queries exceed 200
- **WHEN** `ConnectorRequest.queries` has more than 200 entries
- **THEN** validation SHALL return `PipelineError::Validation`

#### Scenario: Disambiguation values exceed 50,000
- **WHEN** `DisambiguationRequest.values` has more than 50,000 entries
- **THEN** validation SHALL return `PipelineError::Validation`

#### Scenario: Normalization values exceed 50,000
- **WHEN** `NormalizationRequest.values` has more than 50,000 entries
- **THEN** validation SHALL return `PipelineError::Validation`
