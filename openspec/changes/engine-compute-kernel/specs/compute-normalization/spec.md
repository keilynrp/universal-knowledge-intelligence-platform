## ADDED Requirements

### Requirement: Text normalization pipeline
The engine SHALL provide a `compute_normalization` pipeline that applies unicode normalization, diacritic stripping, and rule-based transformations to entity field values.

#### Scenario: Unicode NFD normalization and ASCII folding
- **WHEN** the pipeline receives text containing diacritics (e.g., "Muller", "Garcon")
- **THEN** it SHALL apply NFD decomposition followed by combining character removal, producing ASCII equivalents ("Muller", "Garcon")

#### Scenario: Surname-first reformatting
- **WHEN** the pipeline receives a name in VIAF inverted format (e.g., "Smith, John A.")
- **THEN** it SHALL detect and reformat to "John A. Smith"

#### Scenario: Name variant generation
- **WHEN** the pipeline receives a person name
- **THEN** it SHALL generate variants (full name, surname-first, initials-only, first-last only) matching the output of `backend/authority/normalize.py:name_variants()`

### Requirement: Rule-based normalization
The engine SHALL accept a list of normalization rules (pattern, replacement, scope) and apply them in order to input values.

#### Scenario: Apply regex normalization rules
- **WHEN** rules include a pattern-based substitution (e.g., strip trailing whitespace, normalize "Univ." to "University")
- **THEN** the engine SHALL apply each rule in sequence and return the normalized result

#### Scenario: Batch normalization
- **WHEN** the pipeline receives a batch of values with rules
- **THEN** it SHALL normalize all values and return results in the same order as input

### Requirement: Normalization Python fallback
The Python normalization code SHALL delegate to the engine for bulk operations and fall back to local implementation for single-value operations or when the engine is unavailable.

#### Scenario: Bulk normalization delegates to engine
- **WHEN** more than 100 values need normalization and the engine is healthy
- **THEN** the backend SHALL batch them into a single engine call

#### Scenario: Single value uses local Python
- **WHEN** a single value needs normalization
- **THEN** the backend SHALL use local Python implementation directly (no gRPC overhead)
