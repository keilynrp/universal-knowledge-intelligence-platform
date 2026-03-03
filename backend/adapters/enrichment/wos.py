import logging
import httpx
from typing import List, Optional

from backend.schemas_enrichment import EnrichedRecord
from backend.adapters.enrichment.base import BaseScientometricAdapter

logger = logging.getLogger(__name__)

class WebOfScienceAdapter(BaseScientometricAdapter):
    """
    Scientometric Adapter for Clarivate Web of Science (WoS) Starter API.
    Implements Phase 3: Premium APIs (BYOK - Bring Your Own Key).
    """
    def __init__(self, api_key: Optional[str] = None):
        """
        Initializes the WoS Adapter. The adapter remains inactive if no API key is provided.
        """
        self.api_key = api_key
        self.base_url = "https://wos-api.clarivate.com/api/wos"
        
        if self.api_key:
            logger.info("WebOfScienceAdapter initialized with a BYOK API Key (Phase 3 Active).")
        else:
            logger.info("WebOfScienceAdapter is inactive (No API Key provided).")

    @property
    def is_active(self) -> bool:
        return bool(self.api_key)

    def search_by_doi(self, doi: str) -> Optional[EnrichedRecord]:
        """
        Search WoS by DOI (Digital Object Identifier).
        """
        if not self.is_active:
            return None
        results = self._execute_search(f'DO="{doi}"', limit=1)
        return results[0] if results else None

    def search_by_title(self, title: str, limit: int = 5) -> List[EnrichedRecord]:
        """
        Searches WoS for a specific publication title.
        """
        if not self.is_active:
            return []
        query = f'TI="{title}"'
        return self._execute_search(query, limit=limit)

    def search_by_author(self, name: str, limit: int = 10) -> List[EnrichedRecord]:
        """
        Searches WoS based on the author's name.
        """
        if not self.is_active:
            return []
        query = f'AU="{name}"'
        return self._execute_search(query, limit=limit)

    def _execute_search(self, query: str, limit: int) -> List[EnrichedRecord]:
        headers = {
            "X-ApiKey": self.api_key or "",
            "Accept": "application/json"
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(
                    self.base_url,
                    headers=headers,
                    params={
                        "databaseId": "WOS",
                        "usrQuery": query,
                        "count": limit,
                        "firstRecord": 1
                    },
                    timeout=10.0
                )
                if response.status_code == 401 or response.status_code == 403:
                    logger.warning("WebOfScienceAdapter API Key is invalid or rate-limited.")
                    return []
                    
                response.raise_for_status()
                data = response.json()
                
                # WoS JSON structure extraction
                records = data.get("Data", {}).get("Records", {}).get("records", {}).get("REC", [])
                if isinstance(records, dict): # Single record case
                    records = [records]
                    
                return [self._convert_to_ndo(rec) for rec in records]
        except Exception as e:
            logger.error(f"WebOfScienceAdapter search error: {e}")
            return []

    def _convert_to_ndo(self, rec: dict) -> EnrichedRecord:
        """
        Converts the dynamic WoS JSON output into our Normalized Data Object.
        """
        uid = rec.get("UID", "")
        static_data = rec.get("static_data", {})
        summary = static_data.get("summary", {})
        
        # Extract title
        titles = summary.get("titles", {}).get("title", [])
        if isinstance(titles, dict):
            titles = [titles]
            
        main_title = "Unknown Title"
        for t in titles:
            if isinstance(t, dict) and t.get("type") == "item":
                main_title = t.get("content", "Unknown Title")
                break
                
        # Extract Citations
        dynamic_data = rec.get("dynamic_data", {})
        citation_count = 0
        try:
            tc_val = dynamic_data.get("citation_related", {}).get("tc_list", {}).get("silo_tc", {}).get("local_count", 0)
            citation_count = int(tc_val)
        except (ValueError, TypeError):
            pass
             
        # Extract Authors
        authors = []
        names = summary.get("names", {}).get("name", [])
        if isinstance(names, dict):
            names = [names]
        for n in names:
            if isinstance(n, dict):
                 authors.append(n.get("full_name", ""))
                 
        return EnrichedRecord(
            doi=uid,  # Using WOS UID as primary identifier if pure DOI is not found
            title=main_title,
            authors=authors,
            citation_count=citation_count,
            concepts=["WoS-Indexed"], # WoS keywords require complex abstract mining
            source_api="Web of Science (Premium)",
            raw_response=rec
        )
