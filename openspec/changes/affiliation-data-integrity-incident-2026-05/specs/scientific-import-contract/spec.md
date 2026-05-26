## ADDED Requirements

### Requirement: Scientific import MUST NOT mirror publisher into affiliation
The `_ingest_records` helper in `backend/routers/api_import.py` SHALL NOT write `EnrichedRecord.publisher` into `attributes_json.affiliation`. The publisher field carries provider-source metadata (often a journal display name from OpenAlex's `primary_location.source`); affiliations represent institutional anchors and must come exclusively from `EnrichedRecord.affiliations` and `EnrichedRecord.canonical_affiliations`.

#### Scenario: Provider returns publisher but no affiliations
- **WHEN** an `EnrichedRecord` arrives with `publisher = "Journal of Medical Library Association"` and `affiliations = []`
- **THEN** the persisted entity's `attributes_json` contains `publisher` under the `publisher` key
- **AND** does not contain any `affiliation` or `affiliations` keys

#### Scenario: Provider returns both publisher and real affiliations
- **WHEN** an `EnrichedRecord` arrives with `publisher = "Nature"` and `affiliations = ["MIT, US", "Stanford University, US"]`
- **THEN** the persisted entity's `attributes_json.publisher` equals `"Nature"`
- **AND** `attributes_json.affiliation` equals `"MIT, US; Stanford University, US"`
- **AND** `attributes_json.affiliations` equals `["MIT, US", "Stanford University, US"]`

#### Scenario: Provider returns neither publisher nor affiliations
- **WHEN** an `EnrichedRecord` arrives with both fields empty
- **THEN** the persisted entity's `attributes_json` contains neither `publisher`, `affiliation`, nor `affiliations` keys

### Requirement: Scientific import MUST preserve structured affiliation layers when present
When `EnrichedRecord.canonical_affiliations` or `EnrichedRecord.author_affiliations` carry entries, the importer SHALL persist them under `attributes_json.canonical_affiliations` and `attributes_json.author_affiliations` respectively, using `model_dump()` or equivalent dataclass serialization.

#### Scenario: OpenAlex authorship contains institutions
- **WHEN** OpenAlex returns an authorship with two institutions per author
- **THEN** `attributes_json.canonical_affiliations` is a list of dicts with `name`, `country_code`, and optional ROR/OpenAlex identifiers
- **AND** `attributes_json.author_affiliations` maps each author to their institution list
- **AND** these structures persist regardless of whether `attributes_json.affiliation` is populated
