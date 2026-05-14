## ADDED Requirements

### Requirement: Scientific API connector pipeline
The engine SHALL provide a `scientific_connectors` pipeline that fetches, parses, and normalizes publication data from external scientific APIs.

#### Scenario: Fetch from OpenAlex
- **WHEN** the pipeline receives a connector request with source="openalex" and query parameters (DOI, title, author)
- **THEN** it SHALL call the OpenAlex API, parse the JSON response, and return normalized Publication proto messages

#### Scenario: Fetch from Crossref
- **WHEN** the pipeline receives source="crossref" with a DOI
- **THEN** it SHALL call the Crossref API and return normalized publication data including title, authors, journal, year, and DOI

#### Scenario: Fetch from PubMed
- **WHEN** the pipeline receives source="pubmed" with a PMID or search query
- **THEN** it SHALL call the PubMed E-utilities API and return normalized publication data

### Requirement: Connector rate limiting
Each connector SHALL implement per-source rate limiting to respect API terms of service.

#### Scenario: OpenAlex rate limit
- **WHEN** requests exceed the OpenAlex polite pool rate (10 req/s with mailto)
- **THEN** the connector SHALL queue requests and throttle to stay within limits

#### Scenario: Rate limit across concurrent jobs
- **WHEN** multiple pipeline jobs use the same connector concurrently
- **THEN** the rate limiter SHALL be shared across jobs (process-level, not per-job)

### Requirement: Connector retry and error handling
Connectors SHALL retry transient failures with exponential backoff.

#### Scenario: Transient HTTP error
- **WHEN** an API returns HTTP 429 or 503
- **THEN** the connector SHALL retry up to 3 times with exponential backoff (1s, 2s, 4s)

#### Scenario: Permanent error
- **WHEN** an API returns HTTP 404 or 400
- **THEN** the connector SHALL skip that record and log a warning, not retry

### Requirement: Bulk fetch mode
The connector pipeline SHALL support batch requests for multiple records in a single pipeline invocation.

#### Scenario: Batch DOI resolution
- **WHEN** the pipeline receives a list of 100 DOIs with source="crossref"
- **THEN** it SHALL fetch all 100 records (respecting rate limits) and return results as a batch, reporting per-record success/failure in the output

### Requirement: Connector API key handling
API keys for external services SHALL be passed via the `options` map in `ProcessRequest`, never stored in engine configuration.

#### Scenario: API key provided
- **WHEN** `options` contains `api_key` for a connector
- **THEN** the connector SHALL use it for authenticated requests

#### Scenario: No API key provided
- **WHEN** no `api_key` is in `options` and the API supports unauthenticated access
- **THEN** the connector SHALL proceed with unauthenticated requests (possibly at reduced rate limits)
