## ADDED Requirements

### Requirement: Configurable cascade order via environment variable
The system SHALL support an optional `ENRICHMENT_CASCADE` environment variable containing a comma-separated list of provider identifiers. When set, only the listed providers SHALL be used, in the specified order.

#### Scenario: Custom cascade order
- **WHEN** `ENRICHMENT_CASCADE=openalex,crossref,pubmed` is set
- **THEN** the enrichment worker SHALL only attempt OpenAlex, Crossref, and PubMed (in that order) and skip all other providers

#### Scenario: Default cascade when env var is unset
- **WHEN** `ENRICHMENT_CASCADE` is not set
- **THEN** the system SHALL use the full default cascade: `scopus,wos,openalex,crossref,pubmed,semantic_scholar,dblp,scholar`

#### Scenario: Invalid provider name in cascade
- **WHEN** `ENRICHMENT_CASCADE` contains an unrecognized provider name
- **THEN** the system SHALL log a warning at startup and skip the unrecognized provider

### Requirement: Provider registry
The system SHALL maintain a registry mapping provider identifiers to adapter instances and circuit breakers. Valid identifiers SHALL be: `scopus`, `wos`, `openalex`, `crossref`, `pubmed`, `semantic_scholar`, `dblp`, `scholar`.

#### Scenario: Registry lookup
- **WHEN** the enrichment worker needs to execute the cascade
- **THEN** it SHALL iterate through the configured provider list, looking up each adapter and circuit breaker from the registry

### Requirement: Provider health monitoring endpoint
The system SHALL expose `GET /enrichment/providers` returning the status of each registered provider: name, is_active, circuit breaker state (closed/open/half_open), success count, failure count, and last used timestamp.

#### Scenario: All providers healthy
- **WHEN** no circuit breakers are tripped
- **THEN** all providers SHALL show `circuit_state: "closed"` in the response

#### Scenario: Provider circuit open
- **WHEN** OpenAlex's circuit breaker has tripped
- **THEN** OpenAlex SHALL show `circuit_state: "open"` and include the recovery timestamp

#### Scenario: Inactive BYOK provider
- **WHEN** Scopus has no API key configured
- **THEN** Scopus SHALL show `is_active: false` in the response

### Requirement: EnrichedRecord extended fields
The `EnrichedRecord` NDO SHALL be extended with the following optional fields (all defaulting to `None`): `funding: Optional[List[str]]`, `references_count: Optional[int]`, `tldr: Optional[str]`, `influential_citation_count: Optional[int]`, `license: Optional[str]`, `mesh_terms: Optional[List[str]]`, `venue: Optional[str]`.

#### Scenario: Existing adapters unaffected
- **WHEN** an existing adapter (OpenAlex, Scopus, WoS) returns an `EnrichedRecord` without setting new fields
- **THEN** the new fields SHALL default to `None` and no errors SHALL occur

#### Scenario: New adapter populates extended fields
- **WHEN** the Crossref adapter returns a record with funding data
- **THEN** the `funding` field SHALL contain funder names and persist to `attributes_json`

### Requirement: Extended fields persistence
The enrichment worker SHALL persist non-None extended fields from `EnrichedRecord` into `entity.attributes_json` alongside existing enrichment data.

#### Scenario: TLDR persisted
- **WHEN** Semantic Scholar enriches an entity with a TLDR
- **THEN** `attributes_json` SHALL contain `"tldr": "<text>"` after enrichment

#### Scenario: MeSH terms persisted
- **WHEN** PubMed enriches an entity with MeSH terms
- **THEN** `attributes_json` SHALL contain `"mesh_terms": [...]` after enrichment

### Requirement: Cascade short-circuits on first match
The cascade SHALL stop at the first provider that returns a non-empty result. Subsequent providers SHALL NOT be called for that entity.

#### Scenario: OpenAlex matches
- **WHEN** OpenAlex returns a result for an entity
- **THEN** Crossref, PubMed, Semantic Scholar, DBLP, and Scholar SHALL NOT be called for that entity

#### Scenario: OpenAlex misses, Crossref matches
- **WHEN** OpenAlex returns empty but Crossref returns a result
- **THEN** PubMed and subsequent providers SHALL NOT be called for that entity
