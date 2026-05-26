# import-structured-layer-persistence Specification

## Purpose
TBD - created by archiving change affiliation-data-integrity-incident-2026-05. Update Purpose after archive.
## Requirements
### Requirement: Canonical affiliations MUST be persisted when the provider supplies them
When `EnrichedRecord.canonical_affiliations` carries one or more `CanonicalAffiliation` entries, the importer SHALL serialize them into `attributes_json.canonical_affiliations` as a list of dicts containing at minimum `name`, and the optional fields `country_code`, `ror`, `openalex_id`, `type`, and `lineage` whenever the provider returned them.

#### Scenario: OpenAlex authorship contains institutions with ROR identifiers
- **WHEN** OpenAlex returns an authorship with two institutions, both with ROR IDs and country codes
- **THEN** `attributes_json.canonical_affiliations` is a list of two dicts
- **AND** each dict contains `name`, `country_code`, and `ror`
- **AND** the dict keys match the field names of the `CanonicalAffiliation` dataclass

#### Scenario: Institution lacks a ROR identifier
- **WHEN** OpenAlex returns an institution with `display_name` and `country_code` but no `ror`
- **THEN** the persisted dict contains `name` and `country_code`
- **AND** the `ror` key is absent or set to `null` (never an empty string)

### Requirement: Author-level affiliations MUST be persisted when the provider supplies them
When `EnrichedRecord.author_affiliations` carries entries, the importer SHALL serialize them into `attributes_json.author_affiliations` as a list of dicts. Each entry SHALL preserve the author identity (`author_name`, optional `author_orcid`, optional `author_openalex_id`), the author's ordinal position, and the list of institutions associated with that author for that publication.

#### Scenario: A paper has three authors, each with a distinct affiliation
- **WHEN** OpenAlex returns three authorships, each with one institution
- **THEN** `attributes_json.author_affiliations` is a list of three dicts
- **AND** each dict contains `author_name`, `author_order`, and `institutions` (list with one entry)
- **AND** the institutions field references the same institution name as in `attributes_json.canonical_affiliations`

#### Scenario: A paper has an author with no listed institutions
- **WHEN** OpenAlex returns an authorship where `institutions = []`
- **THEN** the corresponding entry in `attributes_json.author_affiliations` has `institutions: []`
- **AND** the entry is still present so the author count remains accurate

### Requirement: Structured layers MUST persist independently of the scalar affiliation field
The presence of `attributes_json.canonical_affiliations` or `attributes_json.author_affiliations` SHALL NOT depend on whether `attributes_json.affiliation` was set. The structured layers are persisted whenever the provider supplies the data, regardless of whether the joined display string was also created.

#### Scenario: Provider returns canonical_affiliations but legacy `affiliations` is empty
- **WHEN** an `EnrichedRecord` arrives with `canonical_affiliations = [{name: "MIT", ...}]` but `affiliations = []`
- **THEN** `attributes_json.canonical_affiliations` is persisted with the MIT entry
- **AND** `attributes_json.affiliation` is not created (per the field-isolation spec)
- **AND** the entity still has structured affiliation data accessible by analytics and the frontend

