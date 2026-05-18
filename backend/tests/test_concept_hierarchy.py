"""
Tests for concept hierarchy materialization and endpoints.
"""
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend import models
from backend.analyzers.concept_hierarchy import (
    _read_cache,
    _write_cache,
    _cache_path,
    build_concept_tree,
    _gather_corpus_concepts,
    _CACHE_DIR,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_entity(db, name="Test", domain="science", concepts="Biology, Genetics", concept_ids=None):
    attrs = {}
    if concept_ids:
        attrs["enrichment_concept_ids"] = concept_ids
    entity = models.RawEntity(
        primary_label=name,
        domain=domain,
        enrichment_status="completed",
        enrichment_concepts=concepts,
        attributes_json=json.dumps(attrs) if attrs else "{}",
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def _make_concept_node(db, openalex_id, name, level, domain="science", parent_id=None, entity_count=0):
    node = models.ConceptNode(
        openalex_id=openalex_id,
        display_name=name,
        level=level,
        domain=domain,
        parent_id=parent_id,
        entity_count=entity_count,
        last_fetched_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


# ── Model tests ──────────────────────────────────────────────────────────────

class TestConceptNodeModel:

    def test_create_concept_node(self, db_session):
        node = _make_concept_node(db_session, "C41008148", "Computer Science", 0)
        assert node.id is not None
        assert node.openalex_id == "C41008148"
        assert node.level == 0
        assert node.parent_id is None

    def test_self_referential_fk(self, db_session):
        parent = _make_concept_node(db_session, "C41008148", "Computer Science", 0)
        child = _make_concept_node(db_session, "C154945302", "AI", 1, parent_id=parent.id)
        assert child.parent_id == parent.id

    def test_unique_constraint_per_domain(self, db_session):
        _make_concept_node(db_session, "C41008148", "CS", 0, domain="science")
        # Same concept in different domain should work
        _make_concept_node(db_session, "C41008148", "CS", 0, domain="healthcare")
        # Same concept in same domain should fail
        with pytest.raises(Exception):
            _make_concept_node(db_session, "C41008148", "CS Duplicate", 0, domain="science")


# ── Cache tests ──────────────────────────────────────────────────────────────

class TestConceptCache:

    def test_cache_miss_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.analyzers.concept_hierarchy._CACHE_DIR", tmp_path)
        assert _read_cache("C_nonexistent") is None

    def test_cache_write_and_read(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.analyzers.concept_hierarchy._CACHE_DIR", tmp_path)
        data = {"id": "C123", "display_name": "Test Concept", "level": 1}
        _write_cache("C123", data)
        cached = _read_cache("C123")
        assert cached is not None
        assert cached["display_name"] == "Test Concept"

    def test_cache_expired_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.analyzers.concept_hierarchy._CACHE_DIR", tmp_path)
        data = {
            "id": "C123",
            "_cached_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        }
        path = tmp_path / "C123.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert _read_cache("C123") is None


# ── Materialization logic tests ──────────────────────────────────────────────

class TestMaterializationLogic:

    def test_gather_corpus_concepts(self, db_session):
        _make_entity(db_session, "E1", concepts="Machine Learning, AI")
        _make_entity(db_session, "E2", concepts="Machine Learning, Biology")
        freq = _gather_corpus_concepts(db_session, "science")
        assert freq["Machine Learning"] == 2
        assert freq["AI"] == 1
        assert freq["Biology"] == 1

    def test_gather_empty_domain(self, db_session):
        freq = _gather_corpus_concepts(db_session, "empty_domain")
        assert freq == {}

    @pytest.mark.asyncio
    async def test_materialize_with_mocked_openalex(self, db_session):
        _make_entity(
            db_session, "Paper1", concepts="Deep Learning",
            concept_ids=["https://openalex.org/C108583219"],
        )

        mock_concept_data = {
            "https://openalex.org/C108583219": {
                "id": "https://openalex.org/C108583219",
                "display_name": "Deep Learning",
                "level": 3,
                "ancestors": [
                    {"id": "https://openalex.org/C154945302", "display_name": "AI", "level": 1},
                    {"id": "https://openalex.org/C41008148", "display_name": "Computer Science", "level": 0},
                ],
            },
            "https://openalex.org/C154945302": {
                "id": "https://openalex.org/C154945302",
                "display_name": "Artificial Intelligence",
                "level": 1,
                "ancestors": [
                    {"id": "https://openalex.org/C41008148", "display_name": "Computer Science", "level": 0},
                ],
            },
            "https://openalex.org/C41008148": {
                "id": "https://openalex.org/C41008148",
                "display_name": "Computer Science",
                "level": 0,
                "ancestors": [],
            },
        }

        async def mock_fetch_batch(concept_ids):
            return {cid: mock_concept_data[cid] for cid in concept_ids if cid in mock_concept_data}

        with patch("backend.analyzers.concept_hierarchy._fetch_concepts_batch", side_effect=mock_fetch_batch):
            from backend.analyzers.concept_hierarchy import materialize_domain_concepts
            result = await materialize_domain_concepts(db_session, "science")

        assert result["nodes_created"] >= 1
        nodes = db_session.query(models.ConceptNode).filter(models.ConceptNode.domain == "science").all()
        names = {n.display_name for n in nodes}
        assert "Deep Learning" in names
        assert "Computer Science" in names

    @pytest.mark.asyncio
    async def test_idempotent_materialization(self, db_session):
        """Running materialization twice should not create duplicates."""
        _make_entity(
            db_session, "Paper1", concepts="Biology",
            concept_ids=["https://openalex.org/C86803240"],
        )

        mock_data = {
            "https://openalex.org/C86803240": {
                "id": "https://openalex.org/C86803240",
                "display_name": "Biology",
                "level": 0,
                "ancestors": [],
            },
        }

        async def mock_fetch_batch(concept_ids):
            return {cid: mock_data[cid] for cid in concept_ids if cid in mock_data}

        with patch("backend.analyzers.concept_hierarchy._fetch_concepts_batch", side_effect=mock_fetch_batch):
            from backend.analyzers.concept_hierarchy import materialize_domain_concepts
            r1 = await materialize_domain_concepts(db_session, "science")
            r2 = await materialize_domain_concepts(db_session, "science")

        count = db_session.query(models.ConceptNode).filter(
            models.ConceptNode.domain == "science",
            models.ConceptNode.openalex_id == "https://openalex.org/C86803240",
        ).count()
        assert count == 1


# ── Tree building tests ──────────────────────────────────────────────────────

class TestConceptTree:

    def test_tree_returns_nested_structure(self, db_session):
        root = _make_concept_node(db_session, "C0", "Computer Science", 0, entity_count=50)
        child = _make_concept_node(db_session, "C1", "AI", 1, parent_id=root.id, entity_count=30)
        _make_concept_node(db_session, "C2", "ML", 2, parent_id=child.id, entity_count=10)

        tree = build_concept_tree(db_session, "science")
        assert len(tree["nodes"]) == 1
        assert tree["nodes"][0]["name"] == "Computer Science"
        assert len(tree["nodes"][0]["children"]) == 1
        assert tree["nodes"][0]["children"][0]["name"] == "AI"
        assert len(tree["nodes"][0]["children"][0]["children"]) == 1

    def test_empty_tree(self, db_session):
        tree = build_concept_tree(db_session, "empty_domain")
        assert tree["nodes"] == []
        assert tree["materialized_at"] is None


# ── Endpoint tests ───────────────────────────────────────────────────────────

class TestConceptEndpoints:

    def test_tree_endpoint(self, client, auth_headers, db_session):
        root = _make_concept_node(db_session, "C0", "CS", 0, entity_count=5)
        resp = client.get("/analytics/concepts/science/tree", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) >= 1

    def test_concept_detail_endpoint(self, client, auth_headers, db_session):
        node = _make_concept_node(db_session, "C0", "Biology", 0, entity_count=2)
        _make_entity(db_session, "Bio Paper", concepts="Biology")

        resp = client.get(f"/analytics/concepts/science/{node.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Biology"
        assert data["total"] >= 1

    def test_concept_detail_pagination(self, client, auth_headers, db_session):
        node = _make_concept_node(db_session, "C0", "Biology", 0)
        for i in range(5):
            _make_entity(db_session, f"Paper {i}", concepts="Biology")

        resp = client.get(f"/analytics/concepts/science/{node.id}?page=1&per_page=2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entities"]) == 2
        assert data["total"] == 5

    def test_concept_detail_not_found(self, client, auth_headers):
        resp = client.get("/analytics/concepts/science/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_viewer_cannot_materialize(self, client, viewer_headers):
        resp = client.post("/analytics/concepts/science/materialize", headers=viewer_headers)
        assert resp.status_code == 403

    def test_admin_can_read_tree(self, client, auth_headers, db_session):
        resp = client.get("/analytics/concepts/science/tree", headers=auth_headers)
        assert resp.status_code == 200
