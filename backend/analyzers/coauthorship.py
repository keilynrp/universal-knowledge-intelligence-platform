"""
Co-authorship Network analyzer — build and analyze co-authorship graphs
from EntityRelationship edges of type CO_AUTHOR.

Includes: degree centrality, community detection (connected components +
greedy modularity).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations
from typing import Any

from sqlalchemy import or_
from sqlalchemy import text

from backend.analyzers.topic_modeling import _validate_domain
from backend.database import engine
from backend.tenant_access import add_org_sql_filter

logger = logging.getLogger(__name__)

MAX_AUTHORS_FOR_COAUTH = 15


def _coauthor_pairs(authors: list[str]) -> list[tuple[str, str]]:
    """Return canonical coauthor pairs for a publication author list."""
    clean_authors = list(dict.fromkeys(a.strip() for a in authors if a and a.strip()))
    if len(clean_authors) < 2:
        return []

    if len(clean_authors) > MAX_AUTHORS_FOR_COAUTH:
        pairs = [(clean_authors[0], a) for a in clean_authors[1:]]
    else:
        pairs = list(combinations(clean_authors, 2))

    return [(min(a, b), max(a, b)) for a, b in pairs if a != b]


def extract_coauthor_edges(
    entity_id: int,
    authors: list[str],
    db_session,
    org_id: int | None = None,
) -> int:
    """
    Generate CO_AUTHOR edges for a multi-author entity.
    Returns number of edges created/updated.
    """
    from backend import models

    pairs = _coauthor_pairs(authors)
    if not pairs:
        return 0

    source = db_session.get(models.RawEntity, entity_id)
    source_domain = getattr(source, "domain", None)
    notes = [f"{a}||{b}" for a, b in pairs]

    existing_query = (
        db_session.query(models.EntityRelationship)
        .join(models.RawEntity, models.RawEntity.id == models.EntityRelationship.source_id)
        .filter(
            models.EntityRelationship.relation_type == "CO_AUTHOR",
            models.EntityRelationship.notes.in_(notes),
        )
    )
    if org_id is None:
        existing_query = existing_query.filter(models.EntityRelationship.org_id.is_(None))
    else:
        existing_query = existing_query.filter(models.EntityRelationship.org_id == org_id)
    if source_domain in (None, "default"):
        existing_query = existing_query.filter(
            or_(models.RawEntity.domain == "default", models.RawEntity.domain.is_(None))
        )
    else:
        existing_query = existing_query.filter(models.RawEntity.domain == source_domain)

    existing_by_note = {row.notes: row for row in existing_query.all()}

    for a, b in pairs:
        note = f"{a}||{b}"
        existing = existing_by_note.get(note)
        if existing:
            existing.weight = (existing.weight or 1.0) + 1.0
        else:
            db_session.add(models.EntityRelationship(
                source_id=entity_id,
                target_id=entity_id,  # self-ref placeholder; real IDs would need author entity lookup
                relation_type="CO_AUTHOR",
                weight=1.0,
                notes=note,
                org_id=org_id,
            ))

    return len(pairs)


def _load_coauthor_edges(
    domain_id: str, org_id: int | None = None,
) -> list[dict[str, Any]]:
    """Load all CO_AUTHOR edges for a domain."""
    where_clauses = ["er.relation_type = 'CO_AUTHOR'"]
    params: dict[str, object] = {}

    if domain_id not in ("all",):
        if domain_id == "default":
            where_clauses.append("(re.domain = :domain_id OR re.domain IS NULL)")
        else:
            where_clauses.append("re.domain = :domain_id")
        params["domain_id"] = domain_id
    add_org_sql_filter(where_clauses, params, org_id, column_name="er.org_id")

    sql = f"""
        SELECT er.id, er.notes, er.weight
        FROM entity_relationships er
        JOIN raw_entities re ON re.id = er.source_id
        WHERE {' AND '.join(where_clauses)}
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return [dict(row._mapping) for row in rows]


def compute_degree_centrality(adj: dict[str, set[str]]) -> dict[str, float]:
    """Compute degree centrality for each node: degree / (N-1)."""
    n = len(adj)
    if n <= 1:
        return {node: 0.0 for node in adj}
    return {
        node: round(len(neighbors) / (n - 1), 4)
        for node, neighbors in adj.items()
    }


def detect_communities(adj: dict[str, set[str]]) -> dict[str, int]:
    """
    Detect communities using connected components.
    Each connected component gets a distinct community_id.
    """
    visited: set[str] = set()
    communities: dict[str, int] = {}
    community_id = 0

    for node in adj:
        if node in visited:
            continue
        # BFS to find connected component
        queue = [node]
        component: list[str] = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)

        for n in component:
            communities[n] = community_id
        community_id += 1

    return communities


def coauthorship_network(
    domain_id: str,
    *,
    min_weight: int = 1,
    limit: int | None = None,
    org_id: int | None = None,
) -> dict[str, Any]:
    """Build co-authorship network with centrality and community detection."""
    _validate_domain(domain_id, org_id=org_id)

    edges_raw = _load_coauthor_edges(domain_id, org_id=org_id)

    # Parse edges from notes field (format: "Author A||Author B")
    edge_weights: dict[tuple[str, str], float] = defaultdict(float)
    for row in edges_raw:
        notes = row.get("notes", "")
        if "||" not in notes:
            continue
        parts = notes.split("||", 1)
        a, b = parts[0].strip(), parts[1].strip()
        if not a or not b:
            continue
        key = (min(a, b), max(a, b))
        edge_weights[key] += row.get("weight", 1.0)

    # Filter by min_weight
    filtered_edges = {k: w for k, w in edge_weights.items() if w >= min_weight}

    # Build adjacency list
    adj: dict[str, set[str]] = defaultdict(set)
    for (a, b) in filtered_edges:
        adj[a].add(b)
        adj[b].add(a)

    if not adj:
        return {
            "domain_id": domain_id,
            "nodes": [],
            "edges": [],
        }

    # Compute metrics
    centrality = compute_degree_centrality(dict(adj))
    communities = detect_communities(dict(adj))

    # Count publications per author (from edge count)
    pub_counts: dict[str, int] = defaultdict(int)
    for (a, b), w in filtered_edges.items():
        pub_counts[a] += int(w)
        pub_counts[b] += int(w)

    # Build node list
    nodes = [
        {
            "id": author,
            "label": author,
            "degree": len(adj[author]),
            "centrality": centrality.get(author, 0.0),
            "community_id": communities.get(author, 0),
            "total_publications": pub_counts.get(author, 0),
        }
        for author in adj
    ]

    # Sort by degree centrality descending
    nodes.sort(key=lambda n: n["centrality"], reverse=True)

    # Apply limit
    if limit is not None:
        top_authors = {n["id"] for n in nodes[:limit]}
        nodes = nodes[:limit]
        # Only keep edges between top authors
        filtered_edges = {
            k: w for k, w in filtered_edges.items()
            if k[0] in top_authors and k[1] in top_authors
        }

    # Build edge list
    edges = [
        {
            "source": a,
            "target": b,
            "weight": w,
        }
        for (a, b), w in sorted(filtered_edges.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "domain_id": domain_id,
        "nodes": nodes,
        "edges": edges,
    }
