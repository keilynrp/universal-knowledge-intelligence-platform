# import-affiliation-field-isolation Specification

## Purpose
TBD - created by archiving change affiliation-data-integrity-incident-2026-05. Update Purpose after archive.
## Requirements
### Requirement: Publisher MUST NOT be written into the affiliation field
The `_ingest_records` helper in `backend/routers/api_import.py` and any equivalent ingestion path SHALL NOT write `EnrichedRecord.publisher` into `attributes_json.affiliation` or `attributes_json.affiliations`. Publisher carries provider-source metadata (frequently a journal display name from OpenAlex `primary_location.source.display_name`); affiliations are institutional anchors.

#### Scenario: Provider returns publisher but no affiliations
- **WHEN** an `EnrichedRecord` arrives with `publisher = "Journal of Medical Library Association"` and `affiliations = []`
- **THEN** the persisted entity's `attributes_json.publisher` equals `"Journal of Medical Library Association"`
- **AND** `attributes_json` contains neither `affiliation` nor `affiliations` keys

#### Scenario: Provider returns publisher resembling an institution name
- **WHEN** an `EnrichedRecord` arrives with `publisher = "Massachusetts Institute of Technology Press"` (a publisher whose name contains an institution) and `affiliations = []`
- **THEN** `attributes_json.affiliation` is not created
- **AND** the publisher value is stored only under `attributes_json.publisher`

### Requirement: Affiliation fields MUST be sourced exclusively from `EnrichedRecord.affiliations`
When `_ingest_records` writes `attributes_json.affiliation` (joined string) and `attributes_json.affiliations` (list), the values SHALL be derived from `EnrichedRecord.affiliations` only, with no fallback to `publisher`, `venue`, `source_title`, or any other field.

#### Scenario: Provider returns real affiliations alongside publisher
- **WHEN** an `EnrichedRecord` arrives with `publisher = "Nature"` and `affiliations = ["MIT, US", "Stanford University, US"]`
- **THEN** `attributes_json.publisher` equals `"Nature"`
- **AND** `attributes_json.affiliation` equals `"MIT, US; Stanford University, US"`
- **AND** `attributes_json.affiliations` equals `["MIT, US", "Stanford University, US"]`

#### Scenario: Provider returns an empty affiliations list
- **WHEN** an `EnrichedRecord` arrives with `affiliations = []`
- **THEN** `attributes_json.affiliation` is not created
- **AND** `attributes_json.affiliations` is not created

#### Scenario: Provider returns whitespace-only affiliation strings
- **WHEN** an `EnrichedRecord` arrives with `affiliations = ["   ", ""]`
- **THEN** the empty/whitespace entries are filtered out
- **AND** if all entries were empty, no `affiliation` or `affiliations` key is created

