import time
import urllib.parse
from typing import List, Optional

import httpx

from backend.schemas_enrichment import EnrichedRecord
from backend.adapters.enrichment.base import BaseScientometricAdapter


class CrossrefAdapter(BaseScientometricAdapter):
    """
    Adapter for the Crossref REST API. Free, no API key required.
    Uses the polite pool (mailto param) for faster, more reliable access.
    Rate etiquette: 100ms delay between requests.
    """

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, polite_email: Optional[str] = "research@ukip.dev"):
        self.client = httpx.Client(timeout=15.0)
        self.polite_email = polite_email

    @property
    def is_active(self) -> bool:
        """Crossref is always active — no API key required."""
        return True

    def _build_params(self, custom_params: dict) -> dict:
        params = custom_params.copy()
        if self.polite_email:
            params["mailto"] = self.polite_email
        return params

    def _parse_record(self, raw: dict) -> EnrichedRecord:
        """
        Maps a single Crossref work item JSON to the normalized EnrichedRecord.
        """
        doi = raw.get("DOI")

        # Title
        titles = raw.get("title", [])
        title = titles[0] if titles else "Untitled"

        # Authors
        author_list = []
        for author in raw.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            full_name = f"{given} {family}".strip()
            if full_name:
                author_list.append(full_name)

        # Citation count
        citation_count = raw.get("is-referenced-by-count", 0)

        # Publication year: prefer published-print, fall back to published-online
        publication_year = None
        for date_field in ("published-print", "published-online"):
            date_parts = raw.get(date_field, {}).get("date-parts", [[]])
            if date_parts and date_parts[0] and date_parts[0][0]:
                publication_year = date_parts[0][0]
                break

        # Publisher
        publisher = raw.get("publisher")

        # Open Access detection: check if any license entry is
        # content-version "vor" with a Creative Commons URL
        is_open_access = False
        for lic in raw.get("license", []):
            content_version = lic.get("content-version", "")
            url = lic.get("URL", "")
            if content_version == "vor" and "creativecommons" in url.lower():
                is_open_access = True
                break

        # Concepts from subject array
        concepts = raw.get("subject", [])

        # Extended fields
        funding = None
        funders = raw.get("funder", [])
        if funders:
            funding = [f.get("name") for f in funders if f.get("name")]
            if not funding:
                funding = None

        references_count = raw.get("references-count")

        license_url = None
        licenses = raw.get("license", [])
        if licenses:
            license_url = licenses[0].get("URL")

        container_titles = raw.get("container-title", [])
        venue = container_titles[0] if container_titles else None

        return EnrichedRecord(
            id=doi or "unknown",
            doi=doi,
            title=title,
            authors=author_list,
            citation_count=citation_count,
            publication_year=publication_year,
            publisher=publisher,
            is_open_access=is_open_access,
            concepts=concepts,
            source_api="Crossref",
            raw_response=raw,
            funding=funding,
            references_count=references_count,
            license=license_url,
            venue=venue,
        )

    def search_by_doi(self, doi: str) -> Optional[EnrichedRecord]:
        """
        Exact DOI lookup via https://api.crossref.org/works/{doi}.
        Returns None on 404.
        Raises on 429/5xx for circuit breaker.
        """
        encoded_doi = urllib.parse.quote(doi, safe="")
        url = f"{self.BASE_URL}/{encoded_doi}"
        params = self._build_params({})

        response = self.client.get(url, params=params)
        time.sleep(0.1)

        if response.status_code == 404:
            return None
        if response.status_code == 429 or response.status_code >= 500:
            response.raise_for_status()
        if response.status_code != 200:
            return None

        message = response.json().get("message", {})
        if not message:
            return None

        return self._parse_record(message)

    def search_by_title(self, title: str, limit: int = 5) -> List[EnrichedRecord]:
        """
        Bibliographic title search via query.bibliographic parameter.
        """
        params = self._build_params({
            "query.bibliographic": title,
            "rows": limit,
        })

        response = self.client.get(self.BASE_URL, params=params)
        time.sleep(0.1)

        if response.status_code == 429 or response.status_code >= 500:
            response.raise_for_status()
        if response.status_code != 200:
            return []

        items = response.json().get("message", {}).get("items", [])
        return [self._parse_record(item) for item in items]

    def search_by_author(self, name: str, limit: int = 10) -> List[EnrichedRecord]:
        """
        Author name search via query.author parameter.
        """
        params = self._build_params({
            "query.author": name,
            "rows": limit,
        })

        response = self.client.get(self.BASE_URL, params=params)
        time.sleep(0.1)

        if response.status_code == 429 or response.status_code >= 500:
            response.raise_for_status()
        if response.status_code != 200:
            return []

        items = response.json().get("message", {}).get("items", [])
        return [self._parse_record(item) for item in items]
