## Context

UKIP's enrichment pipeline uses a hardcoded cascade in `enrichment_worker.py`: Scopus → WoS → OpenAlex → Scholar. The adapter pattern (`BaseScientometricAdapter` ABC + `EnrichedRecord` NDO) already abstracts provider differences. Circuit breakers protect each provider independently. PubMed has a full adapter implementation but isn't connected to the cascade.

The current `no_provider_match` failure rate is the most common enrichment failure — adding 4 more free providers (PubMed, Crossref, Semantic Scholar, DBLP) should substantially reduce it.

## Goals / Non-Goals

**Goals:**
- Add 3 new adapters (Crossref, Semantic Scholar, DBLP) following existing patterns
- Wire PubMed into the cascade (adapter exists, needs ABC compliance)
- Make cascade order configurable via env var
- Extend `EnrichedRecord` with optional metadata fields from new providers
- Expose provider health status via API endpoint

**Non-Goals:**
- Changing the enrichment worker's single-record-at-a-time processing model
- Implementing provider-specific bulk/batch endpoints (future optimization)
- Adding OCLC WorldCat (requires paid subscription) or Kaggle (not bibliometric)
- Replacing OpenAlex as primary free provider — it stays first in the free tier
- Provider-level deduplication or cross-provider merging (each entity gets enriched by the first provider that matches)

## Decisions

### D1: Cascade order — BYOK first, then free by coverage breadth

**Decision:** Default cascade: `scopus → wos → openalex → crossref → pubmed → semantic_scholar → dblp → scholar`

**Rationale:**
- BYOK providers (Scopus, WoS) first because the user paid for them and they're highest quality
- OpenAlex first among free providers — broadest coverage (250M+ works), richest metadata
- Crossref second — excellent DOI resolution, funding data, 150M+ records
- PubMed third — 36M biomedical, fills gaps for medical/life sciences
- Semantic Scholar fourth — 200M+ papers but rate-limited, provides unique fields (TLDRs, influential citations)
- DBLP fifth — niche (CS only) but exhaustive for that domain
- Scholar last — scraping fallback, most fragile

**Alternative considered:** Domain-aware ordering (e.g., PubMed first for healthcare domain) — deferred to v2 as premature complexity.

### D2: Configurable cascade via `ENRICHMENT_CASCADE` env var

**Decision:** Optional `ENRICHMENT_CASCADE=openalex,crossref,pubmed` env var. Comma-separated provider IDs. If set, only listed providers are used in that order. If unset, use the full default cascade.

**Rationale:** Allows operators to disable providers they don't want (e.g., remove Scholar) or reorder for their specific corpus. Simple to implement — just filter and sort the provider list at startup.

### D3: PubMed adapter — add ABC compliance, don't rewrite

**Decision:** Add `search_by_doi` and `search_by_author` stubs plus make `PubMedAdapter` extend `BaseScientometricAdapter`. Map `search_bulk` to `search_by_title`. Keep existing XML parsing unchanged.

**Rationale:** The adapter works well — minimal changes to connect it. `search_by_doi` can use PubMed's DOI field search. `search_by_author` can use author name query.

### D4: Crossref adapter — DOI-first strategy

**Decision:** When entity has a DOI, use Crossref's `/works/{doi}` endpoint (exact match, fast). When no DOI, fall back to `/works?query.bibliographic={title}` (fuzzy title search). Include `mailto` parameter for polite pool access.

**Rationale:** Crossref's DOI lookup is authoritative and instant. Title search is slower but useful as fallback. Polite pool gives higher rate limits (no hard cap vs. 50 req/s for anonymous).

### D5: Semantic Scholar adapter — API key optional, title+DOI search

**Decision:** Use S2 Academic Graph API v1. Search via `/paper/search?query={title}` or `/paper/DOI:{doi}` for DOI lookup. Extract `tldr.text`, `influentialCitationCount`, `citationCount`, `venue`, `authors`, `isOpenAccess`. Use `S2_API_KEY` env var if available for higher rate limits.

**Rationale:** S2 provides unique fields (TLDR, influential citations) not available from other providers. Free tier is 5000 req/5min unauthenticated; API key gives 1 req/s sustained.

### D6: DBLP adapter — simple JSON API, no auth

**Decision:** Use DBLP's search API: `https://dblp.org/search/publ/api?q={title}&format=json&h=1`. Extract venue, year, authors, BibTeX key, DOI. No authentication required. Rate limit: polite usage (~1 req/s).

**Rationale:** DBLP is authoritative for CS/IT conferences and journals. Simple JSON API, no auth overhead. Only valuable for CS-domain entities but has near-perfect coverage there.

### D7: `EnrichedRecord` extension — optional fields only

**Decision:** Add optional fields to `EnrichedRecord`: `funding: Optional[List[str]]`, `references_count: Optional[int]`, `tldr: Optional[str]`, `influential_citation_count: Optional[int]`, `license: Optional[str]`, `mesh_terms: Optional[List[str]]`, `venue: Optional[str]`. All default to `None`.

**Rationale:** Backward-compatible — existing adapters don't set these fields and they default to None. New adapters populate them when available. The enrichment worker already persists arbitrary fields from `EnrichedRecord` into `attributes_json`.

### D8: Provider health endpoint

**Decision:** New `GET /enrichment/providers` endpoint returning circuit breaker state, success/failure counts, and last-used timestamp for each registered provider.

**Rationale:** Operators need visibility into which providers are healthy, tripped, or disabled. Useful for debugging `no_provider_match` failures.

## Risks / Trade-offs

- **[Rate limiting from multiple providers]** → Each provider has its own circuit breaker with independent thresholds. Polite delays (1-2s between cascade steps) prevent abuse. Configurable cascade allows disabling providers.
- **[Cascade latency for no-match entities]** → An entity that matches no provider must traverse all providers before failing. Mitigated: circuit breakers skip tripped providers instantly; configurable cascade can reduce the chain.
- **[Semantic Scholar rate limits are strict]** → 5000 req/5min shared among unauthenticated users. Mitigated: S2 is late in cascade (most entities match earlier); circuit breaker trips after 3 failures; exponential backoff on 429.
- **[DBLP only useful for CS]** → Entities from non-CS domains waste a request to DBLP that always returns empty. Mitigated: DBLP is last before Scholar; fast 404 response (~200ms); can be removed from cascade via env var.
- **[PubMed has no citation counts]** → PubMed returns `citation_count=0` always. Mitigated: if PubMed enriches an entity, subsequent manual re-enrichment via OpenAlex could fill citation counts (future enhancement).
