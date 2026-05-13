## Why

The Scientific Import wizard currently only accepts file uploads (CSV, Excel, BibTeX, RIS), requiring users to manually export data from external databases before importing. Bibliometrix/Biblioshiny — the dominant tools in this space — connect directly to OpenAlex and PubMed via API, making dataset assembly a one-click operation. UKIP needs the same capability to compete and to seed its demo mode with real, coherent bibliometric data instead of synthetic Faker records that make analytics look meaningless.

## What Changes

- Add an **OpenAlex API import** tab to the Scientific Import wizard — users enter a keyword query, author name, institution, or ISSN and UKIP fetches up to 1,000 records directly from the OpenAlex REST API (no key required)
- Add a **PubMed/NCBI import** tab to the Scientific Import wizard — users enter a PubMed search query and UKIP fetches records via the NCBI E-utilities API (free, no key required for reasonable volumes)
- Replace the **Demo Mode seed** dataset from Faker-generated synthetic data to a real OpenAlex query (`concept: "knowledge management"`, limit 1,000) — affiliations, DOIs, citations, and concepts are real, making all bibliometric analyses immediately meaningful
- Add a `backend/adapters/enrichment/pubmed.py` adapter using NCBI E-utilities (eFetch/eSearch)
- Extend the existing `OpenAlexAdapter` with a `search_bulk()` method for multi-page collection

## Capabilities

### New Capabilities

- `openalex-wizard-import`: Interactive wizard step to query OpenAlex by keyword/author/institution/ISSN and import results as RawEntities
- `pubmed-wizard-import`: Interactive wizard step to query PubMed via NCBI E-utilities and import results as RawEntities
- `real-demo-seed`: Demo mode seeds from a live OpenAlex query instead of Faker-generated data, with a bundled fallback JSON for offline/CI environments

### Modified Capabilities

- `scientific-import-wizard`: Add two new import mode tabs (OpenAlex, PubMed) alongside the existing file upload tab

## Impact

- **Backend**: new `POST /import/openalex` and `POST /import/pubmed` endpoints; new `PubMedAdapter`; extended `OpenAlexAdapter`; updated `demo.py` router seed logic
- **Frontend**: `frontend/app/import/scientific/page.tsx` — new tab UI with query builder forms
- **Demo**: `data/demo/demo_entities.xlsx` replaced or supplemented by real OpenAlex snapshot; `scripts/generate_demo_dataset.py` updated; fallback JSON bundled for CI
- **Dependencies**: no new required packages (OpenAlex and NCBI E-utilities use plain HTTP); `requests` already added
- **CI**: demo seed tests updated to work with real-data fixture or bundled fallback
