"""
PubMedAdapter — bulk collection from PubMed via NCBI E-utilities.

Flow:
  1. eSearch  → retrieve up to `limit` PMIDs (max 500 per call)
  2. eFetch   → fetch MEDLINE XML in batches of 100
  3. Parse    → extract fields into EnrichedRecord

Rate limits (NCBI policy):
  - Without API key: 3 req/s  → 1/3 s sleep between requests
  - With NCBI_API_KEY env var: 10 req/s → 1/10 s sleep

No third-party library (Biopython, pymed) required.
"""
from __future__ import annotations

import logging
import os
import time
import xml.etree.ElementTree as ET
from typing import List, Optional

import requests

from backend.schemas_enrichment import EnrichedRecord
from backend.adapters.enrichment.base import BaseScientometricAdapter

logger = logging.getLogger(__name__)

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_FETCH_BATCH = 100
_MAX_LIMIT = 500


class PubMedAdapter(BaseScientometricAdapter):
    """Queries PubMed via NCBI E-utilities (eSearch + eFetch)."""

    def __init__(self) -> None:
        self._api_key: Optional[str] = os.environ.get("NCBI_API_KEY") or None
        # Polite rate: 3 req/s without key, 10 req/s with key
        self._delay = 1 / 10 if self._api_key else 1 / 3

    @property
    def is_active(self) -> bool:
        return True

    def _base_params(self) -> dict:
        params: dict = {"retmode": "xml"}
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    # ------------------------------------------------------------------
    # eSearch: get list of PMIDs
    # ------------------------------------------------------------------

    def _esearch(self, query: str, limit: int) -> List[str]:
        params = {
            **self._base_params(),
            "db": "pubmed",
            "term": query,
            "retmax": limit,
        }
        try:
            resp = requests.get(_ESEARCH_URL, params=params, timeout=15)
            time.sleep(self._delay)
        except Exception as exc:
            logger.warning("PubMed eSearch error: %s", exc)
            return []

        if resp.status_code != 200:
            logger.warning("PubMed eSearch returned HTTP %s", resp.status_code)
            return []

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            logger.warning("PubMed eSearch XML parse error: %s", exc)
            return []

        return [el.text for el in root.findall(".//IdList/Id") if el.text]

    # ------------------------------------------------------------------
    # eFetch: fetch MEDLINE XML for a batch of PMIDs
    # ------------------------------------------------------------------

    def _efetch(self, pmids: List[str]) -> str:
        params = {
            **self._base_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "medline",
        }
        try:
            resp = requests.get(_EFETCH_URL, params=params, timeout=30)
            time.sleep(self._delay)
        except Exception as exc:
            logger.warning("PubMed eFetch error: %s", exc)
            return ""

        if resp.status_code != 200:
            logger.warning("PubMed eFetch returned HTTP %s", resp.status_code)
            return ""

        return resp.text

    # ------------------------------------------------------------------
    # XML parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _text(element: Optional[ET.Element], path: str) -> Optional[str]:
        """Safe text extraction; returns None if element or path missing."""
        if element is None:
            return None
        node = element.find(path)
        return node.text if node is not None and node.text else None

    def _parse_article(self, article_el: ET.Element) -> Optional[EnrichedRecord]:
        """Parse a <PubmedArticle> element into an EnrichedRecord."""
        try:
            medline = article_el.find("MedlineCitation")
            if medline is None:
                return None

            pmid_el = medline.find("PMID")
            pmid = pmid_el.text if pmid_el is not None else "unknown"

            art = medline.find("Article")
            if art is None:
                return None

            title = self._text(art, "ArticleTitle") or "Untitled"
            abstract = self._text(art, "Abstract/AbstractText") or ""

            # Authors
            authors: List[str] = []
            for author_el in art.findall("AuthorList/Author"):
                last = self._text(author_el, "LastName") or ""
                fore = self._text(author_el, "ForeName") or ""
                name = f"{last} {fore}".strip()
                if name:
                    authors.append(name)

            # Year
            year_str = self._text(art, "Journal/JournalIssue/PubDate/Year")
            year: Optional[int] = int(year_str) if year_str and year_str.isdigit() else None

            # Affiliation (first one)
            affil_el = art.find(".//AffiliationInfo/Affiliation")
            affiliation = affil_el.text if affil_el is not None else None

            # Journal / Venue
            venue = self._text(art, "Journal/Title")

            # DOI from ArticleIdList
            doi: Optional[str] = None
            pubmed_data = article_el.find("PubmedData")
            if pubmed_data is not None:
                for aid in pubmed_data.findall("ArticleIdList/ArticleId"):
                    if aid.get("IdType") == "doi" and aid.text:
                        doi = aid.text
                        break

            # MeSH terms
            mesh_terms: List[str] = []
            mesh_list = medline.find("MeshHeadingList")
            if mesh_list is not None:
                for heading in mesh_list.findall("MeshHeading"):
                    descriptor = heading.find("DescriptorName")
                    if descriptor is not None and descriptor.text:
                        mesh_terms.append(descriptor.text)

            return EnrichedRecord(
                id=f"pmid:{pmid}",
                doi=doi,
                title=title,
                authors=authors,
                citation_count=0,  # PubMed doesn't provide citation counts
                publication_year=year,
                concepts=[],
                publisher=affiliation,
                is_open_access=False,
                source_api="PubMed",
                mesh_terms=mesh_terms if mesh_terms else None,
                venue=venue,
            )
        except Exception as exc:
            logger.debug("Skipping malformed PubMed record: %s", exc)
            return None

    def _parse_xml(self, xml_text: str) -> List[EnrichedRecord]:
        if not xml_text or xml_text.strip() == "<PubmedArticleSet/>":
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("PubMed eFetch XML parse error: %s", exc)
            return []

        records: List[EnrichedRecord] = []
        for article_el in root.findall("PubmedArticle"):
            rec = self._parse_article(article_el)
            if rec is not None:
                records.append(rec)
        return records

    # ------------------------------------------------------------------
    # BaseScientometricAdapter ABC methods
    # ------------------------------------------------------------------

    def search_by_doi(self, doi: str) -> Optional[EnrichedRecord]:
        """Search PubMed by DOI using a field-qualified query."""
        pmids = self._esearch(f"{doi}[DOI]", limit=1)
        if not pmids:
            return None
        xml_text = self._efetch(pmids)
        records = self._parse_xml(xml_text)
        return records[0] if records else None

    def search_by_title(self, title: str, limit: int = 5) -> List[EnrichedRecord]:
        """Search PubMed by title (wraps search_bulk)."""
        return self.search_bulk(f"{title}[Title]", limit=limit)

    def search_by_author(self, name: str, limit: int = 10) -> List[EnrichedRecord]:
        """Search PubMed by author name using a field-qualified query."""
        return self.search_bulk(f"{name}[Author]", limit=limit)

    # ------------------------------------------------------------------
    # Original bulk API (kept for backward compatibility)
    # ------------------------------------------------------------------

    def search_bulk(self, query: str, limit: int = 100) -> List[EnrichedRecord]:
        """
        Fetch up to `limit` records from PubMed for `query`.
        Caps at 500 records regardless of the requested limit.
        """
        limit = min(limit, _MAX_LIMIT)

        pmids = self._esearch(query, limit)
        if not pmids:
            return []

        records: List[EnrichedRecord] = []
        for i in range(0, len(pmids), _FETCH_BATCH):
            batch = pmids[i : i + _FETCH_BATCH]
            xml_text = self._efetch(batch)
            records.extend(self._parse_xml(xml_text))

        return records[:limit]
