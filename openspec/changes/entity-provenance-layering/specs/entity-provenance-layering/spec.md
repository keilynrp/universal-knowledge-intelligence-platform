## ADDED Requirements

### Requirement: Entity detail separates data provenance layers
The entity detail view SHALL separate fields into original ingestion data, UKIP normalized identity, external enrichment, and authority/audit sections.

#### Scenario: Entity has original and enriched data
- **WHEN** an entity includes both ingestion fields and enrichment fields
- **THEN** original ingestion fields appear in an "Original ingestion" section
- **AND** enrichment fields appear in an "External enrichment" section

#### Scenario: Entity has normalized fields
- **WHEN** an entity has `primary_label`, `canonical_id`, `entity_type`, or validation fields
- **THEN** those fields appear in a "UKIP normalized identity" section

### Requirement: Entity detail preserves original imported values
The entity detail view SHALL preserve original imported values separately from normalized and enriched values.

#### Scenario: Original SKU differs from enriched DOI
- **WHEN** an original record includes SKU and enrichment resolves DOI
- **THEN** SKU is shown as an original identifier
- **AND** DOI is shown as an enrichment identifier
