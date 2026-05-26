import logging
from typing import List, Optional
from scholarly import scholarly, ProxyGenerator

from backend.schemas_enrichment import EnrichedRecord
from backend.adapters.enrichment.base import BaseScientometricAdapter

logger = logging.getLogger(__name__)

class ScholarAdapter(BaseScientometricAdapter):
    """
    Scientometric Adapter for Google Scholar using the `scholarly` library.
    Implements Phase 2: Restricted Scraping.
    """
    def __init__(self, use_free_proxies: bool = False, scraper_api_key: Optional[str] = None):
        """
        Initializes the adapter with optional proxy configuration to avoid IP bans.
        """
        self.pg = ProxyGenerator()
        setup_success = False

        if scraper_api_key:
            logger.info("Setting up ScraperAPI proxy for ScholarAdapter...")
            setup_success = self.pg.ScraperAPI(scraper_api_key)
        elif use_free_proxies:
            logger.info("Setting up Free Proxies for ScholarAdapter...")
            setup_success = self.pg.FreeProxies()
        
        if setup_success:
            scholarly.use_proxy(self.pg)
            logger.info("Proxy successfully configured for ScholarAdapter.")
            self._proxy_ready = True
        else:
            logger.warning("ScholarAdapter running WITHOUT proxy. High risk of IP ban.")
            self._proxy_ready = False

    @property
    def is_active(self) -> bool:
        """Scholar requires a proxy to be safely usable. Without it the
        adapter is considered inactive so the cascade skips it explicitly
        (the enrichment_worker treats missing ``is_active`` as inactive)."""
        return bool(getattr(self, "_proxy_ready", False))

    def search_by_doi(self, doi: str) -> Optional[EnrichedRecord]:
        """
        Google Scholar is not optimal for direct DOI search, but we fall back to a standard
        title search using the DOI.
        """
        return self._search_and_convert(doi, limit=1)

    def search_by_title(self, title: str, limit: int = 5) -> List[EnrichedRecord]:
        """
        Searches Google Scholar for a specific publication title.
        """
        try:
            results = []
            search_query = scholarly.search_pubs(title)
            for _ in range(limit):
                try:
                    pub = next(search_query)
                    if pub:
                        results.append(self._convert_to_ndo(pub))
                except StopIteration:
                    break
            return results
        except Exception as e:
            logger.error(f"ScholarAdapter search_by_title error: {e}")
            return []

    def search_by_author(self, name: str, limit: int = 10) -> List[EnrichedRecord]:
        """
        Finds matching works depending on the author's normalized name.
        """
        try:
            results = []
            search_query = scholarly.search_pubs(f"author:{name}")
            for _ in range(limit):
                try:
                    pub = next(search_query)
                    if pub:
                        results.append(self._convert_to_ndo(pub))
                except StopIteration:
                    break
            return results
        except Exception as e:
            logger.error(f"ScholarAdapter search_by_author error: {e}")
            return []

    def _convert_to_ndo(self, scholar_pub: dict) -> EnrichedRecord:
        """
        Converts the raw output of `scholarly.search_pubs()` into our Normalized Data Object.
        """
        bib = scholar_pub.get("bib", {})
        
        # Scholar might not return an explicit list of concepts natively without deeply parsing
        # abstract or keyword fields. We attempt to extract abstract words conservatively.
        concepts = []
        abstract = bib.get("abstract", "")
        if abstract:
            # Very rudimentary keyword extraction logic to populate concepts if available
            words = [w for w in abstract.split() if len(w) > 5]
            concepts = list(set(words[:10]))  # Just take some long words as dummy concepts for now

        # Map to EnrichedRecord
        return EnrichedRecord(
            doi=scholar_pub.get("pub_url", ""), # Often there is no pure DOI in raw search results
            title=bib.get("title", "Unknown Title"),
            authors=bib.get("author", []),
            citation_count=scholar_pub.get("num_citations", 0),
            concepts=concepts,
            source_api="Google Scholar",
            raw_response=scholar_pub
        )
