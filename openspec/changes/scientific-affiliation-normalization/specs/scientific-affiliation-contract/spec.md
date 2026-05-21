## ADDED Requirements

### Requirement: Normalized enrichment records preserve structured affiliations
The normalized scientific enrichment record SHALL support structured author-level and canonical institution-level affiliations while preserving the legacy text affiliation list.

#### Scenario: Record has no structured affiliations
- **WHEN** an adapter only provides text affiliations
- **THEN** the normalized record remains valid
- **AND** `affiliations` contains the text values

#### Scenario: Record has structured author affiliations
- **WHEN** an adapter provides author-institution relationships
- **THEN** the normalized record includes `author_affiliations`
- **AND** each author affiliation includes author name, optional ORCID, optional provider author ID, author position/order, and institution entries

#### Scenario: Record has canonical affiliations
- **WHEN** multiple authors reference the same institution
- **THEN** the normalized record includes one deduplicated `canonical_affiliations` entry for that institution

### Requirement: Canonical affiliation entries preserve authority identifiers
Canonical affiliation entries SHALL preserve ROR IDs, OpenAlex institution IDs, country codes, institution type, and lineage when provided by the source.

#### Scenario: ROR-backed institution is present
- **WHEN** a source institution includes a ROR ID
- **THEN** the canonical affiliation preserves that ROR ID

#### Scenario: OpenAlex-only institution is present
- **WHEN** a source institution lacks ROR but includes an OpenAlex institution ID
- **THEN** the canonical affiliation preserves the OpenAlex ID
