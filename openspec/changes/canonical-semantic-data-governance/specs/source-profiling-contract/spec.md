## ADDED Requirements

### Requirement: UKIP profiles arbitrary sources before canonical mapping
UKIP SHALL profile arbitrary ingested sources before accepting or applying canonical mapping suggestions.

#### Scenario: Tabular source is ingested
- **WHEN** a user imports a tabular dataset
- **THEN** UKIP profiles field names, inferred types, sparsity, sample values, value distributions, and candidate identifiers
- **AND** it stores or exposes the profile as evidence for mapping suggestions

#### Scenario: API connector source is ingested
- **WHEN** UKIP ingests records from an API connector
- **THEN** UKIP profiles provider payload fields and nested structures that may map to canonical entities or relationships

### Requirement: Source profiles identify semantic candidates
Source profiles SHALL identify candidate semantic roles without asserting canonical identity.

#### Scenario: Institution-like field is detected
- **WHEN** a field contains organization names, ROR IDs, OpenAlex institution IDs, or affiliation-like strings
- **THEN** the source profile marks it as an organization/institution candidate
- **AND** it does not treat the value as a resolved authority record until reconciliation succeeds

#### Scenario: Place-like field is detected
- **WHEN** a field contains country codes, country names, city names, addresses, coordinates, or spatial coverage terms
- **THEN** the source profile marks it as a geographic candidate
- **AND** it preserves the original raw values for later reconciliation evidence
