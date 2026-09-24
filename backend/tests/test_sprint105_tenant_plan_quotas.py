from __future__ import annotations

from uuid import uuid4

from backend import models
from backend.auth import issue_access_token


def _tenant_user(session_factory, *, plan: str = "free", role: str = "admin"):
    suffix = uuid4().hex[:8]
    username = f"quota_{role}_{suffix}"

    with session_factory() as db:
        user = models.User(
            username=username,
            password_hash="test-password-hash",
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()

        org = models.Organization(
            name=f"Quota Org {suffix}",
            slug=f"quota-org-{suffix}",
            owner_id=user.id,
            plan=plan,
            is_active=True,
        )
        db.add(org)
        db.flush()

        db.add(
            models.OrganizationMember(
                org_id=org.id,
                user_id=user.id,
                role="owner",
            )
        )
        user.org_id = org.id
        db.commit()
        org_id = org.id

    token = issue_access_token(subject=username, role=role)
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "org_id": org_id,
        "username": username,
    }


def _workflow_payload(name: str) -> dict:
    return {
        "name": name,
        "description": "quota test workflow",
        "trigger_type": "manual",
        "trigger_config": {},
        "conditions": [],
        "actions": [{"type": "log_only", "config": {}}],
    }


def _store_payload(name: str) -> dict:
    return {
        "name": name,
        "platform": "woocommerce",
        "base_url": f"https://{name.lower().replace(' ', '-')}.example.com",
        "api_key": "key123",
        "api_secret": "secret123",
        "access_token": None,
        "custom_headers": None,
        "sync_direction": "pull",
        "notes": None,
    }


def _create_user(client, auth_headers, username: str):
    response = client.post(
        "/users",
        json={"username": username, "password": "testpw123", "role": "viewer"},
        headers=auth_headers,
    )
    assert response.status_code == 201


def _resource(snapshot: dict, resource_id: str) -> dict:
    return next(item for item in snapshot["resources"] if item["resource"] == resource_id)


