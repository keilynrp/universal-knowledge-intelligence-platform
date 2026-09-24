from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

from backend import models
from backend.auth import issue_access_token
from backend.enrichment_worker import enrich_with_web_scrapers


def _tenant_user(session_factory, *, role: str = "admin"):
    suffix = uuid4().hex[:8]
    username = f"tenant_async_{role}_{suffix}"

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
            name=f"Org {suffix}",
            slug=f"org-async-{suffix}",
            owner_id=user.id,
            plan="pro",
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
    }


def _entity(
    db,
    *,
    org_id: int | None,
    primary_label: str,
    domain: str = "default",
    secondary_label: str | None = None,
    enrichment_status: str = "none",
    enrichment_source: str | None = None,
):
    entity = models.RawEntity(
        org_id=org_id,
        primary_label=primary_label,
        secondary_label=secondary_label,
        domain=domain,
        entity_type="paper",
        source="test",
        validation_status="confirmed",
        enrichment_status=enrichment_status,
        enrichment_source=enrichment_source,
        attributes_json="{}",
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


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


def test_stores_and_scheduled_imports_scope_to_org(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory)
    tenant_b = _tenant_user(session_factory)

    store_response = client.post(
        "/stores",
        json=_store_payload("Tenant A Store"),
        headers=tenant_a["headers"],
    )
    assert store_response.status_code == 201
    store_id = store_response.json()["id"]

    store = db_session.get(models.StoreConnection, store_id)
    assert store is not None
    assert store.org_id == tenant_a["org_id"]

    list_a = client.get("/stores", headers=tenant_a["headers"])
    assert list_a.status_code == 200
    assert [item["id"] for item in list_a.json()] == [store_id]

    list_b = client.get("/stores", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    assert list_b.json() == []

    cross_get = client.get(f"/stores/{store_id}", headers=tenant_b["headers"])
    assert cross_get.status_code == 404

    cross_schedule = client.post(
        "/scheduled-imports",
        json={"store_id": store_id, "name": "Cross Tenant Pull", "interval_minutes": 60},
        headers=tenant_b["headers"],
    )
    assert cross_schedule.status_code == 404

    schedule_response = client.post(
        "/scheduled-imports",
        json={"store_id": store_id, "name": "Tenant A Pull", "interval_minutes": 60},
        headers=tenant_a["headers"],
    )
    assert schedule_response.status_code == 201
    assert schedule_response.json()["org_id"] == tenant_a["org_id"]

    list_sched_a = client.get("/scheduled-imports", headers=tenant_a["headers"])
    assert list_sched_a.status_code == 200
    assert [item["id"] for item in list_sched_a.json()] == [schedule_response.json()["id"]]

    list_sched_b = client.get("/scheduled-imports", headers=tenant_b["headers"])
    assert list_sched_b.status_code == 200
    assert list_sched_b.json() == []

    cross_trigger = client.post(
        f"/scheduled-imports/{schedule_response.json()['id']}/trigger",
        headers=tenant_b["headers"],
    )
    assert cross_trigger.status_code == 404


def test_reports_and_scheduled_reports_scope_to_org(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory)
    tenant_b = _tenant_user(session_factory)

    _entity(
        db_session,
        org_id=tenant_a["org_id"],
        primary_label="Org A Report Entity",
        secondary_label="Brand A",
        domain="science",
        enrichment_status="completed",
        enrichment_source="openalex",
    )
    _entity(
        db_session,
        org_id=tenant_b["org_id"],
        primary_label="Org B Report Entity",
        secondary_label="Brand B",
        domain="science",
        enrichment_status="completed",
        enrichment_source="openalex",
    )

    report_response = client.post(
        "/reports/generate",
        json={
            "domain_id": "science",
            "sections": ["entity_stats", "enrichment_coverage", "top_brands"],
            "title": "Scoped Report",
        },
        headers=tenant_a["headers"],
    )
    assert report_response.status_code == 200
    html = report_response.text
    assert "Org A Report Entity" in html
    assert "Brand A" in html
    assert "Org B Report Entity" not in html
    assert "Brand B" not in html

    schedule_response = client.post(
        "/scheduled-reports",
        json={
            "name": "Tenant A Report",
            "domain_id": "science",
            "format": "html",
            "sections": ["entity_stats"],
            "interval_minutes": 1440,
            "recipient_emails": ["tenant-a@example.com"],
        },
        headers=tenant_a["headers"],
    )
    assert schedule_response.status_code == 201
    assert schedule_response.json()["org_id"] == tenant_a["org_id"]

    list_a = client.get("/scheduled-reports", headers=tenant_a["headers"])
    assert list_a.status_code == 200
    assert [item["id"] for item in list_a.json()] == [schedule_response.json()["id"]]

    list_b = client.get("/scheduled-reports", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    assert list_b.json() == []

    cross_fetch = client.get(
        f"/scheduled-reports/{schedule_response.json()['id']}",
        headers=tenant_b["headers"],
    )
    assert cross_fetch.status_code == 404


def test_scrapers_and_background_enrichment_scope_to_org(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory)
    tenant_b = _tenant_user(session_factory)

    scraper_payload = {
        "name": "Tenant A Scraper",
        "url_template": "https://example.com/search?q={primary_label}",
        "selector_type": "css",
        "selector": "p",
        "field_map": {"0": "enrichment_concepts"},
        "rate_limit_secs": 0.1,
        "is_active": True,
    }
    create_a = client.post("/scrapers", json=scraper_payload, headers=tenant_a["headers"])
    assert create_a.status_code == 201

    create_b = client.post(
        "/scrapers",
        json={**scraper_payload, "name": "Tenant B Scraper"},
        headers=tenant_b["headers"],
    )
    assert create_b.status_code == 201

    list_a = client.get("/scrapers", headers=tenant_a["headers"])
    assert list_a.status_code == 200
    assert [item["name"] for item in list_a.json()] == ["Tenant A Scraper"]

    cross_get = client.get(f"/scrapers/{create_a.json()['id']}", headers=tenant_b["headers"])
    assert cross_get.status_code == 404

    entity_a = _entity(
        db_session,
        org_id=tenant_a["org_id"],
        primary_label="Tenant A Entity",
        enrichment_status="failed",
    )

    db_session.query(models.WebScraperConfig).delete()
    db_session.commit()

    db_session.add(
        models.WebScraperConfig(
            org_id=tenant_b["org_id"],
            name="Tenant B Only Scraper",
            url_template="https://example.com/search?q={primary_label}",
            selector_type="css",
            selector="p",
            field_map=json.dumps({"0": "enrichment_concepts"}),
            rate_limit_secs=0.1,
            is_active=True,
        )
    )
    db_session.commit()

    mock_response = MagicMock(status_code=200, text="<html><body><p>Scoped Concept</p></body></html>")
    with patch("httpx.get", return_value=mock_response):
        assert enrich_with_web_scrapers(db_session, entity_a) is False

    db_session.add(
        models.WebScraperConfig(
            org_id=tenant_a["org_id"],
            name="Tenant A Only Scraper",
            url_template="https://example.com/search?q={primary_label}",
            selector_type="css",
            selector="p",
            field_map=json.dumps({"0": "enrichment_concepts"}),
            rate_limit_secs=0.1,
            is_active=True,
        )
    )
    db_session.commit()

    with patch("httpx.get", return_value=mock_response):
        assert enrich_with_web_scrapers(db_session, entity_a) is True

    db_session.commit()
    db_session.refresh(entity_a)
    assert entity_a.enrichment_status == "completed"
    assert entity_a.enrichment_source == "Tenant A Only Scraper"
