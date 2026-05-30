"""
Authority Resolution Orchestrator.

Steps:
  1. Call all 5 resolvers in parallel (ThreadPoolExecutor).
  2. Apply weighted scoring engine (identifiers + name + affiliation signals).
  3. Deduplicate candidates across sources that refer to the same entity.
  4. Return top-20 candidates ranked by confidence descending.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from thefuzz import fuzz

from backend.authority.base import AuthorityCandidate, ResolveContext
from backend.authority.cache import get_resolver_cache
from backend.authority.normalize import normalize_name
from backend.authority.resilience import ResilientResolver
from backend.circuit_breaker import CircuitBreaker
from backend.authority.coauthorship_signal import candidate_coauthors, compute_candidate_overlap
from backend.authority.scoring import compute_score
from backend.authority.resolvers.wikidata import WikidataResolver
from backend.authority.resolvers.viaf     import ViafResolver
from backend.authority.resolvers.orcid    import OrcidResolver
from backend.authority.resolvers.dbpedia  import DbpediaResolver
from backend.authority.resolvers.openalex import OpenAlexEntityResolver

logger = logging.getLogger(__name__)

_RESOLVERS = [
    WikidataResolver(),
    ViafResolver(),
    OrcidResolver(),
    DbpediaResolver(),
    OpenAlexEntityResolver(),
]

# Wrap each source in a circuit breaker + bounded retry. One breaker per source,
# shared across all resolve_all calls so failures accumulate process-wide.
_BREAKERS = {
    r.source_name: CircuitBreaker(r.source_name, failure_threshold=3, recovery_timeout=60.0)
    for r in _RESOLVERS
}
_RESILIENT = [ResilientResolver(r, _BREAKERS[r.source_name]) for r in _RESOLVERS]

_MAX_RESULTS      = 20
_PARALLEL_TIMEOUT = 12   # seconds to wait for all futures
_DEDUP_THRESHOLD  = 92   # token_sort_ratio threshold for same-entity merging

# Source priority for picking the "winner" when merging duplicates
_SOURCE_PRIORITY = {"orcid": 5, "openalex": 4, "viaf": 3, "wikidata": 2, "dbpedia": 1}


def _deduplicate(candidates: List[AuthorityCandidate]) -> List[AuthorityCandidate]:
    """
    Merge candidates from different sources that refer to the same entity.

    Two candidates are considered duplicates when the token_sort_ratio of their
    normalised canonical labels is >= _DEDUP_THRESHOLD.  The candidate from the
    higher-quality source wins; merged sources are recorded in merged_sources.
    """
    if len(candidates) <= 1:
        return candidates

    used = [False] * len(candidates)
    merged: List[AuthorityCandidate] = []

    for i, c in enumerate(candidates):
        if used[i]:
            continue
        group = [c]
        used[i] = True
        for j in range(i + 1, len(candidates)):
            if used[j]:
                continue
            sim = fuzz.token_sort_ratio(
                normalize_name(c.canonical_label),
                normalize_name(candidates[j].canonical_label),
            )
            if sim >= _DEDUP_THRESHOLD:
                group.append(candidates[j])
                used[j] = True

        if len(group) == 1:
            merged.append(c)
            continue

        # Pick the highest-quality source as the representative
        best = max(group, key=lambda x: _SOURCE_PRIORITY.get(x.authority_source, 0))
        other_refs = [
            f"{x.authority_source}:{x.authority_id}"
            for x in group
            if x is not best
        ]
        best.merged_sources = other_refs
        merged.append(best)

    return merged


async def resolve_all_via_engine(
    value: str,
    entity_type: str,
    context: Optional[ResolveContext] = None,
    engine_client=None,
) -> Optional[List[AuthorityCandidate]]:
    """
    Try delegating authority resolution to the Rust engine.

    Returns resolved candidates on success, or None to signal fallback.
    """
    if engine_client is None:
        return None
    try:
        resp = await engine_client.process_authority(
            field_name="author",
            values=[value],
            entity_type=entity_type,
            context_affiliation=context.affiliation if context else None,
            context_orcid_hint=context.orcid_hint if context else None,
            context_doi=context.doi if context else None,
            context_year=context.year if context else None,
        )
        if resp is None:
            return None

        # Convert proto response to AuthorityCandidate list
        result: List[AuthorityCandidate] = []
        if hasattr(resp, "authority_result") and resp.authority_result.groups:
            for group in resp.authority_result.groups:
                for c in group.candidates:
                    result.append(AuthorityCandidate(
                        authority_source=c.source,
                        authority_id=c.authority_id,
                        canonical_label=c.canonical_label,
                        confidence=c.confidence,
                        score_breakdown=dict(c.score_breakdown),
                        resolution_status=c.resolution_status,
                        merged_sources=list(c.merged_sources),
                        aliases=list(c.aliases),
                        description=c.description if c.HasField("description") else None,
                        uri=c.uri if c.HasField("uri") else None,
                    ))
        return result if result else None
    except Exception as exc:
        logger.warning("Engine authority delegation failed, falling back to Python: %s", exc)
        return None


def resolve_all(
    value: str,
    entity_type: str,
    context: Optional[ResolveContext] = None,
) -> List[AuthorityCandidate]:
    """
    Query all authority sources in parallel for the given value.

    Applies the weighted scoring engine (identifiers + name + affiliation)
    and deduplicates candidates that refer to the same entity across sources.
    Returns at most _MAX_RESULTS candidates sorted by confidence descending.
    """
    if context is None:
        context = ResolveContext()

    raw: List[AuthorityCandidate] = []

    cache = get_resolver_cache()
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(
                cache.get_or_load,
                resolver.source_name,
                value,
                entity_type,
                lambda r=resolver: r.resolve(value, entity_type),
            ): resolver.source_name
            for resolver in _RESILIENT
        }
        for future in as_completed(futures, timeout=_PARALLEL_TIMEOUT):
            source = futures[future]
            try:
                raw.extend(future.result())
            except Exception as exc:
                logger.warning("Authority resolver '%s' timed out or failed: %s", source, exc)

    # Apply weighted scoring engine
    use_coauth = entity_type == "person" and bool(context.coauthors)
    for c in raw:
        coauthors_overlap = None
        if use_coauth:
            # Prefer the local-graph provider (keyed by canonical label); fall
            # back to any collaborators a resolver attached to the candidate.
            if context.candidate_coauthor_provider is not None:
                cand_collaborators = context.candidate_coauthor_provider(c.canonical_label)
            else:
                cand_collaborators = candidate_coauthors(c)
            coauthors_overlap = compute_candidate_overlap(
                context.coauthors, cand_collaborators
            )
        source_prior = 0.0
        if context.source_priors:
            source_prior = context.source_priors.get(c.authority_source, 0.0)
        score, breakdown, evidence, resolution_status = compute_score(
            value=value,
            authority_source=c.authority_source,
            authority_id=c.authority_id,
            canonical_label=c.canonical_label,
            description=c.description,
            orcid_hint=context.orcid_hint,
            affiliation=context.affiliation,
            coauthors_overlap=coauthors_overlap,
            source_prior=source_prior,
            thresholds=context.thresholds,
        )
        c.confidence        = score
        c.score_breakdown   = breakdown
        c.evidence          = evidence
        c.resolution_status = resolution_status

    # Deduplicate cross-source
    deduped = _deduplicate(raw)

    deduped.sort(key=lambda c: c.confidence, reverse=True)
    return deduped[:_MAX_RESULTS]
