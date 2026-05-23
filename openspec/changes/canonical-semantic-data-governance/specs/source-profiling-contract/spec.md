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

### Requirement: Source profiling covers representative real-world payload shapes
UKIP source profiling SHALL handle representative payload shapes including flat CSV files, nested API responses, and structured academic-provider payloads.

#### Scenario: Flat CSV with mixed-quality columns is profiled
- **WHEN** a user imports a CSV file containing columns such as `title`, `author`, `year`, `doi`, `institution`, and several empty or sparse columns
- **THEN** UKIP detects inferred types (string, integer, identifier), computes sparsity per column, extracts sample values, and flags `doi` as a candidate identifier
- **AND** columns with sparsity above a governed threshold are flagged as low-evidence fields in the profile

#### Scenario: Paginated REST API response is profiled
- **WHEN** UKIP ingests records from a paginated REST API connector that returns JSON objects with nested `metadata.authors[].affiliation` structures
- **THEN** UKIP flattens nested paths into profiled field entries (e.g., `metadata.authors[].affiliation`)
- **AND** it detects array cardinality, mixed types within arrays, and candidate semantic roles for nested fields

#### Scenario: OpenAlex Works payload is profiled
- **WHEN** UKIP ingests an OpenAlex Works response containing fields such as `id`, `doi`, `title`, `authorships[].author.display_name`, `authorships[].institutions[].ror`, `concepts[].display_name`, `host_venue.issn_l`
- **THEN** UKIP profiles `doi` and `id` as candidate identifiers, `authorships[].author.display_name` as a person candidate, `authorships[].institutions[].ror` as an organization/institution candidate, and `concepts[].display_name` as a concept/topic candidate
- **AND** nested array depths and value distributions are captured in the profile

#### Scenario: Crossref Works payload is profiled
- **WHEN** UKIP ingests a Crossref Works response containing fields such as `DOI`, `title[]`, `author[].given`, `author[].family`, `author[].affiliation[].name`, `subject[]`, `container-title[]`, `ISSN[]`
- **THEN** UKIP profiles `DOI` as a candidate identifier, `author[].family` and `author[].given` as person-name candidates, `author[].affiliation[].name` as an organization candidate, and `subject[]` as a topic/concept candidate
- **AND** it handles Crossref-specific array wrapping (e.g., `title` as a single-element array) without misclassifying cardinality

#### Scenario: Source with no recognizable identifiers is profiled
- **WHEN** a user imports a dataset that contains no DOIs, ORCIDs, ROR IDs, ISSNs, or other standard identifiers
- **THEN** UKIP completes profiling without error, marks zero candidate identifiers, and flags the dataset as identifier-sparse in the profile summary
- **AND** the profile still captures field names, types, sparsity, and sample values for mapping suggestion input
