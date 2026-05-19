## 1. EnrichedRecord Extension

- [x] 1.1 Add optional fields to `EnrichedRecord` in `schemas_enrichment.py`: `funding`, `references_count`, `tldr`, `influential_citation_count`, `license`, `mesh_terms`, `venue` (all `Optional`, default `None`)
- [x] 1.2 Write test: existing adapters (OpenAlex, Scopus, WoS) still produce valid `EnrichedRecord` without setting new fields

## 2. PubMed Cascade Integration

- [x] 2.1 Make `PubMedAdapter` extend `BaseScientometricAdapter` — add `search_by_doi` (DOI field query), `search_by_title` (wraps `search_bulk`), `search_by_author` (author field query)
- [x] 2.2 Extract MeSH terms from PubMed XML in `_parse_article` and populate `EnrichedRecord.mesh_terms`
- [x] 2.3 Add `is_active` property returning `True`
- [x] 2.4 Register `adapter_pubmed` and `_cb_pubmed` circuit breaker in `enrichment_worker.py`
- [x] 2.5 Write tests: ABC compliance, search_by_doi, search_by_title, MeSH extraction, is_active

## 3. Crossref Adapter

- [x] 3.1 Create `backend/adapters/enrichment/crossref.py` with `CrossrefAdapter` extending `BaseScientometricAdapter`
- [x] 3.2 Implement `search_by_doi` using `/works/{doi}` endpoint with polite `mailto` param
- [x] 3.3 Implement `search_by_title` using `/works?query.bibliographic={title}&rows={limit}` endpoint
- [x] 3.4 Implement `search_by_author` using `/works?query.author={name}` endpoint
- [x] 3.5 Implement `_parse_record` mapping Crossref JSON to `EnrichedRecord` including `funding`, `references_count`, `license`, `is_open_access`
- [x] 3.6 Add polite pool delay (100ms between requests) and error handling (404→None, 429/5xx→raise for circuit breaker)
- [x] 3.7 Register `adapter_crossref` and `_cb_crossref` in `enrichment_worker.py`
- [x] 3.8 Write tests: DOI lookup, title search, funding extraction, license extraction, error handling, empty results

## 4. Semantic Scholar Adapter

- [x] 4.1 Create `backend/adapters/enrichment/semantic_scholar.py` with `SemanticScholarAdapter` extending `BaseScientometricAdapter`
- [x] 4.2 Implement `search_by_doi` using `/paper/DOI:{doi}?fields=...` endpoint
- [x] 4.3 Implement `search_by_title` using `/paper/search?query={title}&fields=...&limit={limit}` endpoint
- [x] 4.4 Implement `search_by_author` using `/paper/search?query={name}&fields=...` endpoint
- [x] 4.5 Implement `_parse_record` mapping S2 JSON to `EnrichedRecord` including `tldr`, `influential_citation_count`, `venue`, `is_open_access`
- [x] 4.6 Support optional `S2_API_KEY` env var in `x-api-key` header; add 200ms delay between requests
- [x] 4.7 Register `adapter_s2` and `_cb_s2` in `enrichment_worker.py`
- [x] 4.8 Write tests: title search, DOI lookup, TLDR extraction, influential citations, API key header, error handling

## 5. DBLP Adapter

- [x] 5.1 Create `backend/adapters/enrichment/dblp.py` with `DBLPAdapter` extending `BaseScientometricAdapter`
- [x] 5.2 Implement `search_by_title` using `https://dblp.org/search/publ/api?q={title}&format=json&h={limit}`
- [x] 5.3 Implement `search_by_doi` by searching DBLP with DOI as query term
- [x] 5.4 Implement `search_by_author` using DBLP publication search filtered by author
- [x] 5.5 Implement `_parse_record` mapping DBLP JSON to `EnrichedRecord` including `venue`, DOI extraction from `ee` field
- [x] 5.6 Add 1-second polite delay between requests; error handling for 429/5xx
- [x] 5.7 Register `adapter_dblp` and `_cb_dblp` in `enrichment_worker.py`
- [x] 5.8 Write tests: title search, DOI lookup, venue extraction, author search, empty results, error handling

## 6. Configurable Cascade

- [x] 6.1 Create provider registry dict mapping provider IDs to `(adapter, circuit_breaker)` tuples in `enrichment_worker.py`
- [x] 6.2 Parse `ENRICHMENT_CASCADE` env var at module load; log warnings for unrecognized provider names
- [x] 6.3 Refactor `enrich_single_record` to iterate through the configured provider list from the registry instead of hardcoded if/elif chain
- [x] 6.4 Write tests: custom cascade order, default cascade, invalid provider name warning, cascade short-circuits on first match

## 7. Extended Fields Persistence

- [x] 7.1 Update enrichment worker to persist non-None extended fields (`funding`, `tldr`, `mesh_terms`, `influential_citation_count`, `references_count`, `license`, `venue`) into `attributes_json`
- [x] 7.2 Write test: enriched entity has extended fields in attributes_json when provider supplies them

## 8. Provider Health Endpoint

- [x] 8.1 Add `GET /enrichment/providers` endpoint to `routers/entities.py` returning provider name, is_active, circuit breaker state, success/failure counts
- [x] 8.2 Add circuit breaker introspection: expose `state`, `failure_count`, `success_count`, `last_failure_time` on `CircuitBreaker` class
- [x] 8.3 Write tests: endpoint returns all providers, shows correct circuit states, shows inactive BYOK providers

## 9. Documentation

- [x] 9.1 Update `.env.example` with new env vars: `ENRICHMENT_CASCADE`, `S2_API_KEY`, `NCBI_API_KEY`, `DBLP_MIRROR`
- [x] 9.2 Add provider setup notes to `docs/superpowers/plans/` describing each provider's capabilities and configuration
