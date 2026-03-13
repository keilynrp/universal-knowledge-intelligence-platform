import logging
import httpx
from typing import List, Optional

from backend.schemas_enrichment import EnrichedRecord
from backend.adapters.enrichment.base import BaseScientometricAdapter

logger = logging.getLogger(__name__)

class ScopusAdapter(BaseScientometricAdapter):
    """
    Scientometric Adapter for Elsevier Scopus Search API.
    Implements Phase 3: Premium APIs (BYOK - Bring Your Own Key).
    """
    def __init__(self, api_key: Optional[str] = None):
        """
        Initializes the Scopus Adapter. The adapter remains inactive if no API key is provided.
        """
        self.api_key = api_key
        self.base_url = "https://api.elsevier.com/content/search/scopus"
        
        if self.api_key:
            logger.info("ScopusAdapter initialized with a BYOK API Key (Phase 3 Active).")
        else:
            logger.info("ScopusAdapter is inactive (No API Key provided).")

    @property
    def is_active(self) -> bool:
        return bool(self.api_key)

    def search_by_doi(self, doi: str) -> Optional[EnrichedRecord]:
        """
        Search Scopus by DOI.
        """
        if not self.is_active:
            return None
        results = self._execute_search(f'DOI("{doi}")', limit=1)
        return results[0] if results else None

    def search_by_title(self, title: str, limit: int = 5) -> List[EnrichedRecord]:
        """
        Searches Scopus for a specific publication title.
        """
        if not self.is_active:
            return []
        query = f'TITLE("{title}")'
        return self._execute_search(query, limit=limit)

    def search_by_author(self, name: str, limit: int = 10) -> List[EnrichedRecord]:
        """
        Searches Scopus based on the author's name.
        """
        if not self.is_active:
            return []
        query = f'AUTH("{name}")'
        return self._execute_search(query, limit=limit)

    def _execute_search(self, query: str, limit: int) -> List[EnrichedRecord]:
        headers = {
            "X-ELS-APIKey": self.api_key or "",
            "Accept": "application/json"
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(
                    self.base_url,
                    headers=headers,
                    params={
                        "query": query,
                        "count": limit,
                    },
                    timeout=10.0
                )
                if response.status_code in (401, 403):
                    logger.warning("ScopusAdapter API Key is invalid or rate-limited.")
                    return []
                    
                response.raise_for_status()
                data = response.json()
                
                entries = data.get("search-results", {}).get("entry", [])
                return [self._convert_to_ndo(entry) for entry in entries if entry.get("error") is None]
        except Exception as e:
            logger.error(f"ScopusAdapter search error: {e}")
            return []

    def _convert_to_ndo(self, rec: dict) -> EnrichedRecord:
        """
        Converts the dynamic Scopus JSON output into our Normalized Data Object.
        """
        uid = rec.get("dc:identifier", "").replace("SCOPUS_ID:", "")
        doi = rec.get("prism:doi", uid)
        main_title = rec.get("dc:title", "Unknown Title")
        
        citation_count_str = rec.get("citedby-count", "0")
        try:
            citation_count = int(citation_count_str)
        except (ValueError, TypeError):
            citation_count = 0
            
        creator = rec.get("dc:creator")
        authors = [creator] if creator else []
                 
        return EnrichedRecord(
            doi=doi,  
            title=main_title,
            authors=authors,
            citation_count=citation_count,
            concepts=["Scopus-Indexed"], 
            source_api="Elsevier Scopus (Premium)",
            raw_response=rec
        )
