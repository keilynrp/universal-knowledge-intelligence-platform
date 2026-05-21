## ADDED Requirements

### Requirement: Accepted institution matches persist as authority records
When an institution candidate is accepted, UKIP SHALL persist a canonical institution authority record with source identifiers and aliases.

#### Scenario: ROR-backed candidate is accepted
- **WHEN** a user or auto-accept rule accepts a ROR-backed candidate
- **THEN** UKIP stores the canonical name, ROR ID, aliases, country, and confidence/status

#### Scenario: OpenAlex-backed candidate is accepted without ROR
- **WHEN** a candidate has OpenAlex institution ID but no ROR
- **THEN** UKIP stores the OpenAlex ID and marks ROR as unresolved

### Requirement: Accepted institution authority records are reusable
Accepted institution authority records SHALL be reused for later affiliation candidates that match the same identifiers.

#### Scenario: Later import has same ROR ID
- **WHEN** a new affiliation candidate has a ROR ID already accepted
- **THEN** UKIP links it to the existing institution authority record rather than creating a duplicate
