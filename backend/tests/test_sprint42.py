"""
Sprint 42 regression tests — Collaborative Annotations.
"""
import pytest

from backend import models


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_entity(db_session) -> int:
    e = models.RawEntity(entity_name="Test Entity", source="user")
    db_session.add(e)
    db_session.commit()
    return e.id


def _seed_authority(db_session) -> int:
    a = models.AuthorityRecord(
        field_name="brand_capitalized",
        original_value="TestBrand",
        authority_source="wikidata",
        authority_id="Q123",
        canonical_label="TestBrand Corp",
        confidence=0.9,
    )
    db_session.add(a)
    db_session.commit()
    return a.id


# ── GET /annotations — requires auth ─────────────────────────────────────────

def test_annotations_requires_auth(client):
    resp = client.get("/annotations")
    assert resp.status_code in (401, 403)


# ── POST /annotations — create on entity ─────────────────────────────────────

def test_create_annotation_on_entity(client, auth_headers, db_session):
    entity_id = _seed_entity(db_session)
    resp = client.post(
        "/annotations",
        json={"entity_id": entity_id, "content": "This entity needs review."},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["entity_id"] == entity_id
    assert data["content"] == "This entity needs review."
    assert data["author_name"] == "testadmin"
    assert data["parent_id"] is None


# ── POST /annotations — reply (parent_id) ────────────────────────────────────

def test_create_reply_annotation(client, auth_headers, db_session):
    entity_id = _seed_entity(db_session)
    # First annotation
    parent_resp = client.post(
        "/annotations",
        json={"entity_id": entity_id, "content": "Parent comment."},
        headers=auth_headers,
    )
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["id"]

    # Reply
    reply_resp = client.post(
        "/annotations",
        json={"entity_id": entity_id, "parent_id": parent_id, "content": "Reply here."},
        headers=auth_headers,
    )
    assert reply_resp.status_code == 201
    assert reply_resp.json()["parent_id"] == parent_id


# ── GET /annotations — filter by entity_id ───────────────────────────────────

def test_list_annotations_by_entity(client, auth_headers, db_session):
    entity_id = _seed_entity(db_session)
    # Create 2 annotations on the entity
    for i in range(2):
        client.post(
            "/annotations",
            json={"entity_id": entity_id, "content": f"Comment {i}"},
            headers=auth_headers,
        )
    resp = client.get(f"/annotations?entity_id={entity_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


# ── PUT /annotations — update own annotation ─────────────────────────────────

def test_update_annotation_own(client, auth_headers, db_session):
    entity_id = _seed_entity(db_session)
    create_resp = client.post(
        "/annotations",
        json={"entity_id": entity_id, "content": "Original content."},
        headers=auth_headers,
    )
    ann_id = create_resp.json()["id"]

    put_resp = client.put(
        f"/annotations/{ann_id}",
        json={"content": "Updated content."},
        headers=auth_headers,
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["content"] == "Updated content."


# ── DELETE /annotations — delete own annotation ──────────────────────────────

def test_delete_annotation_own(client, auth_headers, db_session):
    entity_id = _seed_entity(db_session)
    create_resp = client.post(
        "/annotations",
        json={"entity_id": entity_id, "content": "To be deleted."},
        headers=auth_headers,
    )
    ann_id = create_resp.json()["id"]

    del_resp = client.delete(f"/annotations/{ann_id}", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] == ann_id

    # Confirm gone
    get_resp = client.get(f"/annotations/{ann_id}", headers=auth_headers)
    assert get_resp.status_code == 404


# ── Viewer cannot create annotation ──────────────────────────────────────────

def test_viewer_cannot_create_annotation(client, viewer_headers, db_session):
    entity_id = _seed_entity(db_session)
    resp = client.post(
        "/annotations",
        json={"entity_id": entity_id, "content": "Viewer comment."},
        headers=viewer_headers,
    )
    assert resp.status_code in (401, 403)
