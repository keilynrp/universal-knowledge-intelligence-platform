import urllib.parse
from typing import List, Optional
import httpx # Installed earlier
import re

from backend.schemas_enrichment import EnrichedRecord
from backend.adapters.enrichment.base import BaseScientometricAdapter

class OpenAlexAdapter(BaseScientometricAdapter):
    """
    Adapter for OpenAlex API. Free, enormous, and highly interconnected.
    Good practice: Includes an etiquette email `mailto:` param to use the fast lane.
    Rate Limit: 100,000 reqs/day, heavily throttled on loops unless polite.
    """
    
    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, polite_email: Optional[str] = "research@ukip.dev"):
        self.client = httpx.Client(timeout=10.0)
        self.polite_email = polite_email

    def _build_params(self, custom_params: dict) -> dict:
        params = custom_params.copy()
        if self.polite_email:
            params["mailto"] = self.polite_email
        return params

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
        for authorship in raw_openalex.get("authorships", []):
            author_data = authorship.get("author", {})
            name = author_data.get("display_name")
            if name:
                author_list.append(name)
        
        # 4. Extract concepts from concepts, topics, and keywords fields
        concept_list = []
        seen_concepts: set[str] = set()
        for concept in raw_openalex.get("concepts", []):
            concept_name = concept.get("display_name")
            if concept_name and concept.get("score", 0) >= 0.4:
                key = concept_name.lower()
                if key not in seen_concepts:
                    seen_concepts.add(key)
                    concept_list.append(concept_name)
        for topic in raw_openalex.get("topics", []):
            topic_name = topic.get("display_name")
            if topic_name and topic.get("score", 0) >= 0.4:
                key = topic_name.lower()
                if key not in seen_concepts:
                    seen_concepts.add(key)
                    concept_list.append(topic_name)
        for kw in raw_openalex.get("keywords", []):
            kw_name = kw.get("display_name") if isinstance(kw, dict) else (kw if isinstance(kw, str) else None)
            if kw_name:
                key = kw_name.lower()
                if key not in seen_concepts:
                    seen_concepts.add(key)
                    concept_list.append(kw_name)

        # 5. Get publisher / venue
        publisher = None
        host_venue = raw_openalex.get("primary_location", {})
        if host_venue:
            source = host_venue.get("source", {})
            if source:
                 publisher = source.get("display_name")

        return EnrichedRecord(
            id=id_str,
            doi=clean_doi,
            title=title,
            authors=author_list,
            citation_count=cited_count,
            publication_year=pub_year,
            publisher=publisher,
            is_open_access=oa_status,
            concepts=concept_list,
            source_api="OpenAlex",
            raw_response=raw_openalex # Attach whole tree for potential late parsing rules
        )

    def search_by_doi(self, doi: str) -> Optional[EnrichedRecord]:
        """
        OpenAlex supports direct lookup by appending the DOI to the base URL or filtering.
        """
        # OpenAlex expects https://doi.org/10.xyz format inside the API paths sometimes
        # We enforce searching with `filter=doi:xxxxx` to be safe against URL encoding weirdness
        params = self._build_params({"filter": f"doi:{doi}"})
        response = self.client.get(self.BASE_URL, params=params)
        
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
