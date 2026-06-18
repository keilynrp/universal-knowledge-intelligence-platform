from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class CanonicalAffiliation(BaseModel):
    """Structured institution affiliation normalized from scientific providers."""
    name: str = Field(description="Institution or organization display name")
    ror: Optional[str] = Field(default=None, description="ROR identifier or URL")
    openalex_id: Optional[str] = Field(default=None, description="OpenAlex institution ID")
    country_code: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2 country code")
    type: Optional[str] = Field(default=None, description="Provider institution type")
    lineage: List[str] = Field(default_factory=list, description="Provider lineage IDs")


class AuthorAffiliation(BaseModel):
    """Author-to-institution affiliation relationship from a scientific provider."""
    author_name: str = Field(description="Author display name")
    author_orcid: Optional[str] = Field(default=None, description="Normalized ORCID when available")
    author_openalex_id: Optional[str] = Field(default=None, description="OpenAlex author ID")
    author_position: Optional[str] = Field(default=None, description="Provider author position")
    author_order: Optional[int] = Field(default=None, description="Raw authorship order, 1-based")
    institutions: List[CanonicalAffiliation] = Field(default_factory=list)


class JournalMetrics(BaseModel):
    """Journal/source-level metrics resolved during enrichment."""
    issn_l: Optional[str] = Field(default=None, description="Linking ISSN")
    source_id: Optional[str] = Field(default=None, description="OpenAlex source ID")
    display_name: Optional[str] = Field(default=None, description="Journal name")
    two_yr_mean_citedness: Optional[float] = Field(default=None, description="Open IF proxy (OpenAlex 2yr mean citedness)")
    h_index: Optional[int] = Field(default=None, description="Source h-index")
    apc_usd: Optional[int] = Field(default=None, description="Article Processing Charge in USD")
    apc_currency: Optional[str] = Field(default=None, description="APC currency when from DOAJ")
    apc_source: Optional[str] = Field(default=None, description="'openalex' | 'doaj'")
    is_in_doaj: Optional[bool] = Field(default=None, description="Indexed in DOAJ")
    nif_field: Optional[str] = Field(default=None, description="OpenAlex primary subfield — normalization bucket for the NIF")
    normalized_impact_factor: Optional[float] = Field(default=None, description="Field-normalized IF (filled by batch)")


class EnrichedRecord(BaseModel):
    """
    Normalized Data Object (NDO) for scientometric/bibliometric enrichment.
    Unifies the terminology between different APIs (Scopus, WoS, OpenAlex, etc).
    """
    id: str = Field(description="Internal or Source ID", default="unknown")
    doi: Optional[str] = Field(description="Digital Object Identifier. Best unique key.", default=None)
    title: str = Field(description="Title of the publication or artifact", default="Untitled")
    authors: List[str] = Field(default_factory=list, description="List of author names (normalized)")
    author_orcids: List[Optional[str]] = Field(default_factory=list, description="ORCID for each author (positional, None if unavailable)")
    citation_count: int = Field(default=0, description="Cumulative number of citations")
    publication_year: Optional[int] = Field(default=None, description="Year of publication")
    concepts: List[str] = Field(default_factory=list, description="Extracted keywords, subjects or concepts")
    concept_ids: List[Optional[str]] = Field(default_factory=list, description="OpenAlex concept IDs (positional, None for topics/keywords)")
    publisher: Optional[str] = Field(default=None, description="Journal, Conference, or Publisher name")
    affiliations: List[str] = Field(default_factory=list, description="Institutional or geographic affiliations")
    canonical_affiliations: List[CanonicalAffiliation] = Field(default_factory=list, description="Deduplicated structured institution affiliations")
    author_affiliations: List[AuthorAffiliation] = Field(default_factory=list, description="Per-author structured affiliation relationships")
    is_open_access: bool = Field(default=False, description="Whether the artifact is OA (Open Access)")
    source_api: str = Field(description="Which API provided this data (e.g., 'OpenAlex', 'Scopus')", default="Unknown")
    raw_response: Optional[Dict[str, Any]] = Field(default=None, description="Snapshot of the original JSON for audit and fallback extraction")
    # Extended fields from scientific connectors
    funding: Optional[List[str]] = Field(default=None, description="Funding sources / grant IDs")
    references_count: Optional[int] = Field(default=None, description="Number of references cited")
    tldr: Optional[str] = Field(default=None, description="Auto-generated TL;DR summary (Semantic Scholar)")
    influential_citation_count: Optional[int] = Field(default=None, description="Citations from influential papers (Semantic Scholar)")
    license: Optional[str] = Field(default=None, description="License URL or identifier")
    mesh_terms: Optional[List[str]] = Field(default=None, description="MeSH descriptors (PubMed)")
    venue: Optional[str] = Field(default=None, description="Publication venue (journal/conference name)")
    journal: Optional[JournalMetrics] = Field(default=None, description="Resolved journal-level metrics")
