## ADDED Requirements

### Requirement: Source labels distinguish provenance types
UKIP SHALL use distinct labels for ingestion source, enrichment provider, and authority source.

#### Scenario: Original source is displayed
- **WHEN** the value comes from `source`
- **THEN** the UI labels it "Ingestion source"

#### Scenario: Enrichment source is displayed
- **WHEN** the value comes from `enrichment_source`
- **THEN** the UI labels it "Enrichment provider"

#### Scenario: Authority source is displayed
- **WHEN** the value comes from an authority record or resolver
- **THEN** the UI labels it "Authority source"

### Requirement: Duplicate ambiguous source labels are not rendered
The entity detail view SHALL NOT render multiple fields with the same generic "Source" label when they represent different provenance layers.

#### Scenario: Entity has ingestion source and enrichment provider
- **WHEN** an entity has both `source` and `enrichment_source`
- **THEN** the detail view shows them with distinct labels
