import logging
import os
import re
import time
import urllib.parse
from typing import List, Optional

import httpx

from backend.adapters.enrichment.base import BaseScientometricAdapter
from backend.schemas_enrichment import EnrichedRecord

logger = logging.getLogger(__name__)


class DBLPAdapter(BaseScientometricAdapter):
    """
    Adapter for the DBLP Computer Science Bibliography API.
    DBLP is free and does not require authentication.
    Rate etiquette: 1-second delay between requests.
    Note: DBLP does not provide citation counts.
    """

    SEARCH_URL = "https://dblp.org/search/publ/api"

    def __init__(self) -> None:
        mirror = os.environ.get("DBLP_MIRROR")
        if mirror:
            self.SEARCH_URL = mirror.rstrip("/") + "/search/publ/api"
        self.client = httpx.Client(timeout=15.0)

    @property
    def is_active(self) -> bool:
        return True

    def _polite_delay(self) -> None:
        """1-second polite delay between requests."""
        time.sleep(1.0)

    def _extract_doi(self, ee_field) -> Optional[str]:
        """
        Extract DOI from the `ee` field which can be a string or a list of strings.
        Looks for URLs containing 'doi.org/'.
        """
        if ee_field is None:
            return None

        urls: List[str] = []
        if isinstance(ee_field, str):
            urls = [ee_field]
        elif isinstance(ee_field, list):
            urls = ee_field
        elif isinstance(ee_field, dict):
            # Sometimes ee is a dict with a "text" key
            text = ee_field.get("text")
            if text:
                urls = [text] if isinstance(text, str) else text

        for url in urls:
            if isinstance(url, str) and "doi.org/" in url:
                match = re.search(r"doi\.org/(.+)$", url)
                if match:
                    return match.group(1).rstrip("/")
        return None

    def _parse_authors(self, authors_field) -> List[str]:
        """
        Parse authors from DBLP's authors.author structure.
        Can be a list of dicts or a single dict, each with a 'text' field.
        """
        if authors_field is None:
            return []

        author_data = authors_field.get("author", [])

        if isinstance(author_data, dict):
            author_data = [author_data]

        result: List[str] = []
        for entry in author_data:
            if isinstance(entry, dict):
                name = entry.get("text")
                if name:
                    result.append(name)
            elif isinstance(entry, str):
                result.append(entry)
        return result

    def _parse_record(self, hit: dict) -> EnrichedRecord:
        """
        Maps a DBLP JSON hit object to the normalized EnrichedRecord.
        The hit contains an `info` sub-object with the publication data.
        """
        info = hit.get("info", {})

        record_id = info.get("@id") or info.get("key", "unknown")
        title = info.get("title", "Untitled")
        # DBLP sometimes appends a trailing period to titles
        if isinstance(title, str) and title.endswith("."):
            title = title[:-1]

        doi = self._extract_doi(info.get("ee"))
        authors = self._parse_authors(info.get("authors"))
        venue = info.get("venue")

        pub_year: Optional[int] = None
        raw_year = info.get("year")
        if raw_year is not None:
            try:
                pub_year = int(raw_year)
            except (ValueError, TypeError):
                pub_year = None

        return EnrichedRecord(
            id=str(record_id),
            doi=doi,
            title=title,
            authors=authors,
            author_orcids=[],
            citation_count=0,
            publication_year=pub_year,
            publisher=venue,
            is_open_access=False,
            concepts=[],
            concept_ids=[],
            source_api="DBLP",
            venue=venue,
            raw_response=hit,
        )

    def _extract_hits(self, response: httpx.Response) -> List[dict]:
        """
        Extracts the hit list from a DBLP search JSON response.
        Raises on 429/5xx for circuit breaker integration.
        """
        if response.status_code == 429 or response.status_code >= 500:
            response.raise_for_status()

        if response.status_code != 200:
            logger.warning("DBLP returned status %d", response.status_code)
            return []

        data = response.json()
        hits = data.get("result", {}).get("hits", {})
        hit_list = hits.get("hit", [])

        if not isinstance(hit_list, list):
            return []

        return hit_list

    def search_by_title(self, title: str, limit: int = 5) -> List[EnrichedRecord]:
        """Search DBLP publications by title."""
        self._polite_delay()

        params = {
            "q": title,
            "format": "json",
            "h": limit,
        }

        try:
            response = self.client.get(self.SEARCH_URL, params=params)
        except httpx.HTTPError as exc:
            logger.error("DBLP search_by_title request failed: %s", exc)
            return []

        hit_list = self._extract_hits(response)
        return [self._parse_record(hit) for hit in hit_list]

    def search_by_doi(self, doi: str) -> Optional[EnrichedRecord]:
        """
        Search DBLP using DOI as query term, then filter results
        by matching DOI in the `ee` field.
        """
        self._polite_delay()

        params = {
            "q": doi,
            "format": "json",
            "h": 10,
        }

        try:
            response = self.client.get(self.SEARCH_URL, params=params)
        except httpx.HTTPError as exc:
            logger.error("DBLP search_by_doi request failed: %s", exc)
            return None

        hit_list = self._extract_hits(response)

        normalized_doi = doi.lower().strip()
        for hit in hit_list:
            record = self._parse_record(hit)
            if record.doi and record.doi.lower().strip() == normalized_doi:
                return record

        return None

    def search_by_author(self, name: str, limit: int = 10) -> List[EnrichedRecord]:
        """Search DBLP publications by author name."""
        self._polite_delay()

        params = {
            "q": name,
            "format": "json",
            "h": limit,
        }

        try:
            response = self.client.get(self.SEARCH_URL, params=params)
        except httpx.HTTPError as exc:
            logger.error("DBLP search_by_author request failed: %s", exc)
            return []

        hit_list = self._extract_hits(response)
        return [self._parse_record(hit) for hit in hit_list]
