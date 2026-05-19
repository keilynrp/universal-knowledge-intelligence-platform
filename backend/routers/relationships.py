"""
Sprint 70 — Entity Relationship Graph
  GET  /entities/{id}/graph            — graph: nodes + edges up to depth N
  GET  /entities/{id}/relationships    — list direct relationships
  POST /entities/{id}/relationships    — create a new relationship
  DELETE /relationships/{rel_id}       — delete a relationship

Sprint 73 — Graph Analytics
  GET  /entities/{id}/graph/metrics    — degree, PageRank, component info
  GET  /graph/stats                    — global graph statistics
  GET  /graph/path                     — BFS shortest path
  GET  /graph/components               — list connected components
  GET  /graph/communities              — community summaries
"""
import logging
import json
from collections import defaultdict, deque
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend import graph_analytics, models, schemas
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.services.graph_materializer import materialize_scientific_import_graph
from backend.tenant_access import get_scoped_record, resolve_request_org_id, scope_query_to_org

logger = logging.getLogger(__name__)

router = APIRouter(tags=["relationships"])


def _get_entity_or_404(entity_id: int, db: Session, org_id: int | None) -> models.RawEntity:
    entity = get_scoped_record(db, models.RawEntity, entity_id, org_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    return entity


def _normalize_graph_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    value = domain.strip()
    if not value or value.lower() == "all":
        return None
    return value


def _filter_edges_by_domain(
    db: Session,
    edges: list[tuple[int, int, str, float]],
    org_id: int | None,
    domain: str | None,
) -> list[tuple[int, int, str, float]]:
    scoped_domain = _normalize_graph_domain(domain)
    if not scoped_domain or not edges:
        return edges

    node_ids: set[int] = set()
    for src, dst, _, _ in edges:
        node_ids.add(src)
        node_ids.add(dst)

    domain_node_ids = {
        row[0]
        for row in scope_query_to_org(db.query(models.RawEntity.id), models.RawEntity, org_id)
        .filter(models.RawEntity.id.in_(node_ids), models.RawEntity.domain == scoped_domain)
        .all()
    }
    return [(src, dst, rel, weight) for src, dst, rel, weight in edges if src in domain_node_ids and dst in domain_node_ids]


def _safe_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _concept_set(entity: models.RawEntity) -> set[str]:
    attrs = _safe_json(entity.attributes_json)
    values = [entity.enrichment_concepts, attrs.get("keywords"), attrs.get("concepts")]
    concepts: set[str] = set()
    for raw in values:
        if isinstance(raw, list):
            candidates = raw
        elif isinstance(raw, str):
            candidates = raw.replace("|", ",").replace(";", ",").split(",")
        else:
            candidates = []
        for candidate in candidates:
            value = str(candidate).strip().lower()
            if value:
                concepts.add(value)
    return concepts


@router.get("/graph/stats")
def get_graph_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Sprint 73 — Global graph statistics: nodes, edges, components, top PageRank."""
    org_id = resolve_request_org_id(db, current_user)
    edges = graph_analytics.fetch_edges(db, org_id=org_id)

    if not edges:
        return {
            "total_nodes": 0, "total_edges": 0,
            "total_components": 0, "largest_component_size": 0,
            "top_pagerank": [], "top_degree": [],
        }

    nodes: set[int] = set()
    for src, dst, _, _ in edges:
        nodes.add(src)
        nodes.add(dst)

    components = graph_analytics.connected_components(edges)
    sizes = graph_analytics.component_sizes(components)

    pr = graph_analytics.pagerank(edges)
    top_pr = sorted(pr.items(), key=lambda x: x[1], reverse=True)[:10]

    # Top by total degree
    degree_map: dict[int, int] = {}
    for node in nodes:
        d = graph_analytics.degree_centrality(node, edges)
        degree_map[node] = d["total_degree"]
    top_degree = sorted(degree_map.items(), key=lambda x: x[1], reverse=True)[:10]

    # Resolve labels for top nodes
    top_ids = {nid for nid, _ in top_pr + top_degree}
    label_map = {
        e.id: e.primary_label
        for e in scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
        .filter(models.RawEntity.id.in_(top_ids))
        .all()
    }

    return {
        "total_nodes":            len(nodes),
        "total_edges":            len(edges),
        "total_components":       len(sizes),
        "largest_component_size": max(sizes.values()) if sizes else 0,
        "top_pagerank": [
            {"entity_id": nid, "primary_label": label_map.get(nid), "score": score}
            for nid, score in top_pr
        ],
        "top_degree": [
            {"entity_id": nid, "primary_label": label_map.get(nid), "total_degree": deg}
            for nid, deg in top_degree
        ],
    }


@router.get("/graph/path")
def get_shortest_path(
    from_id: int = Query(..., ge=1),
    to_id:   int = Query(..., ge=1),
    domain: str | None = Query(default=None, min_length=1, max_length=80),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Sprint 73 — BFS shortest path between two entities (directed)."""
    org_id = resolve_request_org_id(db, current_user)
    if from_id == to_id:
        raise HTTPException(status_code=400, detail="from_id and to_id must be different")

    # Verify both entities exist
    for eid in (from_id, to_id):
        if not get_scoped_record(db, models.RawEntity, eid, org_id):
            raise HTTPException(status_code=404, detail=f"Entity {eid} not found")

    scoped_domain = _normalize_graph_domain(domain)
    edges = _filter_edges_by_domain(db, graph_analytics.fetch_edges(db, org_id=org_id), org_id, scoped_domain)
    result = graph_analytics.shortest_path(from_id, to_id, edges)

    if result is None:
        return {"found": False, "from_id": from_id, "to_id": to_id, "path": None}

    # Resolve labels
    path_ids = result["path"]
    label_map = {
        e.id: e.primary_label
        for e in scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
        .filter(models.RawEntity.id.in_(path_ids))
        .all()
    }
    steps = [
        {"entity_id": pid, "primary_label": label_map.get(pid)}
        for pid in path_ids
    ]

    return {
        "found":     True,
        "from_id":   from_id,
        "to_id":     to_id,
        "length":    result["length"],
        "relations": result["relations"],
        "steps":     steps,
    }


@router.get("/graph/components")
def get_graph_components(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Sprint 73 — List all weakly connected components with sizes and member IDs."""
    org_id = resolve_request_org_id(db, current_user)
    edges = graph_analytics.fetch_edges(db, org_id=org_id)

    if not edges:
        return {"total_components": 0, "components": []}

    node_to_comp = graph_analytics.connected_components(edges)
    sizes = graph_analytics.component_sizes(node_to_comp)

    # Group nodes by component
    comp_members: dict[int, list[int]] = defaultdict(list)
    for node_id, comp_id in node_to_comp.items():
        comp_members[comp_id].append(node_id)

    # Sort by size descending
    sorted_comps = sorted(sizes.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_components": len(sizes),
        "components": [
            {
                "component_id": comp_id,
                "size": size,
                "entity_ids": sorted(comp_members[comp_id]),
            }
            for comp_id, size in sorted_comps
        ],
    }


@router.get("/graph/communities")
def get_graph_communities(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return lightweight community-detection summaries over the current graph."""
    org_id = resolve_request_org_id(db, current_user)
    edges = graph_analytics.fetch_edges(db, org_id=org_id)

    if not edges:
        return {"total_communities": 0, "communities": []}

    communities = graph_analytics.detect_communities(edges)
    summaries = graph_analytics.community_summaries(edges, communities)[:limit]
    leader_ids = {summary["leader_id"] for summary in summaries}
    label_map = {
        entity.id: entity.primary_label
        for entity in scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
        .filter(models.RawEntity.id.in_(leader_ids))
        .all()
    }

    return {
        "total_communities": len({community_id for community_id in communities.values()}),
        "communities": [
            {
                **summary,
                "leader": {
                    "entity_id": summary["leader_id"],
                    "primary_label": label_map.get(summary["leader_id"]),
                    "total_degree": summary["leader_degree"],
                },
            }
            for summary in summaries
        ],
    }


@router.get("/graph/visualization")
def get_graph_visualization(
    limit: int = Query(default=500, ge=10, le=2000),
    import_batch_id: int | None = Query(default=None, ge=1),
    provider: str | None = Query(default=None, min_length=2, max_length=80),
    domain: str | None = Query(default=None, min_length=1, max_length=80),
    portal: str | None = Query(default=None, min_length=3, max_length=120),
    portal_slug: str | None = Query(default=None, min_length=3, max_length=120),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return nodes + edges for interactive graph visualization canvas."""
    org_id = resolve_request_org_id(db, current_user)
    portal_ref = portal_slug or portal
    scoped_import_batch_id = import_batch_id
    scoped_domain = _normalize_graph_domain(domain)

    if portal_ref:
        portal_record = (
            scope_query_to_org(db.query(models.CatalogPortal), models.CatalogPortal, org_id)
            .filter(models.CatalogPortal.slug == portal_ref)
            .first()
        )
        if not portal_record:
            raise HTTPException(status_code=404, detail="Catalog portal not found")
        scoped_import_batch_id = scoped_import_batch_id or portal_record.source_batch_id
        scoped_domain = scoped_domain or _normalize_graph_domain(portal_record.domain_id)

    filters_active = bool(scoped_import_batch_id or provider or scoped_domain)
    if not filters_active:
        edges_raw = graph_analytics.fetch_edges(db, org_id=org_id)
    else:
        entity_query = scope_query_to_org(db.query(models.RawEntity.id), models.RawEntity, org_id)
        if scoped_import_batch_id:
            entity_query = entity_query.filter(models.RawEntity.import_batch_id == scoped_import_batch_id)
        if scoped_domain:
            entity_query = entity_query.filter(models.RawEntity.domain == scoped_domain)
        if provider:
            provider_value = provider.strip().lower()
            batch_ids = [
                row[0]
                for row in scope_query_to_org(db.query(models.ImportBatch.id), models.ImportBatch, org_id)
                .filter(models.ImportBatch.source_type == f"science_upload:{provider_value}")
                .all()
            ]
            provider_filters = [
                models.RawEntity.enrichment_source == provider_value,
                models.RawEntity.attributes_json.contains(f'"provider": "{provider_value}"'),
            ]
            if batch_ids:
                provider_filters.append(models.RawEntity.import_batch_id.in_(batch_ids))
            entity_query = entity_query.filter(or_(*provider_filters))

        filtered_node_ids = {row[0] for row in entity_query.all()}
        if not filtered_node_ids:
            edges_raw = []
        else:
            edge_rows = (
                scope_query_to_org(
                    db.query(
                        models.EntityRelationship.source_id,
                        models.EntityRelationship.target_id,
                        models.EntityRelationship.relation_type,
                        models.EntityRelationship.weight,
                    ),
                    models.EntityRelationship,
                    org_id,
                )
                .filter(
                    models.EntityRelationship.source_id.in_(filtered_node_ids),
                    models.EntityRelationship.target_id.in_(filtered_node_ids),
                )
                .all()
            )
            edges_raw = [(r[0], r[1], r[2], r[3]) for r in edge_rows]

    empty = {
        "nodes": [], "links": [], "edge_types": [], "total_communities": 0,
        "filters": {
            "import_batch_id": scoped_import_batch_id,
            "provider": provider,
            "domain": scoped_domain,
            "portal": portal_ref,
        },
        "stats": {"visible_nodes": 0, "visible_edges": 0,
                  "top_pagerank_leader": None, "top_pagerank_score": 0.0},
    }
    if not edges_raw:
        return empty

    communities = graph_analytics.detect_communities(edges_raw)
    pr = graph_analytics.pagerank(edges_raw)

    degree_map: dict[int, int] = defaultdict(int)
    for src, dst, _, _ in edges_raw:
        degree_map[src] += 1
        degree_map[dst] += 1

    top_nodes = {nid for nid, _ in sorted(degree_map.items(), key=lambda x: x[1], reverse=True)[:limit]}
    filtered_edges = [(s, d, r, w) for s, d, r, w in edges_raw if s in top_nodes and d in top_nodes]

    label_map = {
        e.id: e.primary_label
        for e in scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
        .filter(models.RawEntity.id.in_(top_nodes))
        .all()
    }

    edge_types = sorted({r for _, _, r, _ in filtered_edges})

    pr_filtered = {nid: s for nid, s in pr.items() if nid in top_nodes}
    leader_id = max(pr_filtered, key=lambda x: pr_filtered[x]) if pr_filtered else None

    visible_communities = {communities.get(nid) for nid in top_nodes if communities.get(nid) is not None}

    return {
        "nodes": [
            {
                "id": nid,
                "label": label_map.get(nid) or f"#{nid}",
                "community": communities.get(nid, 0),
                "pagerank": round(pr.get(nid, 0.0), 4),
                "degree": degree_map[nid],
            }
            for nid in top_nodes
        ],
        "links": [{"source": s, "target": d, "type": r} for s, d, r, _ in filtered_edges],
        "edge_types": edge_types,
        "total_communities": len(visible_communities),
        "filters": {
            "import_batch_id": scoped_import_batch_id,
            "provider": provider,
            "domain": scoped_domain,
            "portal": portal_ref,
        },
        "stats": {
            "visible_nodes": len(top_nodes),
            "visible_edges": len(filtered_edges),
            "top_pagerank_leader": label_map.get(leader_id) if leader_id else None,
            "top_pagerank_score": round(pr_filtered[leader_id], 2) if leader_id else 0.0,
        },
    }


@router.post("/graph/materialize")
def materialize_graph(
    import_batch_id: int | None = Query(default=None, ge=1),
    entity_id: int | None = Query(default=None, ge=1),
    domain: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=25, ge=1, le=250),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Backfill graph relationships for previously ingested/enriched records."""
    org_id = resolve_request_org_id(db, current_user)
    scoped_domain = _normalize_graph_domain(domain)
    if entity_id:
        entity = _get_entity_or_404(entity_id, db, org_id)
        import_batch_id = import_batch_id or entity.import_batch_id
        scoped_domain = scoped_domain or _normalize_graph_domain(entity.domain)
        if not import_batch_id:
            return {
                "domain": scoped_domain,
                "entity_id": entity_id,
                "import_batch_id": None,
                "limit": limit,
                "totals": {"batches": 0, "publications": 0, "nodes_created": 0, "relationships_created": 0},
                "results": [],
                "diagnostic": "Entity has no import_batch_id, so automatic graph materialization cannot infer a batch.",
            }

    batch_query = scope_query_to_org(db.query(models.RawEntity.import_batch_id), models.RawEntity, org_id)
    batch_query = batch_query.filter(models.RawEntity.import_batch_id.isnot(None))
    if import_batch_id:
        batch_query = batch_query.filter(models.RawEntity.import_batch_id == import_batch_id)
    if scoped_domain:
        batch_query = batch_query.filter(models.RawEntity.domain == scoped_domain)

    batch_ids = [
        row[0]
        for row in batch_query.distinct().order_by(models.RawEntity.import_batch_id.asc()).limit(limit).all()
        if row[0] is not None
    ]
    results = []
    totals = {"batches": 0, "publications": 0, "nodes_created": 0, "relationships_created": 0}
    for batch_id in batch_ids:
        result = materialize_scientific_import_graph(db, batch_id, org_id=org_id)
        results.append({"import_batch_id": batch_id, **result})
        totals["batches"] += 1
        totals["publications"] += int(result.get("publications") or 0)
        totals["nodes_created"] += int(result.get("nodes_created") or 0)
        totals["relationships_created"] += int(result.get("relationships_created") or 0)

    return {
        "domain": scoped_domain,
        "entity_id": entity_id,
        "import_batch_id": import_batch_id,
        "limit": limit,
        "totals": totals,
        "results": results,
    }


@router.get("/entities/{entity_id}/graph/diagnostics")
def get_entity_graph_diagnostics(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Explain why an entity graph is empty and what action can populate it."""
    org_id = resolve_request_org_id(db, current_user)
    entity = _get_entity_or_404(entity_id, db, org_id)
    attrs = _safe_json(entity.attributes_json)
    relationship_count = (
        scope_query_to_org(db.query(models.EntityRelationship), models.EntityRelationship, org_id)
        .filter(
            (models.EntityRelationship.source_id == entity_id)
            | (models.EntityRelationship.target_id == entity_id)
        )
        .count()
    )
    concepts = _concept_set(entity)
    author_count = len(attrs.get("canonical_authors") or attrs.get("enrichment_authors") or [])
    has_identifier = bool(entity.enrichment_doi or entity.canonical_id)
    has_venue = bool(attrs.get("journal") or attrs.get("source_title") or attrs.get("venue"))
    can_materialize = bool(entity.import_batch_id and (concepts or author_count or has_identifier or has_venue))
    missing = []
    if not entity.import_batch_id:
        missing.append("import_batch_id")
    if not concepts:
        missing.append("concepts_or_keywords")
    if not author_count:
        missing.append("authors")
    if not has_identifier:
        missing.append("doi_or_identifier")
    if not has_venue:
        missing.append("venue_or_journal")

    if relationship_count > 0:
        status = "ready"
        action = "Explore direct and two-hop relationships."
    elif can_materialize:
        status = "materializable"
        action = "Run graph materialization for this record or its import batch."
    elif entity.enrichment_status != "completed":
        status = "needs_enrichment"
        action = "Run enrichment first so the graph can infer authors, concepts, DOI, or venue."
    else:
        status = "insufficient_metadata"
        action = "Add authors, concepts, DOI, venue, or create manual relationships."

    return {
        "entity_id": entity_id,
        "domain": entity.domain,
        "import_batch_id": entity.import_batch_id,
        "relationship_count": relationship_count,
        "status": status,
        "action": action,
        "can_materialize": can_materialize,
        "signals": {
            "concept_count": len(concepts),
            "author_count": author_count,
            "has_identifier": has_identifier,
            "has_venue": has_venue,
            "enrichment_status": entity.enrichment_status,
        },
        "missing": missing,
    }


@router.get("/entities/{entity_id}/relationships/suggestions")
def suggest_relationships(
    entity_id: int = Path(..., ge=1),
    limit: int = Query(default=8, ge=1, le=25),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Suggest concrete relationships from shared concepts, batch context, and derived graph nodes."""
    org_id = resolve_request_org_id(db, current_user)
    entity = _get_entity_or_404(entity_id, db, org_id)
    existing_ids = {
        row[0]
        for row in scope_query_to_org(
            db.query(models.EntityRelationship.target_id), models.EntityRelationship, org_id
        )
        .filter(models.EntityRelationship.source_id == entity_id)
        .all()
    } | {
        row[0]
        for row in scope_query_to_org(
            db.query(models.EntityRelationship.source_id), models.EntityRelationship, org_id
        )
        .filter(models.EntityRelationship.target_id == entity_id)
        .all()
    }
    source_concepts = _concept_set(entity)
    candidates_query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(models.RawEntity.id != entity_id)
    if entity.domain:
        candidates_query = candidates_query.filter(models.RawEntity.domain == entity.domain)
    if entity.import_batch_id:
        candidates_query = candidates_query.filter(models.RawEntity.import_batch_id == entity.import_batch_id)

    suggestions = []
    for candidate in candidates_query.order_by(models.RawEntity.id.asc()).limit(250).all():
        if candidate.id in existing_ids:
            continue
        attrs = _safe_json(candidate.attributes_json)
        candidate_concepts = _concept_set(candidate)
        shared = sorted(source_concepts & candidate_concepts)
        relation_type = "related-to"
        reason = ""
        weight = 0.6
        if attrs.get("derived") and candidate.entity_type == "author":
            relation_type = "authored-by"
            reason = "Author node derived from the same import batch."
            weight = 1.0
        elif attrs.get("derived") and candidate.entity_type == "journal":
            relation_type = "published-in"
            reason = "Publication venue derived from the same import batch."
            weight = 0.9
        elif attrs.get("derived") and candidate.entity_type == "concept":
            relation_type = "has-concept"
            reason = "Concept node derived from enrichment or ingest keywords."
            weight = 0.8
        elif shared:
            reason = f"Shared concepts: {', '.join(shared[:3])}"
            weight = min(1.0, 0.5 + len(shared) * 0.1)
        elif entity.import_batch_id and candidate.import_batch_id == entity.import_batch_id:
            reason = "Same import batch and domain."
            weight = 0.4
        else:
            continue
        suggestions.append({
            "target_id": candidate.id,
            "target_label": candidate.primary_label or f"Entity #{candidate.id}",
            "target_type": candidate.entity_type,
            "relation_type": relation_type,
            "weight": round(weight, 2),
            "reason": reason,
        })
        if len(suggestions) >= limit:
            break
    return {"entity_id": entity_id, "suggestions": suggestions}


@router.get("/entities/{entity_id}/graph/metrics")
def get_entity_graph_metrics(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Sprint 73 — Return graph analytics metrics for a single entity:
    degree centrality, PageRank score, connected component info.
    """
    org_id = resolve_request_org_id(db, current_user)
    entity = get_scoped_record(db, models.RawEntity, entity_id, org_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    edges = graph_analytics.fetch_edges(db, org_id=org_id)

    # Degree
    degree = graph_analytics.degree_centrality(entity_id, edges)

    # PageRank
    pr = graph_analytics.pagerank(edges)
    pr_score = pr.get(entity_id, 0.0)
    # Rank position
    sorted_pr = sorted(pr.items(), key=lambda x: x[1], reverse=True)
    pr_rank = next((i + 1 for i, (nid, _) in enumerate(sorted_pr) if nid == entity_id), None)

    # Components
    components = graph_analytics.connected_components(edges)
    sizes = graph_analytics.component_sizes(components)
    comp_id = components.get(entity_id)
    comp_size = sizes.get(comp_id, 0) if comp_id is not None else 0

    return {
        "entity_id":       entity_id,
        "primary_label":   entity.primary_label,
        "degree":          degree,
        "pagerank": {
            "score":        round(pr_score, 6),
            "rank":         pr_rank,
            "total_nodes":  len(pr),
        },
        "component": {
            "component_id": comp_id,
            "size":         comp_size,
        },
    }


@router.get("/entities/{entity_id}/graph", response_model=schemas.EntityGraphResponse)
def get_entity_graph(
    entity_id: int = Path(..., ge=1),
    depth: int = Query(default=1, ge=1, le=2),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Return a subgraph centered on entity_id.
    depth=1 → direct neighbors only.
    depth=2 → neighbors + their neighbors (capped at 50 nodes total).
    """
    org_id = resolve_request_org_id(db, current_user)
    _get_entity_or_404(entity_id, db, org_id)

    visited_ids = set()
    queue = deque([(entity_id, 0)])
    collected_edges: List[models.EntityRelationship] = []
    NODE_CAP = 50

    while queue and len(visited_ids) < NODE_CAP:
        current_id, current_depth = queue.popleft()
        if current_id in visited_ids:
            continue
        visited_ids.add(current_id)

        if current_depth >= depth:
            continue

        # Edges where this node is source or target
        rels = (
            scope_query_to_org(db.query(models.EntityRelationship), models.EntityRelationship, org_id)
            .filter(
                (models.EntityRelationship.source_id == current_id)
                | (models.EntityRelationship.target_id == current_id)
            )
            .all()
        )
        for rel in rels:
            collected_edges.append(rel)
            neighbor = rel.target_id if rel.source_id == current_id else rel.source_id
            if neighbor not in visited_ids and len(visited_ids) < NODE_CAP:
                queue.append((neighbor, current_depth + 1))

    # Deduplicate edges
    seen_edge_ids = set()
    unique_edges = []
    for e in collected_edges:
        if e.id not in seen_edge_ids:
            seen_edge_ids.add(e.id)
            unique_edges.append(e)

    # Only include edges where BOTH endpoints are in visited_ids
    final_edges = [
        e for e in unique_edges
        if e.source_id in visited_ids and e.target_id in visited_ids
    ]

    # Fetch node data
    entities = (
        scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
        .filter(models.RawEntity.id.in_(visited_ids))
        .all()
    )
    entity_map = {e.id: e for e in entities}

    nodes = [
        schemas.GraphNode(
            id=eid,
            label=entity_map[eid].primary_label or f"Entity #{eid}" if eid in entity_map else f"Entity #{eid}",
            entity_type=entity_map[eid].entity_type if eid in entity_map else None,
            domain=entity_map[eid].domain if eid in entity_map else None,
            is_center=(eid == entity_id),
        )
        for eid in visited_ids
    ]

    edges = [
        schemas.GraphEdge(
            id=e.id,
            source=e.source_id,
            target=e.target_id,
            relation_type=e.relation_type,
            weight=e.weight,
        )
        for e in final_edges
    ]

    return schemas.EntityGraphResponse(
        center_id=entity_id,
        depth=depth,
        nodes=nodes,
        edges=edges,
    )


@router.get("/entities/{entity_id}/relationships", response_model=List[schemas.EntityRelationshipResponse])
def list_relationships(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all relationships where this entity is source or target."""
    org_id = resolve_request_org_id(db, current_user)
    _get_entity_or_404(entity_id, db, org_id)
    return (
        scope_query_to_org(db.query(models.EntityRelationship), models.EntityRelationship, org_id)
        .filter(
            (models.EntityRelationship.source_id == entity_id)
            | (models.EntityRelationship.target_id == entity_id)
        )
        .order_by(models.EntityRelationship.created_at.desc())
        .all()
    )


@router.post("/entities/{entity_id}/relationships", response_model=schemas.EntityRelationshipResponse, status_code=201)
def create_relationship(
    payload: schemas.EntityRelationshipCreate,
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Create a directed relationship from entity_id → target_id."""
    org_id = resolve_request_org_id(db, current_user)
    source = _get_entity_or_404(entity_id, db, org_id)
    _get_entity_or_404(payload.target_id, db, org_id)

    if entity_id == payload.target_id:
        raise HTTPException(status_code=400, detail="Self-referential relationships are not allowed.")

    # Prevent duplicate directed edge of same type
    existing = (
        scope_query_to_org(db.query(models.EntityRelationship), models.EntityRelationship, org_id)
        .filter(
            models.EntityRelationship.source_id == entity_id,
            models.EntityRelationship.target_id == payload.target_id,
            models.EntityRelationship.relation_type == payload.relation_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="This relationship already exists.")

    rel = models.EntityRelationship(
        org_id=source.org_id,
        source_id=entity_id,
        target_id=payload.target_id,
        relation_type=payload.relation_type,
        weight=payload.weight,
        notes=payload.notes,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


@router.delete("/relationships/{rel_id}", status_code=204)
def delete_relationship(
    rel_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Delete a relationship by ID."""
    org_id = resolve_request_org_id(db, current_user)
    rel = get_scoped_record(db, models.EntityRelationship, rel_id, org_id)
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    db.delete(rel)
    db.commit()
