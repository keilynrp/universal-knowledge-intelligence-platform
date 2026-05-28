"""Tests for Co-authorship Network analyzer (task 3.5)."""
import pytest
from backend import models
from backend.database import SessionLocal
from backend.analyzers.coauthorship import (
    compute_degree_centrality,
    detect_communities,
    extract_coauthor_edges,
    coauthorship_network,
    MAX_AUTHORS_FOR_COAUTH,
)


def _seed_coauthor_edges(edges: list[tuple[str, str, float]], domain: str = "default"):
    """Seed CO_AUTHOR edges directly into entity_relationships."""
    db = SessionLocal()
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
        db = SessionLocal()
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

    def test_same_pair_is_scoped_by_source_domain(self, db_session):
        first = models.RawEntity(primary_label="Paper A", domain="__coauth_scope_a__")
        second = models.RawEntity(primary_label="Paper B", domain="__coauth_scope_b__")
        db_session.add_all([first, second])
        db_session.flush()

        extract_coauthor_edges(first.id, ["Alice", "Bob"], db_session)
        extract_coauthor_edges(second.id, ["Alice", "Bob"], db_session)
        db_session.commit()

        result_a = coauthorship_network("__coauth_scope_a__")
        result_b = coauthorship_network("__coauth_scope_b__")

        assert result_a["edges"] == [{"source": "Alice", "target": "Bob", "weight": 1.0}]
        assert result_b["edges"] == [{"source": "Alice", "target": "Bob", "weight": 1.0}]


