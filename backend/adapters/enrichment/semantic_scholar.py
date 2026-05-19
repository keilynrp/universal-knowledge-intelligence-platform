import os
import time
from typing import List, Optional

import httpx

from backend.schemas_enrichment import EnrichedRecord
from backend.adapters.enrichment.base import BaseScientometricAdapter


class SemanticScholarAdapter(BaseScientometricAdapter):
    """
    Adapter for Semantic Scholar Academic Graph API.
    Provides TL;DR summaries and influential citation counts.
    Rate Limit: 100 req/5min unauthenticated; higher with S2_API_KEY.
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    _FIELDS = "title,authors,year,citationCount,influentialCitationCount,isOpenAccess,tldr,venue,externalIds"
    _REQUEST_DELAY = 0.2

    def __init__(self) -> None:
        api_key = os.environ.get("S2_API_KEY")
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        self.client = httpx.Client(timeout=15.0, headers=headers)

    @property
    def is_active(self) -> bool:
        return True

    def _parse_record(self, raw: dict) -> EnrichedRecord:
        paper_id = raw.get("paperId", "unknown")
        external_ids = raw.get("externalIds") or {}
        doi = external_ids.get("DOI")
        title = raw.get("title") or "Untitled"
        authors = [a.get("name") for a in (raw.get("authors") or []) if a.get("name")]
        citation_count = raw.get("citationCount") or 0
        publication_year = raw.get("year")
        venue = raw.get("venue") or None
        is_open_access = raw.get("isOpenAccess") or False

        tldr_obj = raw.get("tldr")
        tldr_text = tldr_obj.get("text") if isinstance(tldr_obj, dict) else None
        influential_citation_count = raw.get("influentialCitationCount")

        return EnrichedRecord(
            id=paper_id,
            doi=doi,
            title=title,
            authors=authors,
            citation_count=citation_count,
            publication_year=publication_year,
            publisher=venue,
            is_open_access=is_open_access,
            source_api="Semantic Scholar",
            tldr=tldr_text,
            influential_citation_count=influential_citation_count,
            venue=venue,
            raw_response=raw,
        )

    def search_by_doi(self, doi: str) -> Optional[EnrichedRecord]:
        url = f"{self.BASE_URL}/paper/DOI:{doi}"
        params = {"fields": self._FIELDS}
        response = self.client.get(url, params=params)
        time.sleep(self._REQUEST_DELAY)

        if response.status_code == 404:
            return None
        if response.status_code == 429 or response.status_code >= 500:
            response.raise_for_status()
        if response.status_code != 200:
            return None

        return self._parse_record(response.json())

    def search_by_title(self, title: str, limit: int = 5) -> List[EnrichedRecord]:
        url = f"{self.BASE_URL}/paper/search"
        params = {"query": title, "fields": self._FIELDS, "limit": limit}
        response = self.client.get(url, params=params)
        time.sleep(self._REQUEST_DELAY)

        if response.status_code == 429 or response.status_code >= 500:
            response.raise_for_status()
        if response.status_code != 200:
            return []

        papers = response.json().get("data", [])
        return [self._parse_record(p) for p in papers]

    def search_by_author(self, name: str, limit: int = 10) -> List[EnrichedRecord]:
        url = f"{self.BASE_URL}/paper/search"
        params = {"query": name, "fields": self._FIELDS, "limit": limit}
        response = self.client.get(url, params=params)
        time.sleep(self._REQUEST_DELAY)

        if response.status_code == 429 or response.status_code >= 500:
            response.raise_for_status()
        if response.status_code != 200:
            return []

        papers = response.json().get("data", [])
        return [self._parse_record(p) for p in papers]
