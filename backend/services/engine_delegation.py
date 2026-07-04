"""Shared delegation helpers for routing compute to the Rust engine."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Awaitable, TypeVar

logger = logging.getLogger(__name__)

ENGINE_DELEGATION_THRESHOLD = int(os.environ.get("ENGINE_DELEGATION_THRESHOLD", "100"))
MAX_DELEGATION_VALUES = 50_000

_T = TypeVar("_T")


def _get_engine_client(request) -> Any | None:
    """Extract the EngineClient from request.app.state, or return None."""
    return getattr(request.app.state, "engine_client", None)


def run_coro_sync(coro: Awaitable[_T]) -> _T | None:
    """Run an async coroutine to completion from a *sync* context.

    FastAPI runs sync endpoints in a worker thread with no running event loop,
    so ``asyncio.run`` is safe here and avoids the deprecated
    ``asyncio.get_event_loop()`` bridge. If a loop is already running in this
    thread (unexpected) or the coroutine raises, we swallow the failure and
    return ``None`` so callers cleanly fall back to their Python path.
    """
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        # e.g. "asyncio.run() cannot be called from a running event loop"
        logger.debug("run_coro_sync skipped (running loop): %s", exc)
        return None
    except Exception as exc:
        logger.warning("run_coro_sync failed: %s", exc)
        return None


# ── Analytics ────────────────────────────────────────────────────────────────

async def try_engine_analytics(
    client,
    domain_id: str,
    mode: str,
    top_n: int = 30,
    org_id: int | None = None,
) -> dict | None:
    """
    Delegate analytics to the engine.  Returns converted dict or None on failure.
    """
    if client is None:
        return None
    try:
        resp = await client.process_analytics(
            domain_id=domain_id,
            mode=mode,
            limit=top_n,
        )
        if resp is None:
            return None
        return _convert_analytics(resp, mode)
    except Exception as exc:
        logger.warning("Engine analytics delegation failed, falling back to Python: %s", exc)
        return None


def _convert_analytics(resp, mode: str) -> dict | None:
    ar = getattr(resp, "analytics_result", None)
    if ar is None:
        return None
    if mode == "topics":
        return _convert_topics(ar)
    if mode == "cooccurrence":
        return _convert_cooccurrence(ar)
    if mode == "clusters":
        return _convert_clusters(ar)
    if mode == "correlation":
        return _convert_correlation(ar)
    return None


def _convert_topics(ar) -> dict:
    total_enriched = getattr(ar, "total_enriched", 0)
    topics = [{"concept": t.concept, "count": t.count, "pct": 0.0} for t in ar.topics]
    if total_enriched > 0:
        for t in topics:
            t["pct"] = round(t["count"] / total_enriched * 100, 2)
    return {
        "domain_id": getattr(ar, "domain_id", ""),
        "total_enriched": total_enriched,
        "topics": topics,
    }


def _convert_cooccurrence(ar) -> dict:
    return {
        "domain_id": getattr(ar, "domain_id", ""),
        "total_enriched": getattr(ar, "total_enriched", 0),
        "pairs": [
            {"concept_a": p.concept_a, "concept_b": p.concept_b, "count": getattr(p, "count", 0), "pmi": round(p.pmi, 4)}
            for p in ar.cooccurrences
        ],
    }


def _convert_clusters(ar) -> dict:
    clusters = [
        {
            "id": i,
            "seed": c.seed_concept,
            "size": len(c.members),
            "members": [{"concept": m, "count": 0} for m in c.members],
        }
        for i, c in enumerate(ar.clusters)
    ]
    return {
        "domain_id": getattr(ar, "domain_id", ""),
        "n_clusters": len(clusters),
        "clusters": clusters,
    }


def _convert_correlation(ar) -> dict:
    return {
        "domain_id": getattr(ar, "domain_id", ""),
        "n_entities": getattr(ar, "n_entities", 0),
        "fields_analyzed": getattr(ar, "fields_analyzed", 0),
        "correlations": [
            {
                "field_a": c.field_a,
                "field_b": c.field_b,
                "cramers_v": round(c.cramers_v, 4),
                "strength": c.strength,
            }
            for c in ar.correlations
        ],
    }


# ── Disambiguation ───────────────────────────────────────────────────────────

async def try_engine_disambiguation(
    client,
    field_name: str,
    values: list[str],
    threshold: int = 80,
    similarity_threshold: float = 0.85,
) -> list[dict] | None:
    """
    Delegate disambiguation to the engine.
    Returns list of group dicts or None on failure.
    """
    if client is None:
        return None
    if len(values) > MAX_DELEGATION_VALUES:
        logger.warning(
            "Disambiguation values truncated from %d to %d",
            len(values), MAX_DELEGATION_VALUES,
        )
        values = values[:MAX_DELEGATION_VALUES]
    try:
        resp = await client.process_disambiguation(
            field_name=field_name,
            values=values,
            similarity_threshold=similarity_threshold / 100 if similarity_threshold > 1 else similarity_threshold,
        )
        if resp is None:
            return None
        dr = getattr(resp, "disambiguation_result", None)
        if dr is None:
            return None
        return [
            {
                "canonical": c.canonical_value,
                "variations": list(c.variants),
                "count": c.frequency,
            }
            for c in dr.clusters
        ]
    except Exception as exc:
        logger.warning("Engine disambiguation delegation failed, falling back to Python: %s", exc)
        return None


# ── Normalization ────────────────────────────────────────────────────────────

async def try_engine_normalization(
    client,
    field_name: str,
    values: list[str],
    mode: str = "rules",
    rules: list[dict] | None = None,
) -> dict[str, str] | None:
    """
    Delegate normalization to the engine.
    Returns {original: normalized} mapping or None on failure.
    """
    if client is None:
        return None
    if len(values) > MAX_DELEGATION_VALUES:
        logger.warning(
            "Normalization values truncated from %d to %d",
            len(values), MAX_DELEGATION_VALUES,
        )
        values = values[:MAX_DELEGATION_VALUES]
    try:
        resp = await client.process_normalization(
            values=values,
            mode=mode,
            rules=rules,
        )
        if resp is None:
            return None
        nr = getattr(resp, "normalization_result", None)
        if nr is None:
            return None
        # Build mapping: input values → normalized values (positional)
        mapping = {}
        normalized = list(nr.normalized_values)
        for i, original in enumerate(values):
            if i < len(normalized) and normalized[i] != original:
                mapping[original] = normalized[i]
        return mapping
    except Exception as exc:
        logger.warning("Engine normalization delegation failed, falling back to Python: %s", exc)
        return None


# ── Connectors ───────────────────────────────────────────────────────────────

async def try_engine_connectors(
    client,
    source: str,
    query_type: str,
    queries: list[str],
    limit: int = 10,
) -> list[dict] | None:
    """
    Delegate scientific connector fetch to the engine.
    Returns list of publication dicts or None on failure.
    """
    if client is None:
        return None
    try:
        resp = await client.process_connectors(
            source=source,
            query_type=query_type,
            queries=queries,
            limit=limit,
        )
        if resp is None:
            return None
        cr = getattr(resp, "connector_result", None)
        if cr is None:
            return None
        return [_convert_publication(p) for p in cr.publications]
    except Exception as exc:
        logger.warning("Engine connectors delegation failed, falling back to Python: %s", exc)
        return None


def _convert_publication(pub) -> dict:
    """Convert a proto Publication to the Python dict format."""
    authors = []
    for a in pub.authors:
        authors.append(a.display_name if hasattr(a, "display_name") else str(a))
    return {
        "title": pub.title,
        "doi": pub.doi if pub.doi else None,
        "year": pub.year if pub.year else None,
        "authors": authors,
        "abstract": pub.abstract_text if pub.abstract_text else None,
        "source": pub.enrichment_source if pub.enrichment_source else None,
        "journal": pub.source_title if pub.source_title else None,
        "citations": pub.citation_count if pub.citation_count else 0,
    }
