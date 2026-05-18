## Context

UKIP's Scientific Import wizard (`frontend/app/import/scientific/page.tsx`) currently handles only file uploads. The backend ingestion pipeline (`POST /upload`) parses CSV/Excel/BibTeX/RIS files and creates `RawEntity` records. The existing `OpenAlexAdapter` (`backend/adapters/enrichment/openalex.py`) already wraps the OpenAlex API for single-record enrichment but has no bulk collection capability. The demo seed (`backend/routers/demo.py`) reads `data/demo/demo_entities.xlsx` generated offline with Faker.

Bibliometrix/Biblioshiny connect directly to OpenAlex and PubMed without user-side exports. This design adds the same capability to UKIP with minimal new infrastructure.

## Goals / Non-Goals

**Goals:**
- Bulk import from OpenAlex via keyword/author/institution/ISSN query (up to 1,000 records, multi-page)
- Bulk import from PubMed via NCBI E-utilities (eSearch + eFetch), up to 500 records per run
- Demo mode seeds from a real OpenAlex query with a bundled JSON fallback for offline/CI
- Wizard UX that mirrors the Bibliometrix "search → preview → import" flow
- All imports flow through the existing `RawEntity` pipeline (no new DB schema)

**Non-Goals:**
- Web of Science or Scopus API import (require institutional keys — separate change)
- Full-text download or PDF parsing
- Pagination UI beyond the first 1,000 results in this iteration
- Authentication/API key management for OpenAlex (it's free tier, no key needed at this scale)

## Decisions

### D1: OpenAlex bulk via `search_bulk()` on existing adapter

**Decision**: Extend `OpenAlexAdapter` with a `search_bulk(query, filters, limit)` method that pages through `works` endpoint using `cursor=*` pagination. Returns a list of `EnrichedRecord`.

**Alternatives considered**:
- New standalone adapter class → unnecessary duplication; the existing adapter already handles HTTP + rate limits
- Raw HTTP in the endpoint → no reuse, harder to test

### D2: PubMed via NCBI E-utilities (no new library)

**Decision**: New `PubMedAdapter` in `backend/adapters/enrichment/pubmed.py` using plain `requests` against `eutils.ncbi.nlm.nih.gov`. Flow: `eSearch` (get PMIDs) → `eFetch` (get MEDLINE XML) → parse with `xml.etree.ElementTree`. No third-party library.

**Alternatives considered**:
- `Biopython.Entrez` → adds a heavy dep; E-utilities are simple enough to call directly
- `pymed` library → unmaintained, would repeat the scholarly problem

### D3: Two new POST endpoints, shared ingestion helper

**Decision**: Add `POST /import/openalex` and `POST /import/pubmed`. Both call a shared `_ingest_records(db, records, domain, source)` helper that creates `RawEntity` rows (marking `enrichment_status="pending"` so the background worker picks them up). The existing `POST /upload` logic is factored into the same helper.

**Alternatives considered**:
- Reuse `POST /upload` with a special mode flag → breaks single-responsibility; upload is file-based
- Separate ingestion per endpoint → code duplication, drift risk

### D4: Demo seed — live query + bundled fallback JSON

**Decision**: `POST /demo/seed` first tries a live OpenAlex query (`concept.id: C41008148`, limit 1,000). On failure (offline, rate limit) it falls back to `data/demo/openalex_snapshot.json` committed to the repo. The snapshot is generated once via `scripts/generate_openalex_snapshot.py` and committed.

**Alternatives considered**:
- Always live query → CI fails without network; demo unreliable
- Always use bundled file → loses the "real data on fresh install" benefit for connected environments
- Keep Faker data → analytics look fake, concept/author/geography distributions are random

### D5: Frontend — tab-based wizard extension

**Decision**: Add two new tabs to the scientific import wizard: "OpenAlex" and "PubMed". Each tab has a query builder form (keyword, filters, limit slider) → preview of first 10 results → confirm import. Existing "File Upload" tab is tab index 0, unchanged.

**Alternatives considered**:
- Separate pages per source → breaks the unified wizard UX
- Modal overlay → harder to show preview inline

## Risks / Trade-offs

- **OpenAlex rate limits** → Mitigation: Use `mailto=` param in User-Agent header (polite pool, higher limits); add 0.2s delay between pages; cap at 1,000 records per request
- **PubMed NCBI rate limits** (3 req/s without key, 10/s with key) → Mitigation: Add NCBI_API_KEY env var support; default to 3/s; cap at 500 records
- **Large imports slow the UI** → Mitigation: Import runs async (returns job ID immediately), frontend polls `GET /import/status/{job_id}`; show progress bar
- **Demo snapshot staleness** → Mitigation: snapshot is regenerated manually when needed; it's committed like any other fixture
- **XML parsing complexity (PubMed MEDLINE)** → Mitigation: Extract only the fields UKIP uses (title, authors, year, abstract, DOI, citations, affiliation); skip malformed records

## Open Questions

- Should we add `NCBI_API_KEY` env var support in the initial implementation or defer to V2?
- Max limit for OpenAlex import: 1,000 records per request or configurable? (suggest hardcoding 1,000 for V1)
- Should the import job status be persisted to DB (`import_batches` table exists) or only in-memory for now?
