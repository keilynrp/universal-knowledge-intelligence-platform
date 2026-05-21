## ADDED Requirements

### Requirement: ROR identifiers are normalized for downstream matching
UKIP SHALL normalize ROR identifiers into a stable representation suitable for authority matching.

#### Scenario: ROR is a URL
- **WHEN** a source provides `https://ror.org/03yrm5c26`
- **THEN** the normalized affiliation preserves a consistent ROR identifier that downstream consumers can compare

#### Scenario: ROR is absent
- **WHEN** an institution lacks ROR
- **THEN** UKIP preserves other available identifiers and marks the institution as ROR-unresolved

### Requirement: Institution candidates can be extracted from persisted affiliations
UKIP SHALL expose or provide a helper for extracting institution authority candidates from persisted affiliation metadata.

#### Scenario: Persisted affiliation contains ROR
- **WHEN** the helper reads `attributes_json` with a ROR-backed canonical affiliation
- **THEN** it returns an institution candidate with name, ROR, provider ID, and country code

#### Scenario: Persisted affiliation has duplicate institutions
- **WHEN** multiple author affiliations reference the same ROR-backed institution
- **THEN** the helper returns a single deduplicated institution candidate
