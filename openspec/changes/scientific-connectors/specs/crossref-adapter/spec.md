## ADDED Requirements

### Requirement: Crossref adapter implements BaseScientometricAdapter
The system SHALL provide a `CrossrefAdapter` class in `backend/adapters/enrichment/crossref.py` that extends `BaseScientometricAdapter` and communicates with the Crossref REST API (`https://api.crossref.org/works`).

#### Scenario: Adapter instantiation
- **WHEN** `CrossrefAdapter` is instantiated
- **THEN** it SHALL configure a polite-pool `mailto` parameter using the app's contact email and use `httpx.Client` with a 15-second timeout

### Requirement: DOI-first search strategy
The system SHALL attempt DOI-based lookup (`/works/{doi}`) first when the entity has a DOI. If no DOI is available, the system SHALL fall back to bibliographic title search (`/works?query.bibliographic={title}`).

#### Scenario: Search by DOI
- **WHEN** `search_by_doi("10.1038/s41586-023-06600-9")` is called
- **THEN** the adapter SHALL request `https://api.crossref.org/works/10.1038/s41586-023-06600-9` and return an `EnrichedRecord` with title, authors, citation count, DOI, publisher, and publication year

#### Scenario: Search by title
- **WHEN** `search_by_title("Attention is all you need", limit=1)` is called
- **THEN** the adapter SHALL request `/works?query.bibliographic=Attention+is+all+you+need&rows=1` and return matching `EnrichedRecord` results

#### Scenario: No match found
- **WHEN** a search returns zero results
- **THEN** the adapter SHALL return an empty list (for title search) or `None` (for DOI search)

### Requirement: Extract Crossref-specific metadata
The adapter SHALL extract and map Crossref-specific fields to `EnrichedRecord`: `funding` (funder names from `funder` array), `references_count` (from `references-count`), `license` (from `license[0].URL`), and `is_open_access` (from `is-referenced-by-count` > 0 AND license present).

#### Scenario: Record with funding data
- **WHEN** a Crossref response includes a `funder` array with entries
- **THEN** the `EnrichedRecord.funding` field SHALL contain funder names as a list of strings

#### Scenario: Record with license
- **WHEN** a Crossref response includes a `license` array
- **THEN** the `EnrichedRecord.license` field SHALL contain the URL of the first license entry

### Requirement: Polite pool rate limiting
The adapter SHALL include a `mailto` parameter in all requests to access Crossref's polite pool. The adapter SHALL respect a minimum delay of 100ms between consecutive requests.

#### Scenario: Polite pool header
- **WHEN** any request is made to Crossref
- **THEN** the request SHALL include `mailto=research@ukip.dev` (or configured email) as a query parameter

### Requirement: Error handling
The adapter SHALL handle HTTP 404 (not found), 429 (rate limited), and 5xx (server error) gracefully. HTTP 429 SHALL raise an exception that triggers the circuit breaker.

#### Scenario: Rate limited response
- **WHEN** Crossref returns HTTP 429
- **THEN** the adapter SHALL raise an exception causing the circuit breaker to record a failure

#### Scenario: Server error
- **WHEN** Crossref returns HTTP 500/503
- **THEN** the adapter SHALL raise an exception causing the circuit breaker to record a failure
