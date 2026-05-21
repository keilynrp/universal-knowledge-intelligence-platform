# dblp-adapter Specification

## Purpose
TBD - created by archiving change scientific-connectors. Update Purpose after archive.
## Requirements
### Requirement: DBLP adapter implements BaseScientometricAdapter
The system SHALL provide a `DBLPAdapter` class in `backend/adapters/enrichment/dblp.py` that extends `BaseScientometricAdapter` and communicates with the DBLP search API (`https://dblp.org/search/publ/api`).

#### Scenario: Adapter instantiation
- **WHEN** `DBLPAdapter` is instantiated
- **THEN** it SHALL configure an `httpx.Client` with a 10-second timeout and no authentication headers (DBLP requires no auth)

### Requirement: Title-based publication search
The adapter SHALL search DBLP by title using the publication search API with JSON format.

#### Scenario: Search by title
- **WHEN** `search_by_title("MapReduce: Simplified Data Processing on Large Clusters", limit=1)` is called
- **THEN** the adapter SHALL request `https://dblp.org/search/publ/api?q=MapReduce+Simplified+Data+Processing&format=json&h=1` and return an `EnrichedRecord`

#### Scenario: No match
- **WHEN** a title search returns zero hits
- **THEN** the adapter SHALL return an empty list

### Requirement: DOI-based lookup
The adapter SHALL support DOI lookup by searching DBLP with the DOI as query term (DBLP indexes DOIs in its search).

#### Scenario: Search by DOI
- **WHEN** `search_by_doi("10.1145/1327452.1327492")` is called
- **THEN** the adapter SHALL search DBLP with the DOI and return the matching record if found

### Requirement: Extract DBLP-specific metadata
The adapter SHALL extract: title, authors (from `authors.author` array), publication year, venue (from `venue` field), DOI (from `ee` field when it contains doi.org), and publisher.

#### Scenario: Conference paper
- **WHEN** a DBLP result is a conference paper
- **THEN** the `EnrichedRecord.venue` SHALL contain the conference name and `publisher` SHALL contain the proceedings publisher

#### Scenario: Journal article
- **WHEN** a DBLP result is a journal article
- **THEN** the `EnrichedRecord.venue` SHALL contain the journal name

### Requirement: Polite rate limiting
The adapter SHALL enforce a minimum 1-second delay between consecutive requests to respect DBLP's fair-use policy.

#### Scenario: Consecutive requests
- **WHEN** multiple searches are performed in sequence
- **THEN** each request SHALL wait at least 1 second after the previous one

### Requirement: Author search
The adapter SHALL support searching by author name via DBLP's author search API.

#### Scenario: Search by author
- **WHEN** `search_by_author("Jeffrey Dean", limit=5)` is called
- **THEN** the adapter SHALL search DBLP's publication API filtered by author and return matching `EnrichedRecord` results
