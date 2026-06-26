import logging
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx
import re

from backend.schemas_enrichment import AuthorAffiliation, CanonicalAffiliation, EnrichedRecord, JournalMetrics
from backend.adapters.enrichment.base import BaseScientometricAdapter
from backend.cache import MISS, get_cache, make_key

logger = logging.getLogger(__name__)

# Module-level cache: one week TTL, keyed by OpenAlex source ID.
# InProcessBackend stores raw Python objects (no serializer needed).
# RedisBackend receives plain JSON-safe dicts (str/float/int/bool/None) — safe.
_SOURCE_CACHE = get_cache("enrichment:openalex_source", ttl=7 * 24 * 3600, maxsize=20_000)


def clear_source_cache() -> int:
    """Invalidate every cached ``/sources`` metric and return how many entries
    were dropped.

    The source cache stores the *computed* ``nif_field`` alongside the raw
    metrics, so after the field/subfield resolver changes a backfill would
    otherwise reuse stale values (the cache is Redis-backed and survives
    deploys). Clearing it forces fresh ``/sources`` fetches that recompute the
    bucket.
    """
    return _SOURCE_CACHE.invalidate_prefix()


def _primary_field(body: dict) -> Optional[str]:
    """Display name of the source's dominant OpenAlex *field*, used as the NIF
    normalization bucket.

    We sum each topic's ``count`` per field and return the highest-scoring field
    (ties broken alphabetically for determinism). Field — not subfield — because
    multidisciplinary and medical megajournals carry a few enormous spurious
    subfield topics (e.g. health-economics → "Economics and Econometrics") that
    dominate single-top-topic and per-subfield selection; rolling up to the field
    level (e.g. "Medicine") is robust to that and yields denser, more meaningful
    normalization buckets. Returns None when topics or their fields are absent.
    """
    totals: dict[str, int] = {}
    for topic in (body.get("topics") or []):
        if not topic:
            continue
        field = (topic.get("field") or {}).get("display_name")
        if field:
            totals[field] = totals.get(field, 0) + (topic.get("count") or 0)
    if not totals:
        return None
    return sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _works_last_2_complete_years(counts) -> Optional[int]:
    """Sum works_count over the two most recent COMPLETE calendar years in
    OpenAlex counts_by_year (the current, partial year is excluded). Returns
    None when the data is absent/unusable."""
    if not counts:
        return None
    current_year = datetime.now(timezone.utc).year
    complete = [
        c for c in counts
        if isinstance(c.get("year"), int) and c["year"] < current_year
        and isinstance(c.get("works_count"), (int, float))
    ]
    if not complete:
        return None
    complete.sort(key=lambda row: row["year"], reverse=True)
    return sum(int(c["works_count"]) for c in complete[:2])


