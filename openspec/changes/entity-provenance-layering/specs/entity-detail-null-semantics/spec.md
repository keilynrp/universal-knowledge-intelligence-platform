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
