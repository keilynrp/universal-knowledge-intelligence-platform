"""Coauthorship overlap adapter (Phase 2, Task 7).

Computes a normalized Jaccard overlap between the query author's known
collaborators and a candidate's collaborators. The resolver feeds the result
into the scoring engine's coauthorship signal for ``person`` entities.

External authority resolvers do not yet return collaborator lists, so
``candidate_coauthors`` is a best-effort extractor that degrades to an empty
list — in which case ``compute_candidate_overlap`` returns ``None`` and the
scoring engine leaves the coauthorship weight at zero (safe no-op).
"""
from __future__ import annotations

from typing import Optional, Sequence

from backend.authority.normalize import normalize_name


def _norm_set(names: Sequence[str] | None) -> set[str]:
    if not names:
        return set()
    return {normalize_name(n) for n in names if n and str(n).strip()}


def jaccard_overlap(a: Sequence[str] | None, b: Sequence[str] | None) -> float:
    """Normalized Jaccard similarity of two collaborator name sets (0–1)."""
    sa, sb = _norm_set(a), _norm_set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def candidate_coauthors(candidate) -> list[str]:
    """Best-effort extraction of a candidate's collaborators.

    External resolvers do not currently expose collaborator lists; if a future
    resolver attaches a ``coauthors`` attribute we honor it, otherwise return [].
    """
    raw = getattr(candidate, "coauthors", None)
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw]
    return []


def compute_candidate_overlap(
    query_coauthors: Sequence[str] | None,
    candidate_collaborators: Sequence[str] | None,
) -> Optional[float]:
    """Return the overlap, or ``None`` when either side has no collaborators.

    ``None`` signals "no coauthorship evidence available" so the scoring engine
    skips the signal rather than penalizing the candidate with a 0.0.
    """
    if not query_coauthors or not candidate_collaborators:
        return None
    return jaccard_overlap(query_coauthors, candidate_collaborators)
