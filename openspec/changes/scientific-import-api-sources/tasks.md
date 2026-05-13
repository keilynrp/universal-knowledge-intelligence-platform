## 1. Backend — OpenAlex Adapter Extension

- [x] 1.1 Add `search_bulk(query, filters, limit)` method to `backend/adapters/enrichment/openalex.py` with cursor pagination, polite-pool User-Agent (`mailto=`), 0.2s inter-page delay, and 1,000-record cap
- [x] 1.2 Map OpenAlex `works` response fields (title, authors, year, DOI, abstract, citation_count, concepts, affiliations) to `EnrichedRecord`
- [x] 1.3 Support filter params: `author` → `filter=author.display_name.search:<v>`, `issn` → `filter=primary_location.source.issn:<v>`
- [x] 1.4 Write unit tests for `search_bulk` (mock HTTP, cursor pagination, empty results, limit cap)

## 2. Backend — PubMed Adapter

- [x] 2.1 Create `backend/adapters/enrichment/pubmed.py` with `PubMedAdapter` class
- [x] 2.2 Implement `search_bulk(query, limit)`: eSearch (get PMIDs) → eFetch in batches of 100 (MEDLINE XML) → parse with `xml.etree.ElementTree`
- [x] 2.3 Extract fields: ArticleTitle, AuthorList, PubDate Year, AbstractText, DOI, Affiliation; skip malformed records gracefully
- [x] 2.4 Apply rate-limit delays: 1/3s default; 1/10s when `NCBI_API_KEY` env var is set; cap at 500 records
- [x] 2.5 Write unit tests for `PubMedAdapter` (mock eSearch + eFetch XML responses, missing fields, rate-limit logic)

## 3. Backend — Import Endpoints and Job Tracking

- [x] 3.1 Add `_ingest_records(db, records, domain, source)` helper to `backend/routers/ingest.py` (or a new `backend/routers/api_import.py`) that creates `RawEntity` rows with `enrichment_status="pending"`; skip duplicate DOIs within the same org scope
- [x] 3.2 Add in-memory job store (dict keyed by UUID) to track import job progress (status, progress float, records_inserted, total)
- [x] 3.3 Implement `POST /import/openalex` (editor+): validate payload, enqueue async task that calls `search_bulk` + `_ingest_records`, return 202 with job ID
- [x] 3.4 Implement `POST /import/pubmed` (editor+): same pattern as above using `PubMedAdapter`; validate limit ≤ 500
- [x] 3.5 Implement `GET /import/status/{job_id}`: return current job state from in-memory store; 404 on unknown ID
- [x] 3.6 Register new router in `backend/main.py`
- [x] 3.7 Write integration tests for `/import/openalex`, `/import/pubmed`, `/import/status/{job_id}` (mock adapters, auth checks, 422 on bad limit)

## 4. Backend — Demo Seed Update

- [x] 4.1 Update `backend/routers/demo.py` `POST /demo/seed`: attempt live OpenAlex query (concept C41008148, limit 1,000) via `OpenAlexAdapter.search_bulk()`; on any exception fall back to `data/demo/openalex_snapshot.json`
- [x] 4.2 Clear existing `source="demo"` entities before re-seeding (idempotent)
- [x] 4.3 Return `{"seeded": <n>, "source": "openalex_live" | "openalex_snapshot"}` from seed endpoint
- [x] 4.4 Create `scripts/generate_openalex_snapshot.py` that fetches concept C41008148 records and writes `data/demo/openalex_snapshot.json`
- [x] 4.5 Generate and commit `data/demo/openalex_snapshot.json` (≥100 records) using the script
- [x] 4.6 Update demo seed tests in `tests/test_sprint41.py` (or new `test_demo_seed.py`) to work with real-data fixture and the bundled fallback

## 5. Frontend — Scientific Import Wizard Tabs

- [x] 5.1 Add "OpenAlex" and "PubMed" tabs to `frontend/app/import/scientific/page.tsx` alongside existing "File Upload" tab; "File Upload" stays at tab index 0 and is unchanged
- [x] 5.2 Build OpenAlex query builder form: keyword input, optional author + ISSN filters, limit slider (10–1,000 default 100), "Search Preview" button
- [x] 5.3 Build PubMed query builder form: search query input, limit slider (10–500 default 100), "Search Preview" button
- [x] 5.4 Implement search-preview-import flow for both tabs: preview (call endpoint with limit=10), show first 10 results table, confirm button triggers full import
- [x] 5.5 Implement progress bar component that polls `GET /import/status/{job_id}` every 2 seconds and updates based on `progress` field; stops on `status="done"` or error
- [x] 5.6 Show success banner ("Imported N records") on completion; show inline error banner on failure with retry option
- [x] 5.7 Add i18n keys for all new UI strings in `frontend/app/i18n/translations.ts` (EN + ES)
