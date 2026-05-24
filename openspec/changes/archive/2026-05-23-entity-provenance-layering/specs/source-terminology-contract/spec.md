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

#### Scenario: Authority resolver source is distinct from enrichment provider
- **WHEN** an entity has both enrichment provider and authority resolver references
- **THEN** the enrichment provider label refers to the data enrichment source (e.g., OpenAlex, Crossref)
- **AND** the authority source label refers to the identity resolution source (e.g., ROR, ORCID, Wikidata)

### Requirement: Duplicate ambiguous source labels are not rendered
The entity detail view SHALL NOT render multiple fields with the same generic "Source" label when they represent different provenance layers.

#### Scenario: Entity has ingestion source and enrichment provider
- **WHEN** an entity has both `source` and `enrichment_source`
- **THEN** the detail view shows them with distinct labels

#### Scenario: All three source types are present
- **WHEN** an entity has an ingestion source, an enrichment provider, and an authority record with resolver source
- **THEN** the detail view uses three distinct labels: "Ingestion source", "Enrichment provider", and "Authority source"
- **AND** no two fields share the same label

### Requirement: Source terminology translations cover supported locales
UKIP SHALL provide localized translations for all provenance-related labels in every supported locale.

#### Scenario: English translations exist for provenance labels
- **WHEN** the UI locale is English
- **THEN** the labels "Ingestion source", "Enrichment provider", "Authority source", "Original ingestion", "UKIP normalized identity", "External enrichment", and "Authority and audit" are defined in the EN translation file

#### Scenario: Spanish translations exist for provenance labels
- **WHEN** the UI locale is Spanish
- **THEN** equivalent Spanish labels are defined in the ES translation file for all provenance-related terms

#### Scenario: Null-reason labels are translated
- **WHEN** a null-reason code is displayed to the user
- **THEN** the corresponding human-readable copy is available in all supported locales