class OpenAlexAdapter(BaseScientometricAdapter):
    """
    Adapter for OpenAlex API. Free, enormous, and highly interconnected.
    Good practice: Includes an etiquette email `mailto:` param to use the fast lane.
    Rate Limit: 100,000 reqs/day, heavily throttled on loops unless polite.
    """

    BASE_URL = "https://api.openalex.org/works"
    SOURCES_URL = "https://api.openalex.org/sources"

    def __init__(self, polite_email: Optional[str] = "research@ukip.dev"):
        self.client = httpx.Client(timeout=10.0)
        self.polite_email = polite_email

    @property
    def is_active(self) -> bool:
        """OpenAlex is always active — no API key required (polite pool via mailto).

        This must stay declared explicitly because the enrichment cascade
        treats a missing attribute as inactive (``getattr(adapter, 'is_active',
        False)`` in ``backend.enrichment_worker``). Without it, OpenAlex is
        silently skipped and affiliation-rich data never reaches RawEntity.
        """
        return True

    def _build_params(self, custom_params: dict) -> dict:
        params = custom_params.copy()
        if self.polite_email:
            params["mailto"] = self.polite_email
        return params

    # Rate-limit/transient statuses worth retrying (OpenAlex returns 429 on
    # bursts even within the polite pool; 503 is a transient upstream error).
    _RETRY_STATUSES = frozenset({429, 503})
    _MAX_RETRIES = 3
    _MAX_BACKOFF = 8.0  # seconds

    def _get(self, url: str, params: dict):
        """GET with bounded retry on rate-limit/transient statuses.

        Honors the ``Retry-After`` header when present, otherwise backs off
        exponentially. Returns the final response (caller still inspects
        ``status_code``); only 429/503 are retried so genuine 4xx/5xx fail fast.
        """
        resp = self.client.get(url, params=params)
        for attempt in range(1, self._MAX_RETRIES + 1):
            if resp.status_code not in self._RETRY_STATUSES:
                return resp
            retry_after = resp.headers.get("Retry-After") if hasattr(resp, "headers") else None
            try:
                wait = float(retry_after) if retry_after else min(2.0 ** attempt, self._MAX_BACKOFF)
            except (TypeError, ValueError):
                wait = min(2.0 ** attempt, self._MAX_BACKOFF)
            logger.info(
                "OpenAlex %s (rate-limited) — retrying in %.1fs (attempt %d/%d)",
                resp.status_code, wait, attempt, self._MAX_RETRIES,
            )
            time.sleep(wait)
            resp = self.client.get(url, params=params)
        return resp

    def fetch_source_metrics(self, source_id: str) -> Optional[JournalMetrics]:
        """Fetch /sources/{id} metrics (2yr_mean_citedness, h_index, apc_usd), cached by source_id.

        Returns a JournalMetrics with source-level bibliometric data, or None if
        source_id is empty or the API returns a non-200 response. Only successful
        (200) responses are stored in the cache — transient failures (timeouts,
        429s, 503s) are NOT cached, so a one-off API error does not suppress a
        real source for the full cache TTL.
        """
        if not source_id:
            return None

        key = make_key(("source", source_id))
        cached = _SOURCE_CACHE.get(key)
        if cached is not MISS:
            return JournalMetrics(**cached)

        params = self._build_params({})
        resp = self._get(f"{self.SOURCES_URL}/{source_id}", params=params)
        if resp.status_code != 200:
            return None  # transient failure — do NOT cache

        body = resp.json()
        stats = body.get("summary_stats") or {}
        data = {
            "issn_l": body.get("issn_l"),
            "source_id": source_id,
            "display_name": body.get("display_name"),
            "two_yr_mean_citedness": stats.get("2yr_mean_citedness"),
            "h_index": stats.get("h_index"),
            "apc_usd": body.get("apc_usd"),
            "apc_source": "openalex" if body.get("apc_usd") is not None else None,
            "is_in_doaj": body.get("is_in_doaj"),
            "nif_field": _primary_field(body),
            "works_2yr": _works_last_2_complete_years(body.get("counts_by_year")),
        }
        _SOURCE_CACHE.set(key, data)
        return JournalMetrics(**data)

    def _parse_record(self, raw_openalex: dict) -> EnrichedRecord:
        """
        Takes raw OpenAlex JSON payload and forces it to strictly output the EnrichedRecord 
        Normalized Data Object. Normalizes DOIs, identifies authors safely, and extracts metrics.
        """
        # Parse basic fields
        id_str = raw_openalex.get("id", "unknown")
        
        # 1. Strip the redundant URL prefix some APIs inject
        raw_doi = raw_openalex.get("doi")
        clean_doi = raw_doi.replace("https://doi.org/", "") if raw_doi else None
        
        title = raw_openalex.get("display_name") or raw_openalex.get("title") or "Untitled"
        cited_count = raw_openalex.get("cited_by_count", 0)
        pub_year = raw_openalex.get("publication_year")

        # 2. Extract Open Access flag
        oa_status = raw_openalex.get("open_access", {}).get("is_oa", False)

        # 3. Dig into authors list dynamically
        author_list = []
        orcid_list = []
        canonical_affiliations_by_key: dict[tuple[str, str], CanonicalAffiliation] = {}
        author_affiliations: list[AuthorAffiliation] = []
        for order, authorship in enumerate(raw_openalex.get("authorships", []), start=1):
            author_data = authorship.get("author", {})
            name = author_data.get("display_name")
            author_institutions: list[CanonicalAffiliation] = []
            for institution in authorship.get("institutions", []) or []:
                institution_name = institution.get("display_name")
                if not institution_name:
                    continue
                affiliation = CanonicalAffiliation(
                    name=institution_name,
                    ror=institution.get("ror"),
                    openalex_id=institution.get("id"),
                    country_code=institution.get("country_code"),
                    type=institution.get("type"),
                    lineage=[
                        str(item)
                        for item in (institution.get("lineage") or [])
                        if item is not None
                    ],
                )
                key = _affiliation_dedupe_key(affiliation)
                canonical_affiliations_by_key.setdefault(key, affiliation)
                author_institutions.append(affiliation)
            if name:
                author_list.append(name)
                raw_orcid = author_data.get("orcid")
                # Strip URL prefix if present (e.g. "https://orcid.org/0000-...")
                orcid = raw_orcid.replace("https://orcid.org/", "") if raw_orcid else None
                orcid_list.append(orcid)
                author_affiliations.append(
                    AuthorAffiliation(
                        author_name=name,
                        author_orcid=orcid,
                        author_openalex_id=author_data.get("id"),
                        author_position=authorship.get("author_position"),
                        author_order=order,
                        institutions=author_institutions,
                    )
                )
        
        # 4. Extract concepts from concepts, topics, and keywords fields
        concept_list = []
        concept_id_list = []  # Positional OpenAlex concept IDs (None for topics/keywords)
        seen_concepts: set[str] = set()
        for concept in raw_openalex.get("concepts", []):
            concept_name = concept.get("display_name")
            if concept_name and concept.get("score", 0) >= 0.4:
                key = concept_name.lower()
                if key not in seen_concepts:
                    seen_concepts.add(key)
                    concept_list.append(concept_name)
                    concept_id_list.append(concept.get("id"))
        for topic in raw_openalex.get("topics", []):
            topic_name = topic.get("display_name")
            if topic_name and topic.get("score", 0) >= 0.4:
                key = topic_name.lower()
                if key not in seen_concepts:
                    seen_concepts.add(key)
                    concept_list.append(topic_name)
                    concept_id_list.append(None)
        for kw in raw_openalex.get("keywords", []):
            kw_name = kw.get("display_name") if isinstance(kw, dict) else (kw if isinstance(kw, str) else None)
            if kw_name:
                key = kw_name.lower()
                if key not in seen_concepts:
                    seen_concepts.add(key)
                    concept_list.append(kw_name)
                    concept_id_list.append(None)

        # 5. Get publisher / venue and journal identity
        publisher = None
        journal = None
        host_venue = raw_openalex.get("primary_location") or {}
        if host_venue:
            source = host_venue.get("source") or {}
            if source:
                publisher = source.get("display_name")
                raw_sid = source.get("id")
                source_id = raw_sid.replace("https://openalex.org/", "") if raw_sid else None
                journal = JournalMetrics(
                    issn_l=source.get("issn_l"),
                    source_id=source_id,
                    display_name=source.get("display_name"),
                )

        return EnrichedRecord(
            id=id_str,
            doi=clean_doi,
            title=title,
            authors=author_list,
            author_orcids=orcid_list,
            citation_count=cited_count,
            publication_year=pub_year,
            publisher=publisher,
            is_open_access=oa_status,
            concepts=concept_list,
            concept_ids=concept_id_list,
            affiliations=[
                _affiliation_legacy_label(affiliation)
                for affiliation in canonical_affiliations_by_key.values()
            ],
            canonical_affiliations=list(canonical_affiliations_by_key.values()),
            author_affiliations=author_affiliations,
            source_api="OpenAlex",
            raw_response=raw_openalex,  # Attach whole tree for potential late parsing rules
            journal=journal,
        )

    def search_by_doi(self, doi: str) -> Optional[EnrichedRecord]:
        """
        OpenAlex supports direct lookup by appending the DOI to the base URL or filtering.
        """
        # OpenAlex expects https://doi.org/10.xyz format inside the API paths sometimes
        # We enforce searching with `filter=doi:xxxxx` to be safe against URL encoding weirdness
        params = self._build_params({"filter": f"doi:{doi}"})
        response = self._get(self.BASE_URL, params=params)

        if response.status_code != 200:
            return None

        json_resp = response.json()
        results = json_resp.get("results", [])
        if not results:
            return None
            
        return self._parse_record(results[0])

    def search_by_title(self, title: str, limit: int = 5) -> List[EnrichedRecord]:
        query = urllib.parse.quote_plus(title)
        # We use `search=` which hits the title and abstract, which is resilient against short titles
        params = self._build_params({
            "search": query,
            "per-page": limit
        })
        response = self.client.get(self.BASE_URL, params=params)
        
        if response.status_code != 200:
            return []

        results = response.json().get("results", [])
        return [self._parse_record(r) for r in results]

    def search_by_author(self, name: str, limit: int = 10) -> List[EnrichedRecord]:
        # Filter works authored by someone with a specific name
        params = self._build_params({
            "filter": f"author.display_name.search:{name}",
            "per-page": limit,
            "sort": "cited_by_count:desc" # Defaulting to their best works
        })
        response = self.client.get(self.BASE_URL, params=params)

        if response.status_code != 200:
            return []

        results = response.json().get("results", [])
        return [self._parse_record(r) for r in results]

    _BULK_MAX = 1_000
    _BULK_PAGE_SIZE = 200
    _BULK_INTER_PAGE_DELAY = 0.2  # seconds — polite pool etiquette

    def search_bulk(
        self,
        query: str,
        filters: Optional[Dict[str, str]] = None,
        limit: int = 100,
    ) -> List[EnrichedRecord]:
        """
        Multi-page bulk collection from OpenAlex using cursor pagination.

        Supported filters:
          - "author":      maps to filter=author.display_name.search:<value>
          - "institution": maps to filter=authorships.institutions.display_name.search:<value>
          - "issn":        maps to filter=primary_location.source.issn:<value>
          - "concept_id":  maps to filter=concepts.id:<value>  (e.g. "C41008148")

        Polite-pool etiquette: mailto= is already added by _build_params; a 0.2s
        inter-page delay is applied to stay within the fast lane.
        """
        limit = min(limit, self._BULK_MAX)
        filters = filters or {}

        # Build filter string
        filter_parts: List[str] = []
        if "author" in filters:
            filter_parts.append(f"author.display_name.search:{filters['author']}")
        if "institution" in filters:
            filter_parts.append(
                f"authorships.institutions.display_name.search:{filters['institution']}"
            )
        if "issn" in filters:
            filter_parts.append(f"primary_location.source.issn:{filters['issn']}")
        if "concept_id" in filters:
            filter_parts.append(f"concepts.id:{filters['concept_id']}")

        collected: List[EnrichedRecord] = []
        cursor = "*"

        while len(collected) < limit:
            per_page = min(self._BULK_PAGE_SIZE, limit - len(collected))
            params = self._build_params(
                {
                    "search": query,
                    "per-page": per_page,
                    "cursor": cursor,
                    **({"filter": ",".join(filter_parts)} if filter_parts else {}),
                }
            )

            try:
                response = self.client.get(self.BASE_URL, params=params)
            except Exception:
                break

            if response.status_code != 200:
                break

            body = response.json()
            results = body.get("results", [])
            if not results:
                break

            collected.extend(self._parse_record(r) for r in results)

            next_cursor = body.get("meta", {}).get("next_cursor")
            if not next_cursor:
                break
            cursor = next_cursor

            time.sleep(self._BULK_INTER_PAGE_DELAY)

        return collected[:limit]


def _affiliation_dedupe_key(affiliation: CanonicalAffiliation) -> tuple[str, str]:
    if affiliation.ror:
        return ("ror", affiliation.ror.strip().lower().removeprefix("https://ror.org/"))
    if affiliation.openalex_id:
        return ("openalex", affiliation.openalex_id.strip().lower())
    normalized_name = re.sub(r"\s+", " ", affiliation.name).strip().casefold()
    return ("name_country", f"{normalized_name}|{affiliation.country_code or ''}")


def _affiliation_legacy_label(affiliation: CanonicalAffiliation) -> str:
    if affiliation.country_code:
        return f"{affiliation.name}, {affiliation.country_code}"
    return affiliation.name
