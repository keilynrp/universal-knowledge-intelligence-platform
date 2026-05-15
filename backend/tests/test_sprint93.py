"""
Sprint 93 — Widget SDK tests.

14 tests:
  Unit (data providers):
    - entity_stats returns total + enrichment_rate
    - top_concepts extracts and counts tags correctly
    - recent_entities returns limited list
    - quality_score returns average + distribution
  Integration (router - authenticated):
    - POST /widgets creates widget with public_token (201)
    - GET /widgets lists all widgets
    - GET /widgets/{id} returns detail
    - PUT /widgets/{id} updates widget
    - DELETE /widgets/{id} removes widget
  Integration (public embed endpoints):
    - GET /embed/{token}/config returns metadata without auth
    - GET /embed/{token}/data returns live data without auth
    - GET /embed/{token}/data increments view_count
    - GET /embed/{token}/snippet returns embed code
    - GET /embed/bad-token/data returns 404
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from backend import models
from backend.routers.widgets import (
    _data_entity_stats,
    _data_top_concepts,
    _data_recent_entities,
    _data_quality_score,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_entities(db, count=5):
    for i in range(count):
        e = models.RawEntity(
            primary_label=f"Entity {i}",
            domain="default",
            enrichment_status="completed" if i % 2 == 0 else "none",
            enrichment_concepts=f"concept_a, concept_b" if i < 3 else "concept_c",
            quality_score=0.5 + (i * 0.1),
        )
        db.add(e)
    db.commit()


def _make_entity(db, label: str, domain: str, *, concepts: str = "concept_a", quality_score: float = 0.7):
    entity = models.RawEntity(
        primary_label=label,
        domain=domain,
        enrichment_status="completed",
        enrichment_concepts=concepts,
        quality_score=quality_score,
    )
    db.add(entity)
    db.commit()
    return entity


def _create_widget(client, auth_headers, widget_type="entity_stats", **kwargs):
    payload = {
        "name": f"Test {widget_type} Widget",
        "widget_type": widget_type,
        "config": {"domain": "default"},
        **kwargs,
    }
    resp = client.post("/widgets", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()


# ── Unit: data providers ──────────────────────────────────────────────────────

class TestDataProviders:
    def test_entity_stats(self, db_session):
        _make_entities(db_session)
        result = _data_entity_stats(db_session, {})
        assert result["total"] >= 5
        assert "enrichment_rate" in result
        assert isinstance(result["by_domain"], list)

    def test_entity_stats_respects_domain_id_config(self, db_session):
        _make_entity(db_session, "Science Entity", "science")
        _make_entity(db_session, "Healthcare Entity", "healthcare")

        result = _data_entity_stats(db_session, {"domain_id": "science"})

        assert result["total"] == 1
        assert result["by_domain"] == [{"domain": "science", "count": 1}]

    def test_entity_stats_supports_legacy_domain_config(self, db_session):
        _make_entity(db_session, "Science Entity", "science")
        _make_entity(db_session, "Healthcare Entity", "healthcare")

        result = _data_entity_stats(db_session, {"domain": "healthcare"})

        assert result["total"] == 1
        assert result["by_domain"] == [{"domain": "healthcare", "count": 1}]

    def test_top_concepts(self, db_session):
        _make_entities(db_session)
        result = _data_top_concepts(db_session, {"limit": 5})
        assert "concepts" in result
        assert "total_unique" in result
        # concept_a and concept_b should appear
        labels = [c["concept"] for c in result["concepts"]]
        assert "concept_a" in labels or "concept_b" in labels

    def test_top_concepts_respects_domain_id_config(self, db_session):
        _make_entity(db_session, "Science Entity", "science", concepts="science_only")
        _make_entity(db_session, "Healthcare Entity", "healthcare", concepts="healthcare_only")

        result = _data_top_concepts(db_session, {"domain_id": "science", "limit": 5})

        assert result["concepts"] == [{"concept": "science_only", "count": 1}]

    def test_recent_entities(self, db_session):
        _make_entities(db_session)
        result = _data_recent_entities(db_session, {"limit": 3})
        assert "entities" in result
        assert len(result["entities"]) <= 3
        assert "primary_label" in result["entities"][0]

    def test_recent_entities_respects_domain_id_config(self, db_session):
        _make_entity(db_session, "Science Entity", "science")
        _make_entity(db_session, "Healthcare Entity", "healthcare")

        result = _data_recent_entities(db_session, {"domain_id": "science", "limit": 5})

        assert [entity["domain"] for entity in result["entities"]] == ["science"]

    def test_quality_score(self, db_session):
        _make_entities(db_session)
        result = _data_quality_score(db_session, {})
        assert result["average"] is not None
        assert result["count"] >= 5
        assert len(result["distribution"]) == 4

    def test_quality_score_respects_domain_id_config(self, db_session):
        _make_entity(db_session, "Science Entity", "science", quality_score=0.9)
        _make_entity(db_session, "Healthcare Entity", "healthcare", quality_score=0.2)

        result = _data_quality_score(db_session, {"domain_id": "science"})

        assert result["average"] == 0.9
        assert result["count"] == 1


# ── Integration: authenticated CRUD ──────────────────────────────────────────

class TestWidgetCRUD:
    def test_create_widget(self, client: TestClient, auth_headers: dict):
        resp = client.post("/widgets", json={
            "name": "Entity Stats Widget",
            "widget_type": "entity_stats",
            "config": {"domain": "default"},
            "allowed_origins": "https://mysite.com",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Entity Stats Widget"
        assert "public_token" in data
        assert len(data["public_token"]) == 36  # UUID

    def test_list_widgets(self, client: TestClient, auth_headers: dict):
        _create_widget(client, auth_headers)
        resp = client.get("/widgets", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 1

    def test_get_widget_detail(self, client: TestClient, auth_headers: dict):
        w = _create_widget(client, auth_headers, widget_type="top_concepts")
        resp = client.get(f"/widgets/{w['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["widget_type"] == "top_concepts"

    def test_update_widget(self, client: TestClient, auth_headers: dict):
        w = _create_widget(client, auth_headers)
        resp = client.put(f"/widgets/{w['id']}", json={"name": "Updated Widget", "is_active": False}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Widget"
        assert resp.json()["is_active"] is False

    def test_delete_widget(self, client: TestClient, auth_headers: dict):
        w = _create_widget(client, auth_headers)
        resp = client.delete(f"/widgets/{w['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert client.get(f"/widgets/{w['id']}", headers=auth_headers).status_code == 404


# ── Integration: public embed endpoints ───────────────────────────────────────

class TestPublicEmbed:
    def test_embed_config_no_auth(self, client: TestClient, auth_headers: dict):
        w = _create_widget(client, auth_headers)
        token = w["public_token"]
        resp = client.get(f"/embed/{token}/config")  # no auth headers
        assert resp.status_code == 200
        data = resp.json()
        assert data["widget_type"] == "entity_stats"
        assert "name" in data

    def test_embed_data_no_auth(self, client: TestClient, auth_headers: dict, db_session):
        _make_entities(db_session)
        w = _create_widget(client, auth_headers)
        token = w["public_token"]
        resp = client.get(f"/embed/{token}/data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["widget_type"] == "entity_stats"
        assert "data" in data
        assert "total" in data["data"]

    def test_embed_data_increments_view_count(self, client: TestClient, auth_headers: dict, db_session):
        _make_entities(db_session)
        w = _create_widget(client, auth_headers)
        token = w["public_token"]
        client.get(f"/embed/{token}/data")
        client.get(f"/embed/{token}/data")
        updated = client.get(f"/widgets/{w['id']}", headers=auth_headers).json()
        assert updated["view_count"] >= 2

    def test_embed_snippet_returns_code(self, client: TestClient, auth_headers: dict):
        w = _create_widget(client, auth_headers)
        token = w["public_token"]
        resp = client.get(f"/embed/{token}/snippet")
        assert resp.status_code == 200
        data = resp.json()
        assert "iframe_snippet" in data
        assert "js_snippet" in data
        assert token in data["iframe_snippet"]

    def test_embed_bad_token_returns_404(self, client: TestClient):
        resp = client.get("/embed/00000000-0000-0000-0000-000000000000/data")
        assert resp.status_code == 404