def test_quota_snapshot_reports_enforced_and_advisory_resources(client, session_factory):
    tenant = _tenant_user(session_factory, plan="free")

    key_response = client.post(
        "/api-keys",
        json={"name": "Automation Key", "scopes": ["read"]},
        headers=tenant["headers"],
    )
    assert key_response.status_code == 201

    workflow_response = client.post(
        "/workflows",
        json=_workflow_payload("Workflow 1"),
        headers=tenant["headers"],
    )
    assert workflow_response.status_code == 201

    response = client.get(
        f"/organizations/{tenant['org_id']}/quotas",
        headers=tenant["headers"],
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["organization"]["plan"] == "free"
    members = _resource(payload, "members")
    assert members["limit"] == 3
    assert members["usage"] == 1
    assert members["enforcement"] == "hard"

    workflows = _resource(payload, "workflows")
    assert workflows["usage"] == 1
    assert workflows["remaining"] == 2

    api_keys = _resource(payload, "api_keys_per_user")
    assert api_keys["enforcement"] == "advisory"
    assert api_keys["limit"] == 2
    assert api_keys["usage"] == 1

    alert_channels = _resource(payload, "alert_channels")
    assert alert_channels["status"] == "pending_model_alignment"
    assert alert_channels["usage"] is None


def test_free_plan_blocks_member_invites_after_limit(client, session_factory, auth_headers):
    tenant = _tenant_user(session_factory, plan="free")

    invitees = [f"quota_invitee_{uuid4().hex[:8]}" for _ in range(3)]
    for username in invitees:
        _create_user(client, auth_headers, username)

    first = client.post(
        f"/organizations/{tenant['org_id']}/members",
        json={"username": invitees[0], "role": "member"},
        headers=tenant["headers"],
    )
    assert first.status_code == 201

    second = client.post(
        f"/organizations/{tenant['org_id']}/members",
        json={"username": invitees[1], "role": "member"},
        headers=tenant["headers"],
    )
    assert second.status_code == 201

    third = client.post(
        f"/organizations/{tenant['org_id']}/members",
        json={"username": invitees[2], "role": "member"},
        headers=tenant["headers"],
    )
    assert third.status_code == 403
    assert "Plan limit reached" in third.json()["detail"]


def test_free_plan_blocks_second_store_and_import_schedule(client, session_factory):
    tenant = _tenant_user(session_factory, plan="free")

    first_store = client.post(
        "/stores",
        json=_store_payload("Free Store 1"),
        headers=tenant["headers"],
    )
    assert first_store.status_code == 201

    second_store = client.post(
        "/stores",
        json=_store_payload("Free Store 2"),
        headers=tenant["headers"],
    )
    assert second_store.status_code == 403
    assert "Plan limit reached" in second_store.json()["detail"]

    first_schedule = client.post(
        "/scheduled-imports",
        json={"store_id": first_store.json()["id"], "name": "Daily Pull", "interval_minutes": 60},
        headers=tenant["headers"],
    )
    assert first_schedule.status_code == 201

    second_schedule = client.post(
        "/scheduled-imports",
        json={"store_id": first_store.json()["id"], "name": "Backup Pull", "interval_minutes": 120},
        headers=tenant["headers"],
    )
    assert second_schedule.status_code == 403
    assert "Plan limit reached" in second_schedule.json()["detail"]


def test_free_plan_blocks_scrapers_reports_and_excess_workflows(client, session_factory):
    tenant = _tenant_user(session_factory, plan="free")

    scraper_payload = {
        "name": "Quota Scraper 1",
        "url_template": "https://example.com/search?q={primary_label}",
        "selector_type": "css",
        "selector": "p",
        "field_map": {"0": "enrichment_concepts"},
        "rate_limit_secs": 0.1,
        "is_active": True,
    }
    first_scraper = client.post("/scrapers", json=scraper_payload, headers=tenant["headers"])
    assert first_scraper.status_code == 201

    second_scraper = client.post(
        "/scrapers",
        json={**scraper_payload, "name": "Quota Scraper 2"},
        headers=tenant["headers"],
    )
    assert second_scraper.status_code == 403

    first_report = client.post(
        "/scheduled-reports",
        json={
            "name": "Quota Report 1",
            "domain_id": "default",
            "format": "html",
            "sections": ["entity_stats"],
            "interval_minutes": 1440,
            "recipient_emails": ["quota@example.com"],
        },
        headers=tenant["headers"],
    )
    assert first_report.status_code == 201

    second_report = client.post(
        "/scheduled-reports",
        json={
            "name": "Quota Report 2",
            "domain_id": "default",
            "format": "html",
            "sections": ["entity_stats"],
            "interval_minutes": 1440,
            "recipient_emails": ["quota@example.com"],
        },
        headers=tenant["headers"],
    )
    assert second_report.status_code == 403

    for idx in range(3):
        response = client.post(
            "/workflows",
            json=_workflow_payload(f"Workflow {idx + 1}"),
            headers=tenant["headers"],
        )
        assert response.status_code == 201

    blocked = client.post(
        "/workflows",
        json=_workflow_payload("Workflow 4"),
        headers=tenant["headers"],
    )
    assert blocked.status_code == 403


def test_pro_plan_allows_more_than_free_baseline(client, session_factory):
    tenant = _tenant_user(session_factory, plan="pro")

    first_store = client.post(
        "/stores",
        json=_store_payload("Pro Store 1"),
        headers=tenant["headers"],
    )
    second_store = client.post(
        "/stores",
        json=_store_payload("Pro Store 2"),
        headers=tenant["headers"],
    )

    assert first_store.status_code == 201
    assert second_store.status_code == 201

    first_report = client.post(
        "/scheduled-reports",
        json={
            "name": "Pro Report 1",
            "domain_id": "default",
            "format": "html",
            "sections": ["entity_stats"],
            "interval_minutes": 1440,
            "recipient_emails": ["pro@example.com"],
        },
        headers=tenant["headers"],
    )
    second_report = client.post(
        "/scheduled-reports",
        json={
            "name": "Pro Report 2",
            "domain_id": "default",
            "format": "html",
            "sections": ["entity_stats"],
            "interval_minutes": 1440,
            "recipient_emails": ["pro@example.com"],
        },
        headers=tenant["headers"],
    )

    assert first_report.status_code == 201
    assert second_report.status_code == 201
