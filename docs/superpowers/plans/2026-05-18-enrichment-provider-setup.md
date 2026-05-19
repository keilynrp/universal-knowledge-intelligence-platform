# Enrichment Provider Setup

UKIP's enrichment cascade is configured with `ENRICHMENT_CASCADE`, a comma-separated list of provider IDs. When unset, the default order is:

```text
scopus,wos,openalex,crossref,pubmed,semantic_scholar,dblp,scholar
```

Use a smaller cascade when a deployment should avoid paid providers or experimental fallbacks:

```env
ENRICHMENT_CASCADE=openalex,crossref,pubmed,semantic_scholar,dblp
```

## Providers

- `openalex`: Free default scholarly metadata source. No key required.
- `crossref`: Free DOI metadata, funding, references, license, and publisher metadata. No key required; UKIP sends a polite-pool `mailto`.
- `pubmed`: Free biomedical metadata and MeSH terms. Set `NCBI_API_KEY` for higher NCBI rate limits.
- `semantic_scholar`: Free paper metadata, TLDR, influential citation counts, and venue. Optional `S2_API_KEY` enables higher API limits.
- `dblp`: Free computer science venue metadata. Optional `DBLP_MIRROR` can point to a mirror endpoint.
- `scopus`: BYOK provider. Set `SCOPUS_API_KEY`; inactive without a key.
- `wos`: BYOK provider. Set `WOS_API_KEY`; inactive without a key.
- `scholar`: Disabled by default. Set `SCHOLAR_ENABLED=1` only when the deployment intentionally allows the scraping fallback.

Provider health is exposed at `GET /enrichment/providers`, including active state, circuit breaker status, counters, and last-used timestamps.
