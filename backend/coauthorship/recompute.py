"""Materialize author_stats for a (org_id, domain_id) scope.

Uses python-louvain for graphs >= 50 nodes; connected components otherwise.
Writes are idempotent: the scope's stats are fully rewritten on each call, and
the matching coauthor_dirty_scopes marker is cleared.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import community.community_louvain as community_louvain
import networkx as nx
from sqlalchemy import delete, func

from backend import models

logger = logging.getLogger(__name__)

# Below this node count, connected components are sufficient (and cheaper).
_LOUVAIN_MIN_NODES = 50
# Above these bounds, pure-Python python-louvain is too slow to run inside the
# worker loop (≈15s at 100k edges; ≈18s at 10k nodes). We fall back to
# connected components so a pathological scope can never stall recompute. When
# scopes routinely exceed this, swap in a C-backed detector (igraph/leidenalg).
_LOUVAIN_MAX_NODES = 3000
_LOUVAIN_MAX_EDGES = 25_000
_LOUVAIN_SEED = 42  # deterministic community assignment


def _should_use_louvain(n_nodes: int, n_edges: int) -> bool:
    return (
        _LOUVAIN_MIN_NODES <= n_nodes <= _LOUVAIN_MAX_NODES
        and n_edges <= _LOUVAIN_MAX_EDGES
    )


def _connected_components(graph: nx.Graph) -> dict[int, int]:
    out: dict[int, int] = {}
    for cid, comp in enumerate(nx.connected_components(graph)):
        for node in comp:
            out[node] = cid
    return out


def _clear_dirty_scope(db, org_id: int, domain_id: str) -> None:
    db.execute(
        delete(models.CoauthorDirtyScope).where(
            models.CoauthorDirtyScope.org_id == org_id,
            models.CoauthorDirtyScope.domain_id == domain_id,
        )
    )


def recompute_coauthor_stats(db, *, org_id: int, domain_id: str) -> dict:
    """Rebuild author_stats for one scope from its coauthor_edges.

    Deterministic: Louvain runs with a fixed seed. Caller-agnostic — commits
    its own unit of work (the dispatcher hands one scope at a time).
    """
    t0 = datetime.now(timezone.utc)
    edges = (
        db.query(models.CoauthorEdge)
        .filter_by(org_id=org_id, domain_id=domain_id)
        .all()
    )

    # Full rewrite: wipe this scope's prior stats first.
    db.execute(
        delete(models.AuthorStats).where(
            models.AuthorStats.org_id == org_id,
            models.AuthorStats.domain_id == domain_id,
        )
    )

    if not edges:
        _clear_dirty_scope(db, org_id, domain_id)
        db.commit()
        return {"nodes": 0, "edges": 0, "communities": 0, "wall_time_ms": 0}

    graph = nx.Graph()
    for e in edges:
        graph.add_edge(e.author_a_id, e.author_b_id, weight=e.weight)

    n_nodes = graph.number_of_nodes()
    n_edges = graph.number_of_edges()
    if _should_use_louvain(n_nodes, n_edges):
        communities = community_louvain.best_partition(
            graph, weight="weight", random_state=_LOUVAIN_SEED
        )
    else:
        if n_nodes > _LOUVAIN_MAX_NODES or n_edges > _LOUVAIN_MAX_EDGES:
            logger.warning(
                "scope=(%s,%s) exceeds Louvain cap (nodes=%d edges=%d); "
                "using connected-components fallback to avoid stalling the worker",
                org_id, domain_id, n_nodes, n_edges,
            )
        communities = _connected_components(graph)

    centrality = nx.degree_centrality(graph)
    degree = dict(graph.degree())

    pub_counts = dict(
        db.query(
            models.AuthorPublication.author_id,
            func.count(models.AuthorPublication.entity_id),
        )
        .filter_by(org_id=org_id, domain_id=domain_id)
        .group_by(models.AuthorPublication.author_id)
        .all()
    )

    db.bulk_save_objects([
        models.AuthorStats(
            author_id=node,
            org_id=org_id,
            domain_id=domain_id,
            degree=int(degree.get(node, 0)),
            centrality=float(centrality.get(node, 0.0)),
            community_id=int(communities.get(node, 0)),
            publication_count=int(pub_counts.get(node, 0)),
            computed_at=t0,
        )
        for node in graph.nodes()
    ])

    _clear_dirty_scope(db, org_id, domain_id)
    db.commit()

    elapsed_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    n_comms = len(set(communities.values()))
    logger.info(
        "recompute_coauthor_stats scope=(%s,%s) nodes=%d edges=%d communities=%d wall_ms=%d",
        org_id, domain_id, n_nodes, len(edges), n_comms, elapsed_ms,
    )
    return {
        "nodes": n_nodes,
        "edges": len(edges),
        "communities": n_comms,
        "wall_time_ms": elapsed_ms,
    }
