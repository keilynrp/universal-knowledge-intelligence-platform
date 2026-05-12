"""Tests for Co-authorship Network analyzer (task 3.5)."""
import pytest
from backend.tests.conftest import TestingSessionLocal
from backend import models
from backend.analyzers.coauthorship import (
    compute_degree_centrality,
    detect_communities,
    extract_coauthor_edges,
    coauthorship_network,
    MAX_AUTHORS_FOR_COAUTH,
)


def _seed_coauthor_edges(edges: list[tuple[str, str, float]], domain: str = "default"):
    """Seed CO_AUTHOR edges directly into entity_relationships."""
    db = TestingSessionLocal()
    try:
        # Need at least one entity for the join
        entity = models.RawEntity(
            primary_label="Shared Paper",
            domain=domain,
            enrichment_status="completed",
        )
        db.add(entity)
        db.flush()

        for a, b, weight in edges:
            # Canonical order
            if a > b:
                a, b = b, a
            db.add(models.EntityRelationship(
                source_id=entity.id,
                target_id=entity.id,
                relation_type="CO_AUTHOR",
                weight=weight,
                notes=f"{a}||{b}",
            ))
        db.commit()
    finally:
        db.close()


class TestDegreeCentrality:
    def test_basic_centrality(self):
        adj = {
            "A": {"B", "C"},
            "B": {"A"},
            "C": {"A"},
        }
        centrality = compute_degree_centrality(adj)
        assert centrality["A"] == round(2 / 2, 4)  # 1.0
        assert centrality["B"] == round(1 / 2, 4)  # 0.5
        assert centrality["C"] == round(1 / 2, 4)  # 0.5

    def test_single_node(self):
        adj = {"A": set()}
        centrality = compute_degree_centrality(adj)
        assert centrality["A"] == 0.0

    def test_fully_connected(self):
        adj = {
            "A": {"B", "C"},
            "B": {"A", "C"},
            "C": {"A", "B"},
        }
        centrality = compute_degree_centrality(adj)
        assert all(c == 1.0 for c in centrality.values())


class TestCommunityDetection:
    def test_two_components(self):
        adj = {
            "A": {"B"},
            "B": {"A"},
            "C": {"D"},
            "D": {"C"},
        }
        communities = detect_communities(adj)
        assert communities["A"] == communities["B"]
        assert communities["C"] == communities["D"]
        assert communities["A"] != communities["C"]

    def test_single_component(self):
        adj = {
            "A": {"B"},
            "B": {"A", "C"},
            "C": {"B"},
        }
        communities = detect_communities(adj)
        assert communities["A"] == communities["B"] == communities["C"]

    def test_isolated_nodes(self):
        adj = {
            "A": set(),
            "B": set(),
        }
        communities = detect_communities(adj)
        assert communities["A"] != communities["B"]


class TestCoauthorEdgeExtraction:
    def test_pairwise_extraction(self, db_session):
        count = extract_coauthor_edges(1, ["Alice", "Bob", "Carol"], db_session)
        assert count == 3  # 3 pairs from 3 authors

    def test_two_authors(self, db_session):
        count = extract_coauthor_edges(1, ["Alice", "Bob"], db_session)
        assert count == 1

    def test_single_author(self, db_session):
        count = extract_coauthor_edges(1, ["Alice"], db_session)
        assert count == 0

    def test_cap_behavior(self, db_session):
        authors = [f"Author{i}" for i in range(20)]
        count = extract_coauthor_edges(1, authors, db_session)
        # Star topology: first author linked to 19 others
        assert count == 19


class TestCoauthorshipNetwork:
    def test_network_with_edges(self):
        _seed_coauthor_edges([
            ("Alice", "Bob", 3.0),
            ("Alice", "Carol", 1.0),
            ("Bob", "Carol", 2.0),
        ])
        result = coauthorship_network("default")
        assert len(result["nodes"]) == 3
        assert len(result["edges"]) == 3
        # Alice has degree 2 (connected to Bob and Carol)
        alice_node = next(n for n in result["nodes"] if n["id"] == "Alice")
        assert alice_node["degree"] == 2

    def test_min_weight_filter(self):
        _seed_coauthor_edges([
            ("A", "B", 5.0),
            ("A", "C", 1.0),
        ], domain="__weight_test__")
        result = coauthorship_network("__weight_test__", min_weight=3)
        assert len(result["edges"]) == 1
        assert result["edges"][0]["source"] == "A"
        assert result["edges"][0]["target"] == "B"

    def test_empty_network(self):
        # Use unique domain that has an entity but no CO_AUTHOR edges
        db = TestingSessionLocal()
        try:
            db.add(models.RawEntity(
                primary_label="Solo Paper",
                domain="__coauth_empty__",
                enrichment_status="completed",
            ))
            db.commit()
        finally:
            db.close()
        result = coauthorship_network("__coauth_empty__")
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_limit_param(self):
        _seed_coauthor_edges([
            ("A", "B", 1.0),
            ("A", "C", 1.0),
            ("A", "D", 1.0),
            ("B", "C", 1.0),
        ])
        result = coauthorship_network("default", limit=2)
        assert len(result["nodes"]) <= 2


class TestCoauthorshipEndpoints:
    def test_coauthorship_endpoint_ok(self, client, auth_headers):
        resp = client.get("/analyzers/coauthorship/default", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data

    def test_coauthorship_invalid_domain(self, client, auth_headers):
        resp = client.get("/analyzers/coauthorship/nonexistent_xyz_999", headers=auth_headers)
        assert resp.status_code == 404

    def test_coauthorship_requires_auth(self, client):
        resp = client.get("/analyzers/coauthorship/default")
        assert resp.status_code in (401, 403)
