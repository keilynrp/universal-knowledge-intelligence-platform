"""
Sprint 75 — Knowledge Graph Export
  GET /export/graph?format=graphml|cytoscape|jsonld&domain=<id>

Exports the full entity-relationship graph (or a domain-scoped subgraph) to
standard interchange formats for external analysis tools:
  - GraphML  → Gephi, yEd, igraph
  - Cytoscape JSON  → Cytoscape.js, Cytoscape Desktop
  - JSON-LD  → semantic-web toolchains, knowledge graph platforms
"""
import io
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user
from backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["graph-export"])

# ── Valid formats ─────────────────────────────────────────────────────────────

_FORMAT = Literal["graphml", "cytoscape", "jsonld"]

_CONTENT_TYPES = {
    "graphml":  "application/xml",
    "cytoscape": "application/json",
    "jsonld":   "application/ld+json",
}

_EXTENSIONS = {
    "graphml":  "graphml",
    "cytoscape": "json",
    "jsonld":   "jsonld",
}

# ── JSON-LD relation URI map ───────────────────────────────────────────────────

_REL_TYPE_URIS = {
    "cites":       "https://schema.org/citation",
    "authored-by": "https://schema.org/author",
    "belongs-to":  "https://schema.org/memberOf",
    "related-to":  "https://schema.org/isRelatedTo",
}

# ── Data fetcher ──────────────────────────────────────────────────────────────

def _fetch_graph(db: Session, domain: Optional[str]):
    """
    Return (entities_dict, edges_list).
    If domain is given, include only entities in that domain and edges
    where both endpoints belong to it.
    """
    all_edges = db.query(models.EntityRelationship).all()
    if not all_edges:
        return {}, []

    node_ids: set[int] = set()
    for e in all_edges:
        node_ids.add(e.source_id)
        node_ids.add(e.target_id)

    scoped_domain = domain.strip() if domain else None
    if scoped_domain and scoped_domain.lower() == "all":
        scoped_domain = None

    q = db.query(models.RawEntity).filter(models.RawEntity.id.in_(node_ids))
    if scoped_domain:
        q = q.filter(models.RawEntity.domain == scoped_domain)
    entities: dict[int, models.RawEntity] = {e.id: e for e in q.all()}

    edges = [
        e for e in all_edges
        if e.source_id in entities and e.target_id in entities
    ]
    return entities, edges


# ── GraphML serializer ────────────────────────────────────────────────────────

_GRAPHML_NS = "http://graphml.graphdrawing.org/graphml"

_NODE_KEYS = [
    ("label",         "label",         "string"),
    ("entity_type",   "entity_type",   "string"),
    ("domain",        "domain",        "string"),
    ("quality_score", "quality_score", "double"),
]

_EDGE_KEYS = [
    ("relation_type", "relation_type", "string"),
    ("weight",        "weight",        "double"),
]


def _to_graphml(entities: dict, edges: list) -> bytes:
    ET.register_namespace("", _GRAPHML_NS)
    root = ET.Element(f"{{{_GRAPHML_NS}}}graphml")

    # Key declarations
    for key_id, attr_name, attr_type in _NODE_KEYS:
        ET.SubElement(root, f"{{{_GRAPHML_NS}}}key", {
            "id": key_id, "for": "node",
            "attr.name": attr_name, "attr.type": attr_type,
        })
    for key_id, attr_name, attr_type in _EDGE_KEYS:
        ET.SubElement(root, f"{{{_GRAPHML_NS}}}key", {
            "id": key_id, "for": "edge",
            "attr.name": attr_name, "attr.type": attr_type,
        })

    graph_el = ET.SubElement(root, f"{{{_GRAPHML_NS}}}graph", {
        "id": "G", "edgedefault": "directed",
    })

    for eid, entity in entities.items():
        node_el = ET.SubElement(graph_el, f"{{{_GRAPHML_NS}}}node", {"id": str(eid)})
        for key_id, field in [
            ("label",         entity.primary_label),
            ("entity_type",   entity.entity_type),
            ("domain",        entity.domain),
            ("quality_score", entity.quality_score),
        ]:
            if field is not None:
                d = ET.SubElement(node_el, f"{{{_GRAPHML_NS}}}data", {"key": key_id})
                d.text = str(field)

    for edge in edges:
        edge_el = ET.SubElement(graph_el, f"{{{_GRAPHML_NS}}}edge", {
            "id":     f"e{edge.id}",
            "source": str(edge.source_id),
            "target": str(edge.target_id),
        })
        d_rel = ET.SubElement(edge_el, f"{{{_GRAPHML_NS}}}data", {"key": "relation_type"})
        d_rel.text = edge.relation_type
        d_w = ET.SubElement(edge_el, f"{{{_GRAPHML_NS}}}data", {"key": "weight"})
        d_w.text = str(edge.weight)

    buf = io.BytesIO()
    tree = ET.ElementTree(root)
    tree.write(buf, xml_declaration=True, encoding="utf-8")
    return buf.getvalue()


