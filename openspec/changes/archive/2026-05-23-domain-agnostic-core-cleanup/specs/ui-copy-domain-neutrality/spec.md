## ADDED Requirements

### Requirement: Import and entity UI avoid commerce-first examples
UKIP import and entity detail UI SHALL avoid using commerce-first examples in generic labels and helper text.

#### Scenario: Canonical identifier help text appears
- **WHEN** help text explains canonical identifiers
- **THEN** it uses domain-neutral or current strategic examples such as DOI, ORCID, ROR, local identifier, accession number, or record ID
- **AND** commerce examples appear only when the active adapter or domain pack is commerce-specific

#### Scenario: Secondary label appears
- **WHEN** the UI explains secondary label
- **THEN** it uses examples such as author, institution, venue, source, or organization
- **AND** does not pair brand with author in generic scientific intelligence workflows

### Requirement: Destructive data actions use records/entities language
Destructive generic actions SHALL refer to records or entities, not product records.

#### Scenario: User opens import/export purge action
- **WHEN** the purge action is displayed in a generic workspace
- **THEN** copy says records or entities
- **AND** export filenames avoid product-specific names
