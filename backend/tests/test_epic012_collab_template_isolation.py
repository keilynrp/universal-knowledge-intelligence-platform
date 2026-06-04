"""EPIC-012 Wave 2-3 isolation coverage for collaboration + template surfaces.

annotations, alert_channels, user_dashboards and artifact_templates previously
had no org_id column and their routers performed unscoped lookups. These tests
pin the cross-tenant boundary for each so the leak cannot silently regress.
"""
from __future__ import annotations

import json
from uuid import uuid4

from backend import models
from backend.auth import create_access_token


def _tenant_user(session_factory, *, role: str = "admin", with_org: bool = True):
    suffix = uuid4().hex[:8]
    username = f"tenant_{role}_{suffix}"

    with session_factory() as db:
        user = models.User(
            username=username,
            password_hash="test-password-hash",
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()

        org_id = None
        if with_org:
            org = models.Organization(
                name=f"Org {suffix}",
                slug=f"org-{suffix}",
                owner_id=user.id,
                plan="pro",
                is_active=True,
            )
            db.add(org)
            db.flush()
            db.add(
                models.OrganizationMember(org_id=org.id, user_id=user.id, role="owner")
            )
            user.org_id = org.id
            org_id = org.id

        db.commit()
        user_id = user.id

    token = create_access_token(subject=username, role=role)
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_id,
        "org_id": org_id,
        "username": username,
    }


def _entity(db, *, org_id, primary_label: str):
    entity = models.RawEntity(
        org_id=org_id,
        primary_label=primary_label,
        domain="default",
        entity_type="paper",
        source="test",
        validation_status="confirmed",
        enrichment_status="none",
        attributes_json="{}",
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


# ── Annotations ─────────────────────────────────────────────────────────────

def test_annotations_scope_to_active_org(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory, with_org=True)
    tenant_b = _tenant_user(session_factory, with_org=True)

    entity_a = _entity(db_session, org_id=tenant_a["org_id"], primary_label="Entity A")

    created = client.post(
        "/annotations",
        json={"entity_id": entity_a.id, "content": "private note"},
        headers=tenant_a["headers"],
    )
    assert created.status_code == 201
    ann_id = created.json()["id"]

    # Tenant B cannot see it in a listing for the same entity id.
    list_b = client.get(
        f"/annotations?entity_id={entity_a.id}", headers=tenant_b["headers"]
    )
    assert list_b.status_code == 200
    assert list_b.json() == []

    # Tenant B cannot fetch or delete it directly.
    assert client.get(f"/annotations/{ann_id}", headers=tenant_b["headers"]).status_code == 404
    assert client.delete(f"/annotations/{ann_id}", headers=tenant_b["headers"]).status_code == 404

    # Owner still sees it.
    assert client.get(f"/annotations/{ann_id}", headers=tenant_a["headers"]).status_code == 200


def test_annotation_on_shared_entity_id_stays_isolated(client, session_factory, db_session):
    """entity_id is a soft reference; even if two tenants annotate the same id,
    each tenant only ever sees its own annotations."""
    tenant_a = _tenant_user(session_factory, with_org=True)
    tenant_b = _tenant_user(session_factory, with_org=True)

    entity_a = _entity(db_session, org_id=tenant_a["org_id"], primary_label="Entity A")

    a_note = client.post(
        "/annotations",
        json={"entity_id": entity_a.id, "content": "A note"},
        headers=tenant_a["headers"],
    )
    assert a_note.status_code == 201

    # Tenant B annotates the same entity id — allowed, but stamped to org B.
    b_note = client.post(
        "/annotations",
        json={"entity_id": entity_a.id, "content": "B note"},
        headers=tenant_b["headers"],
    )
    assert b_note.status_code == 201

    # Each tenant's listing for that entity id contains only its own note.
    list_a = client.get(f"/annotations?entity_id={entity_a.id}", headers=tenant_a["headers"])
    assert [a["content"] for a in list_a.json()] == ["A note"]

    list_b = client.get(f"/annotations?entity_id={entity_a.id}", headers=tenant_b["headers"])
    assert [a["content"] for a in list_b.json()] == ["B note"]


# ── Alert channels ──────────────────────────────────────────────────────────

def test_alert_channels_scope_to_active_org(client, session_factory):
    tenant_a = _tenant_user(session_factory, with_org=True)
    tenant_b = _tenant_user(session_factory, with_org=True)

    created = client.post(
        "/alert-channels",
        json={
            "name": "Slack A",
            "type": "slack",
            "webhook_url": "https://hooks.example.test/aaaaaaaa",
            "events": [],
        },
        headers=tenant_a["headers"],
    )
    assert created.status_code == 201
    channel_id = created.json()["id"]

    list_b = client.get("/alert-channels", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    assert all(c["id"] != channel_id for c in list_b.json())

    assert client.get(f"/alert-channels/{channel_id}", headers=tenant_b["headers"]).status_code == 404
    assert client.delete(f"/alert-channels/{channel_id}", headers=tenant_b["headers"]).status_code == 404
    assert client.get(f"/alert-channels/{channel_id}", headers=tenant_a["headers"]).status_code == 200


# ── User dashboards ─────────────────────────────────────────────────────────

def test_dashboards_scope_to_active_org(client, session_factory):
    tenant_a = _tenant_user(session_factory, with_org=True)
    tenant_b = _tenant_user(session_factory, with_org=True)

    created = client.post(
        "/dashboards",
        json={"name": "Dash A", "layout": []},
        headers=tenant_a["headers"],
    )
    assert created.status_code == 201
    dash_id = created.json()["id"]

    list_b = client.get("/dashboards", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    assert list_b.json() == []

    assert client.get(f"/dashboards/{dash_id}", headers=tenant_b["headers"]).status_code == 404
    assert client.get(f"/dashboards/{dash_id}", headers=tenant_a["headers"]).status_code == 200


# ── Artifact templates ──────────────────────────────────────────────────────

def test_artifact_templates_builtins_shared_customs_scoped(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory, with_org=True)
    tenant_b = _tenant_user(session_factory, with_org=True)

    # A platform built-in is visible to every tenant.
    builtin = models.ArtifactTemplate(
        org_id=None,
        name="Built-in Exec Summary",
        description="",
        sections=json.dumps(["entity_stats"]),
        default_title="Exec",
        is_builtin=True,
        created_by=None,
    )
    db_session.add(builtin)
    db_session.commit()
    db_session.refresh(builtin)

    created = client.post(
        "/artifacts/templates",
        json={
            "name": "Custom A",
            "description": "",
            "sections": ["entity_stats"],
            "default_title": "A",
        },
        headers=tenant_a["headers"],
    )
    assert created.status_code == 201
    custom_id = created.json()["id"]

    # Tenant B sees the built-in but not tenant A's custom template.
    list_b = client.get("/artifacts/templates", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    names_b = {t["id"] for t in list_b.json()}
    assert builtin.id in names_b
    assert custom_id not in names_b

    # Tenant B cannot delete tenant A's custom template.
    assert client.delete(
        f"/artifacts/templates/{custom_id}", headers=tenant_b["headers"]
    ).status_code == 404

    # Built-ins cannot be deleted at all (403, not 404).
    assert client.delete(
        f"/artifacts/templates/{builtin.id}", headers=tenant_a["headers"]
    ).status_code == 403

    # Owner can delete its own custom template.
    assert client.delete(
        f"/artifacts/templates/{custom_id}", headers=tenant_a["headers"]
    ).status_code == 204
