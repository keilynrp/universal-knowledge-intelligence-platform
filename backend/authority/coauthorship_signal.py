"""Coauthorship overlap adapter (Phase 2, Task 7).

Computes a normalized Jaccard overlap between the query author's known
collaborators and a candidate's collaborators. The resolver feeds the result
into the scoring engine's coauthorship signal for ``person`` entities.

External authority resolvers do not return collaborator lists, so collaborator
sets are sourced from the **local coauthorship graph** (``Author`` +
``CoauthorEdge``): ``local_coauthor_names`` resolves an author by ``name_key``
and returns its graph neighbors. When an author is unknown or has no edges the
lookup yields ``[]``, ``compute_candidate_overlap`` returns ``None``, and the
scoring engine leaves the coauthorship weight at zero (safe no-op).
"""
from __future__ import annotations

import logging
from typing import Callable, Optional, Sequence

from backend.authority.normalize import normalize_name

logger = logging.getLogger(__name__)

# Cap collaborators pulled from the graph so a hyper-connected author cannot
# blow up the Jaccard set or the query cost.
_MAX_LOCAL_COAUTHORS = 200


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


def local_coauthor_names(
    db,
    name: str,
    org_id: int = 0,
    domain_id: Optional[str] = None,
    limit: int = _MAX_LOCAL_COAUTHORS,
) -> list[str]:
    """Return display names of ``name``'s collaborators from the local graph.

    Resolves the author by ``name_key`` (diacritic/format-insensitive), then
    traverses ``CoauthorEdge`` in both directions, scoped by org and (optional)
    domain, ordered by edge weight. Degrades to ``[]`` on any failure or when
    the author is unknown / has no edges, so scoring stays a safe no-op.
    """
    try:
        from backend import models
        from backend.coauthorship.identity import name_key

        key = name_key(name)
        if not key:
            return []
        author = (
            db.query(models.Author).filter(models.Author.name_key == key).first()
        )
        if author is None:
            return []

        q = db.query(models.CoauthorEdge).filter(
            (models.CoauthorEdge.author_a_id == author.id)
            | (models.CoauthorEdge.author_b_id == author.id)
        )
        if org_id is not None:
            q = q.filter(models.CoauthorEdge.org_id == org_id)
        if domain_id:
            q = q.filter(models.CoauthorEdge.domain_id == domain_id)
        edges = q.order_by(models.CoauthorEdge.weight.desc()).limit(limit).all()

        neighbor_ids = {
            edge.author_b_id if edge.author_a_id == author.id else edge.author_a_id
            for edge in edges
        }
        neighbor_ids.discard(author.id)
        if not neighbor_ids:
            return []

        rows = (
            db.query(models.Author.display_name)
            .filter(models.Author.id.in_(neighbor_ids))
            .all()
        )
        return [r[0] for r in rows if r[0]]
    except Exception as exc:  # defensive: scoring must never fail on this lookup
        logger.debug("local_coauthor_names failed for %r: %s", name, exc)
        return []


def make_local_coauthor_provider(
    db,
    org_id: int = 0,
    domain_id: Optional[str] = None,
) -> Callable[[str], list[str]]:
    """Return a ``name -> [collaborator names]`` lookup bound to a db session.

    Used by the resolver to fetch each candidate's collaborators from the local
    graph (keyed by the candidate's canonical label).
    """
    def _provider(name: str) -> list[str]:
        return local_coauthor_names(db, name, org_id=org_id, domain_id=domain_id)

    return _provider
