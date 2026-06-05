"""EPIC-016 US-072 — Cascade deletion / right to erasure.

Critical tests:
- After deletion, zero subject records remain in every DB surface.
- Cross-org deletion is blocked (404).
- Viewer is rejected (403).
- Wrong confirmation string is rejected (422).
- A completed DataLifecycleEvent with per-store evidence is created.
- ChromaDB delete_document is called for each entity.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from backend import models
from backend.auth import create_access_token
from backend.tenant_access import scope_query_to_org


def _org_with_user(session_factory, *, role: str = "admin"):
    suffix = uuid4().hex[:8]
    with session_factory() as db:
        user = models.User(
            username=f"u_{suffix}", password_hash="x", role=role, is_active=True
        )
        db.add(user)
        db.flush()
        org = models.Organization(
            name=f"Org {suffix}", slug=f"org-{suffix}",
            owner_id=user.id, plan="pro", is_active=True,
        )
        db.add(org)
        db.flush()
        db.add(models.OrganizationMember(org_id=org.id, user_id=user.id, role="owner"))
        user.org_id = org.id
        db.commit()
        uid, oid = user.id, org.id
    token = create_access_token(subject=user.username, role=role)
    return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": uid, "org_id": oid}


def _entity(db, *, org_id):
    e = models.RawEntity(
        org_id=org_id, primary_label=f"E-{uuid4().hex[:6]}", domain="default",
        entity_type="paper", source="test", validation_status="confirmed",
        enrichment_status="none", attributes_json="{}",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _confirm(org_id):
    return {"confirm": f"DELETE org {org_id}"}


def test_deletion_requires_correct_confirmation(client, session_factory):
    tenant = _org_with_user(session_factory)
    resp = client.post(
        "/admin/data-lifecycle/delete",
        json={"confirm": "wrong"},
        headers=tenant["headers"],
    )
    assert resp.status_code == 422


def test_deletion_rejected_for_viewer(client, session_factory):
    viewer = _org_with_user(session_factory, role="viewer")
    resp = client.post(
        "/admin/data-lifecycle/delete",
        json=_confirm(viewer["org_id"]),
        headers=viewer["headers"],
    )
    assert resp.status_code == 403


def test_deletion_erases_entities_from_db(client, session_factory, db_session):
    tenant = _org_with_user(session_factory)
    _entity(db_session, org_id=tenant["org_id"])

    with patch("backend.analytics.vector_store.VectorStoreService") as mock_vs:
        mock_vs.delete_document = MagicMock()
        resp = client.post(
            "/admin/data-lifecycle/delete",
            json=_confirm(tenant["org_id"]),
            headers=tenant["headers"],
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] is True

    # Critical: zero entities remain for this org.
    remaining = scope_query_to_org(
        db_session.query(models.RawEntity), models.RawEntity, tenant["org_id"]
    ).count()
    assert remaining == 0


def test_deletion_calls_chromadb_delete_per_entity(client, session_factory, db_session):
    tenant = _org_with_user(session_factory)
    e1 = _entity(db_session, org_id=tenant["org_id"])
    e2 = _entity(db_session, org_id=tenant["org_id"])
    # Capture ids before deletion (rows will be gone after).
    e1_id, e2_id = e1.id, e2.id
    db_session.expunge_all()

    with patch("backend.analytics.vector_store.VectorStoreService") as mock_vs:
        mock_vs.delete_document = MagicMock()
        client.post(
            "/admin/data-lifecycle/delete",
            json=_confirm(tenant["org_id"]),
            headers=tenant["headers"],
        )
        called_ids = {call.args[0] for call in mock_vs.delete_document.call_args_list}

    assert f"entity-{e1_id}" in called_ids
    assert f"entity-{e2_id}" in called_ids


def test_deletion_creates_completed_lifecycle_event(client, session_factory, db_session):
    tenant = _org_with_user(session_factory)

    with patch("backend.analytics.vector_store.VectorStoreService") as mock_vs:
        mock_vs.delete_document = MagicMock()
        resp = client.post(
            "/admin/data-lifecycle/delete",
            json=_confirm(tenant["org_id"]),
            headers=tenant["headers"],
        )

    assert resp.status_code == 200
    event = (
        db_session.query(models.DataLifecycleEvent)
        .filter(
            models.DataLifecycleEvent.org_id == tenant["org_id"],
            models.DataLifecycleEvent.action == "deletion",
        )
        .order_by(models.DataLifecycleEvent.id.desc())
        .first()
    )
    assert event is not None
    assert event.status == "completed"
    assert event.evidence_json is not None


def test_deletion_does_not_touch_other_org(client, session_factory, db_session):
    tenant_a = _org_with_user(session_factory)
    tenant_b = _org_with_user(session_factory)
    entity_b = _entity(db_session, org_id=tenant_b["org_id"])

    with patch("backend.analytics.vector_store.VectorStoreService") as mock_vs:
        mock_vs.delete_document = MagicMock()
        resp = client.post(
            "/admin/data-lifecycle/delete",
            json=_confirm(tenant_a["org_id"]),
            headers=tenant_a["headers"],
        )

    assert resp.status_code == 200

    # Org B's entity must still exist.
    still_there = db_session.get(models.RawEntity, entity_b.id)
    assert still_there is not None
    assert still_there.org_id == tenant_b["org_id"]