class TestCoauthorshipEndpoints:
    def test_coauthorship_endpoint_ok(self, client, auth_headers):
        resp = client.get("/analyzers/coauthorship/default", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data


class TestEnrichmentHook:
    def test_post_enrichment_persists_coauthor_edges(self):
        """Replays the enrichment side-effect that materializes CO_AUTHOR rows."""
        import json
        from backend.enrichment_worker import _extract_and_persist_coauthor_edges

        db = SessionLocal()
        try:
            entity = models.RawEntity(
                primary_label="Multi-author paper",
                domain="__coauth_hook__",
                enrichment_status="completed",
                attributes_json=json.dumps(
                    {"enrichment_authors": ["Alice", "Bob", "Carol"]},
                ),
            )
            db.add(entity)
            db.commit()
            _extract_and_persist_coauthor_edges(db, entity)
            db.commit()

            rows = (
                db.query(models.EntityRelationship)
                .filter(models.EntityRelationship.relation_type == "CO_AUTHOR")
                .filter(models.EntityRelationship.source_id == entity.id)
                .all()
            )
            assert len(rows) == 3  # 3 pairs from 3 authors
        finally:
            db.close()

        result = coauthorship_network("__coauth_hook__")
        names = {n["id"] for n in result["nodes"]}
        assert names == {"Alice", "Bob", "Carol"}

    def test_hook_no_authors_is_noop(self):
        import json
        from backend.enrichment_worker import _extract_and_persist_coauthor_edges

        db = SessionLocal()
        try:
            entity = models.RawEntity(
                primary_label="Solo paper",
                domain="__coauth_hook_solo__",
                enrichment_status="completed",
                attributes_json=json.dumps({"enrichment_authors": ["Solo"]}),
            )
            db.add(entity)
            db.commit()
            _extract_and_persist_coauthor_edges(db, entity)
            db.commit()

            count = (
                db.query(models.EntityRelationship)
                .filter(models.EntityRelationship.source_id == entity.id)
                .count()
            )
            assert count == 0
        finally:
            db.close()

    def test_hook_accepts_string_separated_authors(self):
        import json
        from backend.enrichment_worker import _extract_and_persist_coauthor_edges

        db = SessionLocal()
        try:
            entity = models.RawEntity(
                primary_label="String authors",
                domain="__coauth_hook_string__",
                enrichment_status="completed",
                attributes_json=json.dumps({"authors": "Alice; Bob; Carol"}),
            )
            db.add(entity)
            db.commit()
            _extract_and_persist_coauthor_edges(db, entity)
            db.commit()

            count = (
                db.query(models.EntityRelationship)
                .filter(models.EntityRelationship.relation_type == "CO_AUTHOR")
                .filter(models.EntityRelationship.source_id == entity.id)
                .count()
            )
            assert count == 3
        finally:
            db.close()


class TestBackfillScript:
    @pytest.fixture(autouse=True)
    def _bind_script_sessionlocal(self, monkeypatch):
        """The script does `from backend.database import SessionLocal` at
        import time, which captures the pre-patched factory. Re-bind it on
        the script module so the script writes to the test DB."""
        import backend.scripts.backfill_coauthor_edges as coauthor_script
        from backend.database import SessionLocal as PatchedSessionLocal

        monkeypatch.setattr(coauthor_script, "SessionLocal", PatchedSessionLocal)


    def test_backfill_populates_existing_entities(self):
        import json
        from backend.scripts.backfill_coauthor_edges import backfill

        db = SessionLocal()
        try:
            for i, authors in enumerate([
                ["Alice", "Bob"],
                ["Alice", "Bob", "Carol"],
                ["Solo"],          # < 2 authors → skipped
                None,              # no authors → skipped
            ]):
                attrs: dict = {}
                if authors is not None:
                    attrs["enrichment_authors"] = authors
                db.add(models.RawEntity(
                    primary_label=f"Paper {i}",
                    domain="__coauth_backfill__",
                    enrichment_status="completed",
                    attributes_json=json.dumps(attrs) if attrs else None,
                ))
            db.commit()
        finally:
            db.close()

        stats = backfill(domain="__coauth_backfill__")
        assert stats["with_authors"] == 2

        result = coauthorship_network("__coauth_backfill__")
        # 2 multi-author papers produce: Alice-Bob (twice → weight 2) +
        # Alice-Carol + Bob-Carol
        names = {n["id"] for n in result["nodes"]}
        assert names == {"Alice", "Bob", "Carol"}
        ab_edge = next(
            e for e in result["edges"]
            if {e["source"], e["target"]} == {"Alice", "Bob"}
        )
        assert ab_edge["weight"] == 2  # seen in both seeded papers

    def test_backfill_reads_canonical_author_shapes(self):
        import json
        from backend.scripts.backfill_coauthor_edges import backfill

        db = SessionLocal()
        try:
            db.add(models.RawEntity(
                primary_label="Canonical authors paper",
                domain="__coauth_canonical_shapes__",
                enrichment_status="completed",
                attributes_json=json.dumps({
                    "canonical_authors": [
                        {"name": "Alice"},
                        {"name": "Bob"},
                        {"name": "Alice"},
                    ],
                }),
            ))
            db.add(models.RawEntity(
                primary_label="Author affiliations paper",
                domain="__coauth_canonical_shapes__",
                enrichment_status="completed",
                attributes_json=json.dumps({
                    "author_affiliations": [
                        {"author_name": "Carol"},
                        {"author_name": "Dave"},
                    ],
                }),
            ))
            db.add(models.RawEntity(
                primary_label="Raw record authors paper",
                domain="__coauth_canonical_shapes__",
                enrichment_status="completed",
                attributes_json=json.dumps({
                    "raw_record": {"authors": "Eve; Frank"},
                }),
            ))
            db.commit()
        finally:
            db.close()

        stats = backfill(domain="__coauth_canonical_shapes__")
        assert stats["with_authors"] == 3
        assert stats["edges_generated"] == 3

        result = coauthorship_network("__coauth_canonical_shapes__")
        edges = {frozenset((e["source"], e["target"])) for e in result["edges"]}
        assert frozenset(("Alice", "Bob")) in edges
        assert frozenset(("Carol", "Dave")) in edges
        assert frozenset(("Eve", "Frank")) in edges

    def test_backfill_dry_run_does_not_write(self):
        import json
        from backend.scripts.backfill_coauthor_edges import backfill

        db = SessionLocal()
        try:
            db.add(models.RawEntity(
                primary_label="Dry run paper",
                domain="__coauth_backfill_dry__",
                enrichment_status="completed",
                attributes_json=json.dumps(
                    {"enrichment_authors": ["X", "Y", "Z"]},
                ),
            ))
            db.commit()
        finally:
            db.close()

        backfill(domain="__coauth_backfill_dry__", dry_run=True)

        result = coauthorship_network("__coauth_backfill_dry__")
        assert result["nodes"] == []

    def test_coauthorship_invalid_domain(self, client, auth_headers):
        resp = client.get("/analyzers/coauthorship/nonexistent_xyz_999", headers=auth_headers)
        assert resp.status_code == 404

    def test_coauthorship_requires_auth(self, client):
        resp = client.get("/analyzers/coauthorship/default")
        assert resp.status_code in (401, 403)
