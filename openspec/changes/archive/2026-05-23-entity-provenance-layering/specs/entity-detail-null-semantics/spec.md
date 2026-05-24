## ADDED Requirements

### Requirement: Missing fields show meaningful null reasons
Entity detail fields SHALL explain why important values are missing instead of showing only a dash.

#### Scenario: Canonical ID missing because original identifier was absent
- **WHEN** `canonical_id` is empty and no original identifier exists
- **THEN** the detail view shows "Not provided in original ingestion" or equivalent localized copy

#### Scenario: Canonical ID missing while original identifier exists
- **WHEN** an original identifier exists but `canonical_id` is empty
- **THEN** the detail view shows "Pending normalization" or equivalent localized copy

#### Scenario: Entity type missing while original category exists
- **WHEN** an original category/type exists but `entity_type` is empty
- **THEN** the detail view shows "Pending type mapping" or equivalent localized copy

#### Scenario: Enrichment DOI missing after enrichment
- **WHEN** enrichment has run but DOI is empty
- **THEN** the detail view shows "Not resolved by enrichment provider" or equivalent localized copy

#### Scenario: Enrichment DOI missing before enrichment
- **WHEN** enrichment has not been attempted on the entity
- **THEN** the detail view shows "Enrichment not run" or equivalent localized copy

#### Scenario: Enrichment concepts missing after enrichment
- **WHEN** enrichment has run but concepts/topics are empty
- **THEN** the detail view shows "Not resolved by enrichment provider" with the enrichment source name when available

#### Scenario: Field is not applicable to entity type or domain
- **WHEN** a field does not apply to the entity type or ingestion source
- **THEN** the detail view shows "Not applicable" or equivalent localized copy
- **AND** the field is visually de-emphasized or hidden depending on display preferences

### Requirement: Null-reason codes are computed from entity state
UKIP SHALL implement a field-state helper that derives null-reason codes from entity field values and lifecycle state.

#### Scenario: Field-state helper returns not_provided
- **WHEN** a field was absent from the original ingestion and has no normalized or enriched value
- **THEN** the helper returns `not_provided`

#### Scenario: Field-state helper returns pending_normalization
- **WHEN** a source value exists but the corresponding normalized field is empty
- **THEN** the helper returns `pending_normalization`

#### Scenario: Field-state helper returns unresolved_enrichment
- **WHEN** enrichment has been attempted but the enrichment field is empty
- **THEN** the helper returns `unresolved_enrichment`

#### Scenario: Field-state helper returns not_applicable
- **WHEN** a field is structurally irrelevant to the entity type, domain, or ingestion source
- **THEN** the helper returns `not_applicable`

#### Scenario: Field-state helper returns unknown
- **WHEN** a field is empty and no reliable reason can be determined from entity state
- **THEN** the helper returns `unknown`

### Requirement: Null-reason copy is testable
UKIP SHALL support automated tests that verify null-reason codes and their human-readable copy for representative entity states.

#### Scenario: Test verifies null-state copy for uploaded entity without identifiers
- **WHEN** a test creates an entity from a CSV upload with no identifier columns
- **THEN** the null-reason for `canonical_id` is `not_provided`
- **AND** the display copy matches the expected localized string

#### Scenario: Test verifies null-state copy for enriched entity with missing DOI
- **WHEN** a test creates an entity that has been enriched but DOI was not resolved
- **THEN** the null-reason for `enrichment_doi` is `unresolved_enrichment`
- **AND** the display copy references the enrichment provider

#### Scenario: Test verifies null-state copy for legacy record
- **WHEN** a test evaluates an entity created before import batch metadata was tracked
- **THEN** the null-reason for ingestion metadata fields is `unknown`
- **AND** the display copy shows "Legacy record" or "Unknown ingestion source"