# ── Cytoscape JSON serializer ─────────────────────────────────────────────────

def _to_cytoscape(entities: dict, edges: list, generated_at: str) -> bytes:
    nodes = [
        {
            "data": {
                "id":           str(eid),
                "label":        e.primary_label or "",
                "entity_type":  e.entity_type or "",
                "domain":       e.domain or "default",
                "quality_score": e.quality_score,
            }
        }
        for eid, e in entities.items()
    ]
    edge_list = [
        {
            "data": {
                "id":            f"e{edge.id}",
                "source":        str(edge.source_id),
                "target":        str(edge.target_id),
                "relation_type": edge.relation_type,
                "weight":        edge.weight,
            }
        }
        for edge in edges
    ]
    payload = {
        "elements": {"nodes": nodes, "edges": edge_list},
        "meta": {
            "format":       "cytoscape",
            "node_count":   len(nodes),
            "edge_count":   len(edge_list),
            "generated_at": generated_at,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


# ── JSON-LD serializer ────────────────────────────────────────────────────────

def _to_jsonld(entities: dict, edges: list, generated_at: str) -> bytes:
    # Group outgoing edges per source entity
    out_edges: dict[int, list] = {eid: [] for eid in entities}
    for edge in edges:
        out_edges[edge.source_id].append(edge)

    context = {
        "@vocab":      "https://schema.org/",
        "ukip":        "https://ukip.example.org/vocab#",
        "entity_type": "ukip:entityType",
        "domain":      "ukip:domain",
        "quality_score": "ukip:qualityScore",
        "weight":      "ukip:weight",
    }
    # Add relation-type shortcuts
    for rel, uri in _REL_TYPE_URIS.items():
        context[rel] = {"@id": uri, "@type": "@id"}

    graph_nodes = []
    for eid, entity in entities.items():
        node: dict = {
            "@id":   f"ukip:entity/{eid}",
            "@type": "schema:Thing",
            "name":  entity.primary_label or "",
        }
        if entity.entity_type:
            node["entity_type"] = entity.entity_type
        if entity.domain:
            node["domain"] = entity.domain
        if entity.quality_score is not None:
            node["quality_score"] = entity.quality_score

        # Group outgoing relations by type
        rel_groups: dict[str, list[str]] = {}
        for edge in out_edges.get(eid, []):
            rel_groups.setdefault(edge.relation_type, []).append(
                f"ukip:entity/{edge.target_id}"
            )
        for rel_type, targets in rel_groups.items():
            node[rel_type] = [{"@id": t} for t in targets]

        graph_nodes.append(node)

    payload = {
        "@context": context,
        "@type":    "ukip:KnowledgeGraph",
        "ukip:generatedAt": generated_at,
        "ukip:nodeCount":   len(entities),
        "ukip:edgeCount":   len(edges),
        "@graph": graph_nodes,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/export/graph")
def export_graph(
    format: _FORMAT = Query(..., description="Output format: graphml | cytoscape | jsonld"),
    domain: Optional[str] = Query(None, max_length=64, description="Filter to a specific domain"),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """
    Sprint 75 — Export the knowledge graph in a standard interchange format.

    Nodes are entities; edges are typed, weighted relationships.
    Optional `domain` parameter scopes the export to a single domain.
    """
    scoped_domain = domain.strip() if domain else None
    if scoped_domain and scoped_domain.lower() == "all":
        scoped_domain = None

    entities, edges = _fetch_graph(db, scoped_domain)
    now = datetime.now(timezone.utc).isoformat()
    domain_slug = f"_{scoped_domain}" if scoped_domain else ""
    filename = f"ukip_graph{domain_slug}.{_EXTENSIONS[format]}"

    if format == "graphml":
        content = _to_graphml(entities, edges)
    elif format == "cytoscape":
        content = _to_cytoscape(entities, edges, now)
    else:  # jsonld
        content = _to_jsonld(entities, edges, now)

    return StreamingResponse(
        io.BytesIO(content),
        media_type=_CONTENT_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
