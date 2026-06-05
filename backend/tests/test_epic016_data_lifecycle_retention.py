"""EPIC-016 US-073 — Retention purge + policy management.

Tests:
- Policy upsert/get scoped to active org.
- purge_expired_orgs deletes data for orgs past retention window.
- Fresh data (within window) is NOT purged.
- Manual trigger endpoint (super_admin only).
- DataLifecycleEvent recorded per purge.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from backend import models
from backend.auth import create_access_token
from backend.services.data_lifecycle import purge_expired_orgs


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


def _entity(db, *, org_id, days_old: int = 0):
    updated = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_old)
    e = models.RawEntity(
        org_id=org_id, primary_label=f"E-{uuid4().hex[:6]}", domain="default",
        entity_type="paper", source="test", validation_status="confirmed",
        enrichment_status="none", attributes_json="{}",
        updated_at=updated,
    )
    db.add(e)
    db.commit()
    return e


def _set_policy(db, org_id, retention_days):
    from backend.tenant_access import persisted_org_id
    persisted = persisted_org_id(org_id)
    pol = db.query(models.RetentionPolicy).filter(
        models.RetentionPolicy.org_id == persisted,
        models.RetentionPolicy.data_class == "all",
    ).first()
    if pol:
        pol.retention_days = retention_days
    else:
        pol = models.RetentionPolicy(
            org_id=persisted, data_class="all", retention_days=retention_days
        )
        db.add(pol)
    db.commit()


# ── Policy API ─────────────────────────────────────────────────────────────

def test_get_retention_policy_returns_default_when_none(client, session_factory):
    tenant = _org_with_user(session_factory)
    resp = client.get("/admin/data-lifecycle/retention", headers=tenant["headers"])
    assert resp.status_code == 200
    assert resp.json()["retention_days"] is None


def test_upsert_retention_policy(client, session_factory):
    tenant = _org_with_user(session_factory)
    resp = client.put(
        "/admin/data-lifecycle/retention",
        json={"data_class": "all", "retention_days": 90},
        headers=tenant["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["retention_days"] == 90

    # Second call updates it
    resp2 = client.put(
        "/admin/data-lifecycle/retention",
        json={"data_class": "all", "retention_days": 180},
        headers=tenant["headers"],
    )
    assert resp2.json()["retention_days"] == 180


# ── Purge logic ────────────────────────────────────────────────────────────

def test_purge_expired_deletes_old_data(db_session, session_factory):
    with session_factory() as db:
        user = models.User(username=f"u_{uuid4().hex[:6]}", password_hash="x",
                           role="admin", is_active=True)
        db.add(user)
        db.flush()
        org = models.Organization(name=f"O-{uuid4().hex[:4]}", slug=f"o-{uuid4().hex[:4]}",
                                   owner_id=user.id, plan="pro", is_active=True)
        db.add(org)
        db.flush()
        user.org_id = org.id
        db.commit()
        org_id = org.id

    # Entity 100 days old, policy = 30 days → should be purged.
    _entity(db_session, org_id=org_id, days_old=100)
    _set_policy(db_session, org_id, retention_days=30)

    with patch("backend.analytics.vector_store.VectorStoreService") as mock_vs:
        mock_vs.delete_document = MagicMock()
        result = purge_expired_orgs(db_session)

    assert str(org_id) in result
    remaining = db_session.query(models.RawEntity).filter(
        models.RawEntity.org_id == org_id
    ).count()
    assert remaining == 0


def test_purge_skips_fresh_data(db_session, session_factory):
    with session_factory() as db:
        user = models.User(username=f"u_{uuid4().hex[:6]}", password_hash="x",
                           role="admin", is_active=True)
        db.add(user)
        db.flush()
        org = models.Organization(name=f"O-{uuid4().hex[:4]}", slug=f"o-{uuid4().hex[:4]}",
                                   owner_id=user.id, plan="pro", is_active=True)
        db.add(org)
        db.flush()
        user.org_id = org.id
        db.commit()
        org_id = org.id

    # Entity only 5 days old, policy = 30 days → NOT purged.
    _entity(db_session, org_id=org_id, days_old=5)
    _set_policy(db_session, org_id, retention_days=30)

    with patch("backend.analytics.vector_store.VectorStoreService") as mock_vs:
        mock_vs.delete_document = MagicMock()
        result = purge_expired_orgs(db_session)

    assert str(org_id) not in result
    remaining = db_session.query(models.RawEntity).filter(
        models.RawEntity.org_id == org_id
    ).count()
    assert remaining == 1


def test_purge_creates_lifecycle_event(db_session, session_factory):
    with session_factory() as db:
        user = models.User(username=f"u_{uuid4().hex[:6]}", password_hash="x",
                           role="admin", is_active=True)
        db.add(user)
        db.flush()
        org = models.Organization(name=f"O-{uuid4().hex[:4]}", slug=f"o-{uuid4().hex[:4]}",
                                   owner_id=user.id, plan="pro", is_active=True)
        db.add(org)
        db.flush()
        user.org_id = org.id
        db.commit()
        org_id = org.id

    _entity(db_session, org_id=org_id, days_old=100)
    _set_policy(db_session, org_id, retention_days=30)

    with patch("backend.analytics.vector_store.VectorStoreService") as mock_vs:
        mock_vs.delete_document = MagicMock()
        purge_expired_orgs(db_session)

    event = db_session.query(models.DataLifecycleEvent).filter(
        models.DataLifecycleEvent.org_id == org_id,
        models.DataLifecycleEvent.action == "purge",
    ).first()
    assert event is not None
    assert event.status == "completed"


def test_manual_purge_trigger_requires_super_admin(client, session_factory):
    admin = _org_with_user(session_factory, role="admin")
    resp = client.post("/admin/data-lifecycle/purge", headers=admin["headers"])
    assert resp.status_code == 403
