from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

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
    publisher: Optional[str] = Field(default=None, description="Journal, Conference, or Publisher name")
    is_open_access: bool = Field(default=False, description="Whether the artifact is OA (Open Access)")
    source_api: str = Field(description="Which API provided this data (e.g., 'OpenAlex', 'Scopus')", default="Unknown")
    raw_response: Optional[Dict[str, Any]] = Field(default=None, description="Snapshot of the original JSON for audit and fallback extraction")
