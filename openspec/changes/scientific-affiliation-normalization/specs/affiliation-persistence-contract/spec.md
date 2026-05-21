## ADDED Requirements

### Requirement: Ingestion persists structured affiliation metadata
Scientific ingestion SHALL persist structured affiliation metadata in `RawEntity.attributes_json`.

#### Scenario: Record includes canonical affiliations
- **WHEN** `_ingest_records` receives an `EnrichedRecord` with `canonical_affiliations`
- **THEN** the persisted `attributes_json` includes `canonical_affiliations`

#### Scenario: Record includes author affiliations
- **WHEN** `_ingest_records` receives an `EnrichedRecord` with `author_affiliations`
- **THEN** the persisted `attributes_json` includes `author_affiliations`

#### Scenario: Legacy affiliation fields remain available
- **WHEN** structured affiliations are persisted
- **THEN** `attributes_json` also includes `affiliation` and `affiliations` text keys for backwards compatibility

### Requirement: Persisted affiliation metadata avoids raw payload dependency
Downstream institutional consumers SHALL be able to read normalized affiliation metadata without reparsing `raw_response`.

#### Scenario: ROR candidate is needed
- **WHEN** an institution authority workflow reads `attributes_json`
- **THEN** it can find ROR/OpenAlex institution identifiers in normalized affiliation fields
