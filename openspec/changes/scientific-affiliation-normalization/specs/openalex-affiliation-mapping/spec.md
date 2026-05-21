## ADDED Requirements

### Requirement: OpenAlex adapter maps authorships institutions
The OpenAlex adapter SHALL parse `authorships[].institutions[]` into normalized structured affiliation fields.

#### Scenario: OpenAlex work has author institutions
- **WHEN** an OpenAlex work includes `authorships[].institutions[]`
- **THEN** the parsed `EnrichedRecord` includes author-affiliation relationships
- **AND** each institution includes display name and available identifiers

#### Scenario: OpenAlex institution has ROR
- **WHEN** an institution includes `ror`
- **THEN** the parsed canonical affiliation includes the ROR value

#### Scenario: OpenAlex institution has country code
- **WHEN** an institution includes `country_code`
- **THEN** the parsed canonical affiliation includes that country code

### Requirement: OpenAlex adapter maintains legacy affiliation compatibility
The OpenAlex adapter SHALL continue populating `affiliations` with readable text values derived from canonical institutions.

#### Scenario: Canonical institutions are parsed
- **WHEN** an OpenAlex work has canonical institutions
- **THEN** `affiliations` includes human-readable institution strings
- **AND** existing geographic fallback consumers can continue reading text affiliation values
