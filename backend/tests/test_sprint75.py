"""
Sprint 75 — Knowledge Graph Export tests.

Covers:
- GET /export/graph auth guard
- format=graphml: valid XML, <graphml> root, node/edge presence
- format=cytoscape: valid JSON, elements.nodes / elements.edges structure, meta block
- format=jsonld: valid JSON-LD, @context, @graph, relation grouping
- domain filter: only entities + edges in specified domain returned
- empty graph: each format returns valid empty structure
- invalid format: 422 Unprocessable Entity
- Content-Disposition header includes correct filename and extension
- _fetch_graph unit: domain filter, edge filtering when endpoint outside domain
- serializer unit: _to_graphml, _to_cytoscape, _to_jsonld with known data
"""
import io
import json
import xml.etree.ElementTree as ET

import pytest

from backend.routers.graph_export import (
    _fetch_graph,
    _to_cytoscape,
    _to_graphml,
    _to_jsonld,
)

pytestmark = pytest.mark.postgres


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_entity(db, id_: int, label: str, domain: str = "default", entity_type: str = "paper"):
    from backend import models
    e = models.RawEntity(
        id=id_,
        primary_label=label,
        domain=domain,
        entity_type=entity_type,
    )
    db.add(e)
    return e


def _make_edge(db, src: int, tgt: int, rel: str = "cites", weight: float = 1.0):
    from backend import models
    edge = models.EntityRelationship(
        source_id=src,
        target_id=tgt,
        relation_type=rel,
        weight=weight,
    )
    db.add(edge)
    return edge


@pytest.fixture
def graph_db(db_session):
    """Seed: 3 entities (2 science, 1 default) + 2 edges.

    The `flush()` is load-bearing, not tidiness. `models.py` declares no
    `relationship()` anywhere, so SQLAlchemy's unit of work has no dependency
    processor telling it that `entity_relationships` rows need their
    `raw_entities` rows first. The topological sort people expect here applies
    to `create_all()`, not to INSERT ordering inside a flush — so with entities
    and edges pending together, the edges can go first.

    SQLite does not enforce foreign keys, so this never mattered there. On
    PostgreSQL it is a ForeignKeyViolation at fixture setup. The application
    code gets this right on its own (`graph_materializer._get_or_create_node`
    flushes the node before any edge references it); only the fixtures relied
    on the dialect being permissive.
    """
    _make_entity(db_session, 1001, "Paper A", domain="science")
    _make_entity(db_session, 1002, "Paper B", domain="science")
    _make_entity(db_session, 1003, "Widget X", domain="default")
    db_session.flush()
    _make_edge(db_session, 1001, 1002, rel="cites", weight=2.0)
    _make_edge(db_session, 1002, 1003, rel="related-to", weight=1.0)
    db_session.commit()
    return db_session


# ── Serializer unit tests ─────────────────────────────────────────────────────

class TestSerializers:
    def _entities(self):
        from types import SimpleNamespace
        return {
            1: SimpleNamespace(id=1, primary_label="Alpha", entity_type="paper", domain="science", quality_score=0.8),
            2: SimpleNamespace(id=2, primary_label="Beta",  entity_type="person", domain="science", quality_score=None),
        }

    def _edges(self):
        from types import SimpleNamespace
        return [
            SimpleNamespace(id=1, source_id=1, target_id=2, relation_type="authored-by", weight=1.0),
        ]

    def test_graphml_is_valid_xml(self):
        data = _to_graphml(self._entities(), self._edges())
        root = ET.fromstring(data)
        assert "graphml" in root.tag

    def test_graphml_has_nodes(self):
        data = _to_graphml(self._entities(), self._edges())
        root = ET.fromstring(data)
        ns = "http://graphml.graphdrawing.org/graphml"
        graph = root.find(f"{{{ns}}}graph")
        nodes = graph.findall(f"{{{ns}}}node")
        assert len(nodes) == 2

    def test_graphml_has_edges(self):
        data = _to_graphml(self._entities(), self._edges())
        root = ET.fromstring(data)
        ns = "http://graphml.graphdrawing.org/graphml"
        graph = root.find(f"{{{ns}}}graph")
        edges = graph.findall(f"{{{ns}}}edge")
        assert len(edges) == 1

    def test_graphml_edge_relation_type(self):
        data = _to_graphml(self._entities(), self._edges())
        root = ET.fromstring(data)
        ns = "http://graphml.graphdrawing.org/graphml"
        graph = root.find(f"{{{ns}}}graph")
        edge = graph.findall(f"{{{ns}}}edge")[0]
        data_els = {d.get("key"): d.text for d in edge.findall(f"{{{ns}}}data")}
        assert data_els["relation_type"] == "authored-by"

    def test_graphml_empty_graph(self):
        data = _to_graphml({}, [])
        root = ET.fromstring(data)
        ns = "http://graphml.graphdrawing.org/graphml"
        graph = root.find(f"{{{ns}}}graph")
        assert len(graph.findall(f"{{{ns}}}node")) == 0
        assert len(graph.findall(f"{{{ns}}}edge")) == 0

    def test_cytoscape_structure(self):
        data = json.loads(_to_cytoscape(self._entities(), self._edges(), "2026-01-01"))
        assert "elements" in data
        assert len(data["elements"]["nodes"]) == 2
        assert len(data["elements"]["edges"]) == 1

    def test_cytoscape_node_fields(self):
        data = json.loads(_to_cytoscape(self._entities(), self._edges(), "2026-01-01"))
        node = data["elements"]["nodes"][0]["data"]
        assert "id" in node
        assert "label" in node
        assert "domain" in node

    def test_cytoscape_meta_counts(self):
        data = json.loads(_to_cytoscape(self._entities(), self._edges(), "2026-01-01"))
        assert data["meta"]["node_count"] == 2
        assert data["meta"]["edge_count"] == 1

    def test_cytoscape_empty(self):
        data = json.loads(_to_cytoscape({}, [], "2026-01-01"))
        assert data["elements"]["nodes"] == []
        assert data["elements"]["edges"] == []

    def test_jsonld_context_and_graph(self):
        data = json.loads(_to_jsonld(self._entities(), self._edges(), "2026-01-01"))
        assert "@context" in data
        assert "@graph" in data
        assert len(data["@graph"]) == 2

    def test_jsonld_relation_grouped(self):
        data = json.loads(_to_jsonld(self._entities(), self._edges(), "2026-01-01"))
        graph = {n["@id"]: n for n in data["@graph"]}
        node1 = graph["ukip:entity/1"]
        assert "authored-by" in node1
        assert node1["authored-by"][0]["@id"] == "ukip:entity/2"

    def test_jsonld_empty(self):
        data = json.loads(_to_jsonld({}, [], "2026-01-01"))
        assert data["@graph"] == []


