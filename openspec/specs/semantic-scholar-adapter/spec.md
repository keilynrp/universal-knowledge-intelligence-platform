# semantic-scholar-adapter Specification

## Purpose
TBD - created by archiving change scientific-connectors. Update Purpose after archive.
## Requirements
### Requirement: Semantic Scholar adapter implements BaseScientometricAdapter
The system SHALL provide a `SemanticScholarAdapter` class in `backend/adapters/enrichment/semantic_scholar.py` that extends `BaseScientometricAdapter` and communicates with the Semantic Scholar Academic Graph API (`https://api.semanticscholar.org/graph/v1`).

#### Scenario: Adapter instantiation with API key
- **WHEN** `SemanticScholarAdapter` is instantiated and `S2_API_KEY` env var is set
- **THEN** it SHALL include the API key in the `x-api-key` header for all requests

#### Scenario: Adapter instantiation without API key
- **WHEN** `SemanticScholarAdapter` is instantiated without `S2_API_KEY`
- **THEN** it SHALL operate in unauthenticated mode (lower rate limits)

### Requirement: Title and DOI search
The adapter SHALL support searching by title via `/paper/search?query={title}&fields=...&limit=1` and by DOI via `/paper/DOI:{doi}?fields=...`.

#### Scenario: Search by title
- **WHEN** `search_by_title("BERT: Pre-training of Deep Bidirectional Transformers", limit=1)` is called
- **THEN** the adapter SHALL return an `EnrichedRecord` with title, authors, citation count, year, venue, and DOI

#### Scenario: Search by DOI
- **WHEN** `search_by_doi("10.18653/v1/N19-1423")` is called
- **THEN** the adapter SHALL return an `EnrichedRecord` for the matching paper

#### Scenario: No match
- **WHEN** a search returns no results
- **THEN** the adapter SHALL return an empty list or `None`

### Requirement: Extract Semantic Scholar-specific metadata
The adapter SHALL extract unique S2 fields: `influential_citation_count` (from `influentialCitationCount`), `tldr` (from `tldr.text`), `venue` (from `venue`), and `is_open_access` (from `isOpenAccess`).

#### Scenario: Paper with TLDR
- **WHEN** a paper has a TLDR summary available
- **THEN** the `EnrichedRecord.tldr` field SHALL contain the TLDR text string

#### Scenario: Paper with influential citations
- **WHEN** a paper has `influentialCitationCount > 0`
- **THEN** the `EnrichedRecord.influential_citation_count` SHALL contain that value

### Requirement: Request fields parameter
All API requests SHALL specify the `fields` parameter to request only needed fields: `paperId,title,authors,year,citationCount,influentialCitationCount,tldr,venue,isOpenAccess,externalIds`.

#### Scenario: Efficient field selection
- **WHEN** any paper request is made
- **THEN** the request SHALL include a `fields` parameter limiting response to required fields only

### Requirement: Rate limit handling with exponential backoff
The adapter SHALL handle HTTP 429 responses by raising an exception for the circuit breaker. The adapter SHALL include a 200ms minimum delay between requests.

#### Scenario: Rate limited
- **WHEN** the API returns HTTP 429
- **THEN** the adapter SHALL raise an exception triggering circuit breaker failure recording

#### Scenario: Timeout
- **WHEN** a request exceeds 10 seconds
- **THEN** the adapter SHALL raise a timeout exception triggering circuit breaker failure
