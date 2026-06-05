"""EPIC-016 US-071 — Subject/tenant export (DSAR).

Pins:
- Bundle contains the active org's rows from each surface.
- A different org's data never appears in the bundle.
- Non-admin (viewer) is rejected with 403.
- A DataLifecycleEvent audit record is created and completed.
"""
from __future__ import annotations

from uuid import uuid4

from backend import models
from backend.auth import create_access_token


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
    return e


def test_export_returns_bundle_for_active_org(client, session_factory, db_session):
    tenant = _org_with_user(session_factory)
    _entity(db_session, org_id=tenant["org_id"])

    resp = client.post("/admin/data-lifecycle/export", headers=tenant["headers"])
    assert resp.status_code == 200

    bundle = resp.json()
    assert "entities" in bundle
    assert bundle["_counts"]["entities"] >= 1
    assert all(e["org_id"] == tenant["org_id"] for e in bundle["entities"])


def test_export_does_not_leak_other_org(client, session_factory, db_session):
    tenant_a = _org_with_user(session_factory)
    tenant_b = _org_with_user(session_factory)
    _entity(db_session, org_id=tenant_a["org_id"])

    resp = client.post("/admin/data-lifecycle/export", headers=tenant_b["headers"])
    assert resp.status_code == 200

    bundle = resp.json()
    # Org B's bundle must not contain org A's entities
    assert all(e["org_id"] != tenant_a["org_id"] for e in bundle.get("entities", []))


def test_export_rejected_for_viewer(client, session_factory):
    viewer = _org_with_user(session_factory, role="viewer")
    resp = client.post("/admin/data-lifecycle/export", headers=viewer["headers"])
    assert resp.status_code == 403


def test_export_creates_completed_lifecycle_event(client, session_factory, db_session):
    tenant = _org_with_user(session_factory)

    resp = client.post("/admin/data-lifecycle/export", headers=tenant["headers"])
    assert resp.status_code == 200

    event = (
        db_session.query(models.DataLifecycleEvent)
        .filter(
            models.DataLifecycleEvent.org_id == tenant["org_id"],
            models.DataLifecycleEvent.action == "export",
        )
        .order_by(models.DataLifecycleEvent.id.desc())
        .first()
    )
    assert event is not None
    assert event.status == "completed"
    assert event.completed_at is not None
    assert event.evidence_json is not None


def test_list_events_scoped_to_org(client, session_factory, db_session):
    tenant_a = _org_with_user(session_factory)
    tenant_b = _org_with_user(session_factory)

    # Trigger an export for org A only
    client.post("/admin/data-lifecycle/export", headers=tenant_a["headers"])

    # Org A sees its event
    resp_a = client.get("/admin/data-lifecycle/events", headers=tenant_a["headers"])
    assert resp_a.status_code == 200
    assert len(resp_a.json()) >= 1

    # Org B sees no events (none created for org B)
    resp_b = client.get("/admin/data-lifecycle/events", headers=tenant_b["headers"])
    assert resp_b.status_code == 200
    assert resp_b.json() == []
