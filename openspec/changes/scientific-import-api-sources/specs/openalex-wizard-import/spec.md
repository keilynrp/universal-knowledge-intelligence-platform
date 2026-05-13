## ADDED Requirements

### Requirement: OpenAlex bulk search
The backend SHALL expose a `search_bulk(query, filters, limit)` method on `OpenAlexAdapter` that pages through the OpenAlex `works` endpoint using cursor-based pagination (`cursor=*`) and returns a list of `EnrichedRecord` objects up to the specified limit (max 1,000).

#### Scenario: Keyword query returns records
- **WHEN** `search_bulk` is called with a keyword query and limit ≤ 1,000
- **THEN** the adapter fetches pages from `https://api.openalex.org/works?search=<query>&cursor=*` following `meta.next_cursor` until the limit is reached or results are exhausted
- **THEN** each result is mapped to an `EnrichedRecord` with title, authors, year, DOI, abstract, citation_count, concepts, and affiliations

#### Scenario: Polite pool usage
- **WHEN** `search_bulk` is called
- **THEN** the HTTP request includes `mailto=` in the User-Agent header string
- **THEN** a 0.2-second delay is applied between successive page requests

#### Scenario: Limit enforcement
- **WHEN** `search_bulk` is called with limit > 1,000
- **THEN** the adapter caps the collection at 1,000 records and stops pagination

#### Scenario: Empty results
- **WHEN** the OpenAlex query returns zero results
- **THEN** `search_bulk` returns an empty list without raising an exception

### Requirement: POST /import/openalex endpoint
The backend SHALL expose `POST /import/openalex` that accepts a query payload, calls `OpenAlexAdapter.search_bulk()`, persists the results as `RawEntity` rows via `_ingest_records()`, and returns a job ID for async status polling.

#### Scenario: Successful import request
- **WHEN** an authenticated editor+ user sends `POST /import/openalex` with `{"query": "knowledge management", "limit": 500, "filters": {}}`
- **THEN** the endpoint returns HTTP 202 with `{"job_id": "<uuid>", "status": "queued", "record_count": 500}`
- **THEN** RawEntity rows are created with `enrichment_status="pending"` and `source="openalex"`

#### Scenario: Import with author filter
- **WHEN** the payload includes `{"filters": {"author": "Jane Doe"}}`
- **THEN** the adapter appends `filter=author.display_name.search:<value>` to the OpenAlex query

#### Scenario: Import with ISSN filter
- **WHEN** the payload includes `{"filters": {"issn": "1234-5678"}}`
- **THEN** the adapter appends `filter=primary_location.source.issn:<value>` to the OpenAlex query

#### Scenario: Unauthenticated request rejected
- **WHEN** the request is sent without a valid JWT
- **THEN** the endpoint returns HTTP 401

### Requirement: Shared _ingest_records helper
The backend SHALL provide an `_ingest_records(db, records, domain, source)` helper used by both `/import/openalex` and `/import/pubmed` that creates `RawEntity` rows from `EnrichedRecord` objects, setting `enrichment_status="pending"` so the background worker processes them.

#### Scenario: Records persisted correctly
- **WHEN** `_ingest_records` is called with a list of `EnrichedRecord` objects
- **THEN** one `RawEntity` row is created per record with `primary_label=title`, `domain=domain`, `source=source`, `enrichment_status="pending"`

#### Scenario: Duplicate DOI skipped
- **WHEN** a record with an already-existing DOI is encountered (same org scope)
- **THEN** the duplicate is skipped and not inserted; the returned count reflects only new rows
