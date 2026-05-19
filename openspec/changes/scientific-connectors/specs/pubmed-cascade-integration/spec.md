## ADDED Requirements

### Requirement: PubMed adapter extends BaseScientometricAdapter
The existing `PubMedAdapter` SHALL be modified to extend `BaseScientometricAdapter`, implementing the required `search_by_doi`, `search_by_title`, and `search_by_author` abstract methods.

#### Scenario: ABC compliance
- **WHEN** `PubMedAdapter` is instantiated
- **THEN** it SHALL satisfy the `BaseScientometricAdapter` interface without errors

#### Scenario: search_by_title maps to existing search_bulk
- **WHEN** `search_by_title("BRCA1 mutations in breast cancer", limit=1)` is called
- **THEN** the adapter SHALL use the existing eSearch + eFetch pipeline and return `EnrichedRecord` results

### Requirement: DOI-based search via PubMed
The adapter SHALL support `search_by_doi` by using PubMed's field-qualified search: `{doi}[DOI]`.

#### Scenario: DOI lookup
- **WHEN** `search_by_doi("10.1056/NEJMoa2034577")` is called
- **THEN** the adapter SHALL search PubMed with `10.1056/NEJMoa2034577[DOI]` and return the matching record

#### Scenario: DOI not in PubMed
- **WHEN** a DOI is not indexed in PubMed
- **THEN** the adapter SHALL return `None`

### Requirement: Author-based search
The adapter SHALL support `search_by_author` using PubMed's author field search: `{name}[Author]`.

#### Scenario: Author search
- **WHEN** `search_by_author("Fauci AS", limit=5)` is called
- **THEN** the adapter SHALL return up to 5 `EnrichedRecord` results for that author

### Requirement: MeSH term extraction
The adapter SHALL extract MeSH (Medical Subject Headings) terms from PubMed XML and populate `EnrichedRecord.mesh_terms`.

#### Scenario: Record with MeSH terms
- **WHEN** a PubMed record includes `<MeshHeadingList>` in the XML
- **THEN** `EnrichedRecord.mesh_terms` SHALL contain the descriptor names as a list of strings

### Requirement: Circuit breaker registration
The PubMed adapter SHALL be registered with its own circuit breaker (`_cb_pubmed`) in `enrichment_worker.py` with threshold 3 and recovery 60s.

#### Scenario: PubMed API failure triggers circuit
- **WHEN** PubMed returns 3 consecutive errors (HTTP 500 or timeout)
- **THEN** the circuit breaker SHALL open and skip PubMed for 60 seconds

### Requirement: is_active property
The adapter SHALL expose an `is_active` property that returns `True` always (PubMed is free and always available, unlike BYOK providers).

#### Scenario: Active check
- **WHEN** `adapter_pubmed.is_active` is evaluated
- **THEN** it SHALL return `True`
