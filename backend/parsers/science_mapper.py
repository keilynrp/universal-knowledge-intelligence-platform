"""
Maps parsed BibTeX/RIS records to RawEntity kwargs for the science domain.

primary_label  = title
canonical_id   = DOI (cleaned)
secondary_label = first author
entity_type    = publication type (journal_article, book, etc.)
domain         = "science"
enrichment_concepts = keywords (comma-separated)
attributes_json = all remaining science-specific fields
"""
import json
from typing import Any

from backend.services.text_normalization import normalize_import_value


def _clean_doi(doi: str | None) -> str | None:
    """Normalize DOI — strip URL prefix if present."""
    if not doi:
        return None
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
    return doi or None


def _first_author(authors: str | None) -> str | None:
    """Extract the first author name from a semicolon- or 'and'-separated list."""
    if not authors:
        return None
    # Split on semicolons or "and"
    parts = [p.strip() for p in authors.replace(" and ", ";").split(";") if p.strip()]
    return parts[0] if parts else None


def science_record_to_entity(record: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a parsed BibTeX/RIS record dict to a RawEntity kwargs dict.
    Always sets domain='science'.
    """
    record = normalize_import_value(record)
    title   = record.get("title") or ""
    doi     = _clean_doi(record.get("doi"))
    authors = record.get("authors")
    year    = record.get("year")
    journal = record.get("journal")
    abstract = record.get("abstract")
    keywords = record.get("keywords")
    etype   = record.get("entity_type", "publication")
    citation_count = record.get("citation_count")

    # Build attributes_json with all science-specific fields
    attrs: dict[str, Any] = {}
    for field in (
        "authors", "editors", "journal", "year", "volume", "issue",
        "start_page", "end_page", "pages", "publisher", "doi", "url",
        "issn", "isbn", "language", "institution", "note", "address",
        "_cite_key", "_entry_type", "_ris_type", "_plaintext_type",
        "abstract", "citation_count", "reference_count", "document_type",
        "full_authors", "corresponding_author", "researcher_ids", "orcids",
        "funding", "open_access", "retrieved_at", "eissn", "pubmed_id",
        "_source_name", "_source_version",
        "raw_fn", "raw_vr", "raw_pt", "raw_au", "raw_af", "raw_ti", "raw_so",
        "raw_la", "raw_dt", "raw_c1", "raw_c3", "raw_rp", "raw_ri", "raw_oi",
        "raw_fu", "raw_ct", "raw_nr", "raw_pu", "raw_sn", "raw_ei", "raw_pd",
        "raw_py", "raw_vl", "raw_is", "raw_bp", "raw_ep", "raw_di", "raw_pg",
        "raw_pm", "raw_oa", "raw_da",
    ):
        val = record.get(field)
        if val is not None:
            attrs[field] = val

    # Keywords → enrichment_concepts (comma-separated)
    concepts = None
    if keywords:
        # Normalize: keywords may be semicolon or comma separated
        concepts = ", ".join(
            k.strip() for k in keywords.replace(";", ",").split(",") if k.strip()
        )

    return {
        "domain":               "science",
        "primary_label":        title or None,
        "canonical_id":         doi,
        "secondary_label":      _first_author(authors),
        "entity_type":          etype,
        "enrichment_citation_count": int(citation_count) if citation_count not in (None, "") else None,
        "enrichment_concepts":  concepts,
        "attributes_json":      json.dumps(attrs, ensure_ascii=False) if attrs else None,
    }