# ── _fetch_graph unit tests ───────────────────────────────────────────────────

class TestFetchGraph:
    def test_no_edges_returns_empty(self, db_session):
        entities, edges = _fetch_graph(db_session, None)
        assert entities == {}
        assert edges == []

    def test_domain_filter_excludes_other_domain(self, graph_db):
        entities, edges = _fetch_graph(graph_db, "science")
        assert all(e.domain == "science" for e in entities.values())
        # Edge 1002→1003 must be excluded (1003 is default domain)
        edge_pairs = {(e.source_id, e.target_id) for e in edges}
        assert (1002, 1003) not in edge_pairs

    def test_no_domain_filter_returns_all(self, graph_db):
        entities, edges = _fetch_graph(graph_db, None)
        assert len(entities) == 3
        assert len(edges) == 2


# ── Endpoint integration tests ────────────────────────────────────────────────

class TestExportGraphEndpoint:
    def test_requires_auth(self, client):
        resp = client.get("/export/graph?format=cytoscape")
        assert resp.status_code in (401, 403)

    def test_invalid_format_returns_422(self, client, editor_headers):
        resp = client.get("/export/graph?format=invalid_xyz", headers=editor_headers)
        assert resp.status_code == 422

    def test_graphml_content_type(self, client, editor_headers):
        resp = client.get("/export/graph?format=graphml", headers=editor_headers)
        assert resp.status_code == 200
        assert "xml" in resp.headers["content-type"]

    def test_cytoscape_content_type(self, client, editor_headers):
        resp = client.get("/export/graph?format=cytoscape", headers=editor_headers)
        assert resp.status_code == 200
        assert "json" in resp.headers["content-type"]

    def test_jsonld_content_type(self, client, editor_headers):
        resp = client.get("/export/graph?format=jsonld", headers=editor_headers)
        assert resp.status_code == 200
        assert "json" in resp.headers["content-type"]

    def test_graphml_filename_extension(self, client, editor_headers):
        resp = client.get("/export/graph?format=graphml", headers=editor_headers)
        cd = resp.headers.get("content-disposition", "")
        assert ".graphml" in cd

    def test_cytoscape_filename_extension(self, client, editor_headers):
        resp = client.get("/export/graph?format=cytoscape", headers=editor_headers)
        cd = resp.headers.get("content-disposition", "")
        assert ".json" in cd

    def test_jsonld_filename_extension(self, client, editor_headers):
        resp = client.get("/export/graph?format=jsonld", headers=editor_headers)
        cd = resp.headers.get("content-disposition", "")
        assert ".jsonld" in cd

    def test_empty_graph_graphml_is_valid_xml(self, client, editor_headers):
        # No entities/edges in clean test DB → valid empty GraphML
        resp = client.get("/export/graph?format=graphml", headers=editor_headers)
        assert resp.status_code == 200
        root = ET.fromstring(resp.content)
        assert "graphml" in root.tag

    def test_empty_graph_cytoscape_is_valid_json(self, client, editor_headers):
        resp = client.get("/export/graph?format=cytoscape", headers=editor_headers)
        data = resp.json()
        assert "elements" in data

    def test_domain_filter_in_filename(self, client, editor_headers):
        resp = client.get("/export/graph?format=graphml&domain=science", headers=editor_headers)
        cd = resp.headers.get("content-disposition", "")
        assert "science" in cd

    def test_with_data_graphml_has_nodes(self, client, editor_headers, graph_db):
        resp = client.get("/export/graph?format=graphml", headers=editor_headers)
        assert resp.status_code == 200
        root = ET.fromstring(resp.content)
        ns = "http://graphml.graphdrawing.org/graphml"
        graph = root.find(f"{{{ns}}}graph")
        nodes = graph.findall(f"{{{ns}}}node")
        assert len(nodes) == 3

    def test_with_data_cytoscape_node_count(self, client, editor_headers, graph_db):
        resp = client.get("/export/graph?format=cytoscape", headers=editor_headers)
        data = resp.json()
        assert data["meta"]["node_count"] == 3
        assert data["meta"]["edge_count"] == 2

    def test_domain_filter_reduces_node_count(self, client, editor_headers, graph_db):
        resp = client.get("/export/graph?format=cytoscape&domain=science", headers=editor_headers)
        data = resp.json()
        assert data["meta"]["node_count"] == 2
        assert data["meta"]["edge_count"] == 1

    def test_with_data_jsonld_graph_list(self, client, editor_headers, graph_db):
        resp = client.get("/export/graph?format=jsonld", headers=editor_headers)
        data = resp.json()
        assert "@graph" in data
        assert len(data["@graph"]) == 3
