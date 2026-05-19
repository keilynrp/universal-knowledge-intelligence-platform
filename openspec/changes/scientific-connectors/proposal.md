## Why

UKIP's enrichment pipeline currently relies on a narrow provider cascade: Scopus and WoS (BYOK, rarely configured), OpenAlex (primary workhorse), and Google Scholar (scraping fallback). When OpenAlex returns no match, entities fail with `no_provider_match` — the most common enrichment failure code. Adding more free, high-quality scientific data sources would dramatically reduce this failure rate and enrich entities with complementary metadata (funding, influential citations, TLDRs, MeSH terms) that no single provider covers alone.

A PubMed adapter already exists (`pubmed.py`) but is not wired into the cascade. Three additional free APIs — Crossref, Semantic Scholar, and DBLP — cover complementary niches and would strengthen the pipeline with minimal cost.

**Provider evaluation (included/excluded):**

| Provider | Verdict | Rationale |
|----------|---------|-----------|
| PubMed (NCBI) | **Include** — already coded, just needs cascade wiring | 36M+ biomedical records, free, PMIDs, MeSH terms |
| Crossref | **Include** — new adapter | 150M+ DOIs, funding metadata, references, license info, free polite pool |
| Semantic Scholar | **Include** — new adapter | 200M+ papers, influential citation counts, TLDRs, embeddings, free API key |
| DBLP | **Include** — new adapter | Exhaustive CS/IT conference+journal coverage, free, no auth required |
| OCLC/WorldCat | **Exclude v1** — requires paid OCLC Cataloging + FirstSearch subscription; free Entities API is too limited (no full bibliographic search) |
| Kaggle | **Exclude** — dataset repository, not bibliometric; API is for dataset management, doesn't map to `EnrichedRecord` |

## What Changes

- **Wire PubMed** into the enrichment cascade with its own circuit breaker (adapter already exists, needs `BaseScientometricAdapter` compliance + cascade position)
- **New Crossref adapter** (`crossref.py`): search by DOI and title via Crossref REST API; extracts funding, license, reference count, ISSN
- **New Semantic Scholar adapter** (`semantic_scholar.py`): search by title/DOI via S2 API; extracts influential citation count, TLDR, paper embeddings, venue
- **New DBLP adapter** (`dblp.py`): search by title via DBLP API; extracts conference/journal venue, BibTeX key, author pages
- **Extend `EnrichedRecord`** NDO with optional fields: `funding`, `references_count`, `tldr`, `influential_citation_count`, `license`, `mesh_terms`
- **Configurable cascade order** via env var `ENRICHMENT_CASCADE` (comma-separated provider names, default: `scopus,wos,openalex,crossref,pubmed,semantic_scholar,dblp,scholar`)
- **Provider health dashboard endpoint** exposing circuit breaker states and success rates per provider

## Capabilities

### New Capabilities
- `crossref-adapter`: Crossref REST API adapter implementing `BaseScientometricAdapter` with DOI-first search, funding extraction, and polite-pool rate limiting
- `semantic-scholar-adapter`: Semantic Scholar Academic Graph API adapter with title/DOI search, influential citations, TLDRs, and API key support
- `dblp-adapter`: DBLP API adapter for CS-domain publications with venue extraction and BibTeX metadata
- `pubmed-cascade-integration`: Wire existing PubMed adapter into enrichment cascade with `BaseScientometricAdapter` compliance and circuit breaker
- `enrichment-cascade-config`: Configurable provider cascade order via environment variable with provider health monitoring endpoint

### Modified Capabilities
_(none — existing adapter interfaces and cascade logic are extended, not changed)_

## Impact

- **Backend adapters**: 3 new files in `backend/adapters/enrichment/` (crossref, semantic_scholar, dblp); 1 modified (pubmed — add ABC compliance)
- **Schemas**: `EnrichedRecord` extended with optional fields (backward-compatible)
- **Enrichment worker**: Cascade logic updated to support configurable order and 4 new provider slots
- **Circuit breakers**: 4 new instances (pubmed, crossref, semantic_scholar, dblp)
- **Dependencies**: No new Python packages — all adapters use `httpx` (already installed) for HTTP calls
- **Env vars**: `ENRICHMENT_CASCADE` (optional), `NCBI_API_KEY` (optional, existing), `S2_API_KEY` (optional), `DBLP_MIRROR` (optional)
- **API**: New `GET /enrichment/providers` endpoint for provider health status
