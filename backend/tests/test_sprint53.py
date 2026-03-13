"""
Sprint 53 — Full-Text Search (FTS5)
GET  /search
POST /search/rebuild
"""
import pytest
from sqlalchemy import text


# ── Access control ─────────────────────────────────────────────────────────────

def test_search_requires_auth(client):
    resp = client.get("/search?q=test")
    assert resp.status_code in (401, 403)


def test_search_rebuild_requires_admin(client, editor_headers):
    resp = client.post("/search/rebuild", headers=editor_headers)
    assert resp.status_code in (401, 403)


# ── Shape ──────────────────────────────────────────────────────────────────────

def test_search_returns_shape(client, auth_headers, db_session):
    resp = client.get("/search?q=anything", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_search_empty_query_422(client, auth_headers):
    resp = client.get("/search?q=", headers=auth_headers)
    assert resp.status_code == 422


# ── Indexing ───────────────────────────────────────────────────────────────────

def test_search_finds_entity_after_rebuild(client, auth_headers, db_session, session_factory):
    """Seed an entity, rebuild index, then search → found."""
    with session_factory() as db:
        db.execute(text(
            "INSERT INTO raw_entities (entity_name, sku, brand_capitalized, enrichment_status, source) "
            "VALUES ('Zythium Widget Pro', 'ZWP-001', 'AcmeCorp', 'none', 'user')"
        ))
        db.commit()

    # Rebuild
    rebuild = client.post("/search/rebuild", headers=auth_headers)
    assert rebuild.status_code == 200
    assert rebuild.json()["indexed"] >= 1

    # Search by entity name token
    resp = client.get("/search?q=Zythium", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    titles = [item["title"] for item in data["items"]]
    assert any("Zythium" in t for t in titles)


def test_search_finds_entity_by_sku(client, auth_headers, db_session, session_factory):
    """Prefix search on SKU field."""
    with session_factory() as db:
        db.execute(text(
            "INSERT INTO raw_entities (entity_name, sku, brand_capitalized, enrichment_status, source) "
            "VALUES ('Generic Entity', 'UNIQ-XK99', 'BrandX', 'none', 'user')"
        ))
        db.commit()

    client.post("/search/rebuild", headers=auth_headers)

    resp = client.get("/search?q=UNIQ-XK99", headers=auth_headers)
    assert resp.status_code == 200
    # SKU lives in the body field — result should surface
    assert resp.json()["total"] >= 1


def test_search_filter_by_doc_type(client, auth_headers, db_session, session_factory):
    """doc_type filter returns only matching resource types."""
    with session_factory() as db:
        db.execute(text(
            "INSERT INTO raw_entities (entity_name, sku, brand_capitalized, enrichment_status, source) "
            "VALUES ('FilterTest Entity', 'FT-001', 'FilterBrand', 'none', 'user')"
        ))
        db.commit()

    client.post("/search/rebuild", headers=auth_headers)

    resp = client.get("/search?q=FilterTest&doc_type=entity", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["doc_type"] == "entity"
