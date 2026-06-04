"""EPIC-012 isolation coverage for analysis contexts and embed widgets.

These routers previously fetched their records (and, for public embeds, the
underlying RawEntity data) without any tenant filter even though both models
carry an ``org_id``. The tests below pin the cross-tenant boundary so the leak
cannot silently regress.
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


def _analysis_context(db, *, org_id, user_id, label: str):
    record = models.AnalysisContext(
        org_id=org_id,
        domain_id="default",
        user_id=user_id,
        label=label,
        context_snapshot=json.dumps({"generated_at": "2026-06-04", "kpis": {}}),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _embed_widget(db, *, org_id, created_by, name: str, token: str):
    widget = models.EmbedWidget(
        org_id=org_id,
        name=name,
        widget_type="entity_stats",
        config="{}",
        public_token=token,
        allowed_origins="*",
        is_active=True,
        created_by=created_by,
    )
    db.add(widget)
    db.commit()
    db.refresh(widget)
    return widget


def _entity(db, *, org_id, primary_label: str):
    entity = models.RawEntity(
        org_id=org_id,
        primary_label=primary_label,
        domain="default",
        entity_type="paper",
        source="test",
        validation_status="confirmed",
        enrichment_status="completed",
        enrichment_source="openalex",
        enrichment_citation_count=1,
        attributes_json="{}",
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


# ── Analysis contexts ───────────────────────────────────────────────────────

def test_analysis_contexts_scope_to_active_org(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory, with_org=True)
    tenant_b = _tenant_user(session_factory, with_org=True)

    ctx_a = _analysis_context(
        db_session, org_id=tenant_a["org_id"], user_id=tenant_a["user_id"], label="Ctx A"
    )
    _analysis_context(
        db_session, org_id=tenant_b["org_id"], user_id=tenant_b["user_id"], label="Ctx B"
    )

    listing = client.get("/context/sessions", headers=tenant_a["headers"])
    assert listing.status_code == 200
    assert {row["label"] for row in listing.json()} == {"Ctx A"}

    own = client.get(f"/context/sessions/{ctx_a.id}", headers=tenant_a["headers"])
    assert own.status_code == 200

    cross = client.get(f"/context/sessions/{ctx_a.id}", headers=tenant_b["headers"])
    assert cross.status_code == 404


def test_analysis_context_cross_tenant_delete_blocked(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory, with_org=True)
    tenant_b = _tenant_user(session_factory, with_org=True)

    ctx_a = _analysis_context(
        db_session, org_id=tenant_a["org_id"], user_id=tenant_a["user_id"], label="Ctx A"
    )

    cross_delete = client.delete(
        f"/context/sessions/{ctx_a.id}", headers=tenant_b["headers"]
    )
    assert cross_delete.status_code == 404

    # Still present for the owning tenant.
    still_there = client.get(f"/context/sessions/{ctx_a.id}", headers=tenant_a["headers"])
    assert still_there.status_code == 200


# ── Embed widgets ───────────────────────────────────────────────────────────

def test_embed_widgets_scope_to_active_org(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory, with_org=True)
    tenant_b = _tenant_user(session_factory, with_org=True)

    widget_a = _embed_widget(
        db_session,
        org_id=tenant_a["org_id"],
        created_by=tenant_a["user_id"],
        name="Widget A",
        token=f"tok-a-{uuid4().hex[:8]}",
    )
    _embed_widget(
        db_session,
        org_id=tenant_b["org_id"],
        created_by=tenant_b["user_id"],
        name="Widget B",
        token=f"tok-b-{uuid4().hex[:8]}",
    )

    listing = client.get("/widgets", headers=tenant_a["headers"])
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert {item["name"] for item in body["items"]} == {"Widget A"}

    cross = client.get(f"/widgets/{widget_a.id}", headers=tenant_b["headers"])
    assert cross.status_code == 404


def test_public_embed_data_only_exposes_owning_tenant(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory, with_org=True)
    tenant_b = _tenant_user(session_factory, with_org=True)

    _entity(db_session, org_id=tenant_a["org_id"], primary_label="A One")
    _entity(db_session, org_id=tenant_a["org_id"], primary_label="A Two")
    _entity(db_session, org_id=tenant_b["org_id"], primary_label="B One")

    token = f"tok-pub-{uuid4().hex[:8]}"
    _embed_widget(
        db_session,
        org_id=tenant_a["org_id"],
        created_by=tenant_a["user_id"],
        name="Public A",
        token=token,
    )

    # Public, unauthenticated embed data must only count tenant A's entities.
    resp = client.get(f"/embed/{token}/data")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 2
