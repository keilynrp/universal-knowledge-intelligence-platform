## ADDED Requirements

### Requirement: PubMedAdapter using NCBI E-utilities
The backend SHALL provide a `PubMedAdapter` in `backend/adapters/enrichment/pubmed.py` that queries PubMed via the NCBI E-utilities API (eSearch + eFetch) using plain `requests` and `xml.etree.ElementTree`. No third-party library (Biopython, pymed) SHALL be used.

#### Scenario: eSearch then eFetch flow
- **WHEN** `search_bulk(query, limit)` is called
- **THEN** the adapter first calls `eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=<query>&retmax=<limit>` to retrieve PMIDs
- **THEN** it calls `eFetch` with the retrieved PMIDs in batches of 100 to fetch MEDLINE XML
- **THEN** it parses the XML and returns a list of `EnrichedRecord` objects

#### Scenario: Field extraction from MEDLINE XML
- **WHEN** eFetch returns MEDLINE XML for a record
- **THEN** the adapter extracts: ArticleTitle, AuthorList (LastName + ForeName), PubDate Year, AbstractText, DOI (from ArticleIdList type="doi"), and Affiliation
- **THEN** malformed or missing fields are skipped gracefully (no exception raised)

#### Scenario: Rate limit compliance
- **WHEN** making successive requests
- **THEN** a delay of 1/3 second is applied between requests (≤3 req/s without API key)
- **WHEN** `NCBI_API_KEY` env var is set
- **THEN** the key is added as `api_key=` param and the delay is reduced to 1/10 second (≤10 req/s)

#### Scenario: Limit enforcement
- **WHEN** `search_bulk` is called with limit > 500
- **THEN** the adapter caps the collection at 500 records

#### Scenario: Empty results
- **WHEN** the eSearch returns zero PMIDs
- **THEN** `search_bulk` returns an empty list without raising an exception

### Requirement: POST /import/pubmed endpoint
The backend SHALL expose `POST /import/pubmed` that accepts a PubMed query payload, calls `PubMedAdapter.search_bulk()`, persists results via `_ingest_records()`, and returns a job ID.

#### Scenario: Successful import request
- **WHEN** an authenticated editor+ user sends `POST /import/pubmed` with `{"query": "knowledge management systematic review", "limit": 200}`
- **THEN** the endpoint returns HTTP 202 with `{"job_id": "<uuid>", "status": "queued", "record_count": <n>}`
- **THEN** RawEntity rows are created with `enrichment_status="pending"` and `source="pubmed"`

#### Scenario: Unauthenticated request rejected
- **WHEN** the request is sent without a valid JWT
- **THEN** the endpoint returns HTTP 401

#### Scenario: Invalid limit rejected
- **WHEN** the payload includes `limit` > 500
- **THEN** the endpoint returns HTTP 422 with a validation error

### Requirement: Async job status polling
The backend SHALL expose `GET /import/status/{job_id}` so the frontend can poll the status of an import job and display a progress bar.

#### Scenario: Job in progress
- **WHEN** `GET /import/status/{job_id}` is called while import is running
- **THEN** the endpoint returns `{"job_id": "<id>", "status": "running", "progress": 0.6, "records_inserted": 120, "total": 200}`

#### Scenario: Job completed
- **WHEN** `GET /import/status/{job_id}` is called after import finishes
- **THEN** the endpoint returns `{"job_id": "<id>", "status": "done", "progress": 1.0, "records_inserted": 200, "total": 200}`

#### Scenario: Unknown job ID
- **WHEN** `GET /import/status/{job_id}` is called with a non-existent job ID
- **THEN** the endpoint returns HTTP 404
