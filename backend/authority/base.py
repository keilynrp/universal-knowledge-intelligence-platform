"""
Base classes and shared data structures for the Authority Resolution Layer.
Each external authority source implements BaseAuthorityResolver.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dc_field
from typing import Dict, List, Optional


@dataclass
class ResolveContext:
    """
    Optional contextual signals attached to a resolve request.
    Used by the scoring engine to compute affiliation and identifier signals.
    """
    affiliation:  Optional[str] = None   # e.g. "Universidad de Buenos Aires"
    orcid_hint:   Optional[str] = None   # e.g. "0000-0001-XXXX-XXXX" if known
    doi:          Optional[str] = None   # e.g. "10.1038/..."
    year:         Optional[int] = None   # publication year for temporal context
    coauthors:    Optional[List[str]] = None  # known collaborators of the query author (persons)


@dataclass
class AuthorityCandidate:
    """A single candidate returned by an authority resolver."""
    authority_source:  str
    authority_id:      str
    canonical_label:   str
    aliases:           List[str]         = dc_field(default_factory=list)
    description:       Optional[str]     = None
    confidence:        float             = 0.0        # filled by orchestrator
    uri:               Optional[str]     = None
    # Sprint 16 — scoring engine fields
    score_breakdown:   Dict[str, float]  = dc_field(default_factory=dict)
    evidence:          List[str]         = dc_field(default_factory=list)
    resolution_status: str               = "unresolved"
    merged_sources:    List[str]         = dc_field(default_factory=list)
    hierarchy_distance: Optional[int]    = None


class BaseAuthorityResolver(ABC):
    """Abstract base for all authority resolvers."""

    source_name: str
    timeout: int = 8  # seconds per HTTP request

    @abstractmethod
    def resolve(self, value: str, entity_type: str) -> List[AuthorityCandidate]:
        """
        Query the external authority and return raw candidates.
        Confidence and scoring are computed later by the orchestrator.
        Must never raise — catch and log internally, return [] on failure.
        """
        ...
