from __future__ import annotations

from uuid import uuid4

from backend import models
from backend.auth import issue_access_token


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
                models.OrganizationMember(
                    org_id=org.id,
                    user_id=user.id,
                    role="owner",
                )
            )
            user.org_id = org.id
            org_id = org.id

        db.commit()
        user_id = user.id

    token = issue_access_token(subject=username, role=role)
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_id,
        "org_id": org_id,
        "username": username,
    }


def _entity(
    db,
    *,
    org_id: int | None,
    primary_label: str,
    secondary_label: str | None = None,
    domain: str = "default",
    entity_type: str = "paper",
    enrichment_concepts: str | None = None,
    enrichment_status: str = "none",
    enrichment_citation_count: int = 0,
):
    entity = models.RawEntity(
        org_id=org_id,
        primary_label=primary_label,
        secondary_label=secondary_label,
        domain=domain,
        entity_type=entity_type,
        source="test",
        validation_status="confirmed",
        enrichment_status=enrichment_status,
        enrichment_source="openalex" if enrichment_status == "completed" else None,
        enrichment_citation_count=enrichment_citation_count,
        enrichment_concepts=enrichment_concepts,
        attributes_json="{}",
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def _authority_record(db, *, org_id: int | None, original_value: str, canonical_label: str):
    record = models.AuthorityRecord(
        org_id=org_id,
        field_name="brand_capitalized",
        original_value=original_value,
        authority_source="wikidata",
        authority_id=f"Q-{uuid4().hex[:8]}",
        canonical_label=canonical_label,
        aliases="[]",
        description="test",
        confidence=0.95,
        uri="https://example.test/authority",
        status="pending",
        resolution_status="probable_match",
        score_breakdown="{}",
        evidence="[]",
        merged_sources="[]",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _workflow_payload(name: str) -> dict:
    return {
        "name": name,
        "description": "tenant-scoped workflow",
        "trigger_type": "manual",
        "trigger_config": {},
        "conditions": [],
        "actions": [{"type": "log_only", "config": {}}],
    }


def test_entities_scope_to_active_org(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory, role="admin", with_org=True)
    tenant_b = _tenant_user(session_factory, role="admin", with_org=True)

    entity_a = _entity(db_session, org_id=tenant_a["org_id"], primary_label="Org A Entity")
    entity_b = _entity(db_session, org_id=tenant_b["org_id"], primary_label="Org B Entity")

    response = client.get("/entities", headers=tenant_a["headers"])
    assert response.status_code == 200
    labels = {item["primary_label"] for item in response.json()}
    assert labels == {"Org A Entity"}

    own_detail = client.get(f"/entities/{entity_a.id}", headers=tenant_a["headers"])
    assert own_detail.status_code == 200
    assert own_detail.json()["id"] == entity_a.id

    other_detail = client.get(f"/entities/{entity_b.id}", headers=tenant_a["headers"])
    assert other_detail.status_code == 404


def test_legacy_global_scope_only_sees_null_org_rows(client, session_factory, db_session):
    legacy_user = _tenant_user(session_factory, role="editor", with_org=False)
    tenant_user = _tenant_user(session_factory, role="admin", with_org=True)

    global_entity = _entity(db_session, org_id=None, primary_label="Legacy Global Entity")
    _entity(db_session, org_id=tenant_user["org_id"], primary_label="Tenant Scoped Entity")

    response = client.get("/entities", headers=legacy_user["headers"])
    assert response.status_code == 200

    labels = {item["primary_label"] for item in response.json()}
    assert labels == {"Legacy Global Entity"}

    detail = client.get(f"/entities/{global_entity.id}", headers=legacy_user["headers"])
    assert detail.status_code == 200


def test_analytics_endpoints_scope_to_active_org(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory, role="admin", with_org=True)
    tenant_b = _tenant_user(session_factory, role="admin", with_org=True)

    _entity(
        db_session,
        org_id=tenant_a["org_id"],
        primary_label="AI Paper",
        secondary_label="Brand A",
        enrichment_status="completed",
        enrichment_citation_count=12,
        enrichment_concepts="AI, Forecasting",
    )
    _entity(
        db_session,
        org_id=tenant_b["org_id"],
        primary_label="Biology Paper",
        secondary_label="Brand B",
        enrichment_status="completed",
        enrichment_citation_count=5,
        enrichment_concepts="Biology, Genomics",
    )

    stats = client.get("/stats", headers=tenant_a["headers"])
    assert stats.status_code == 200
    assert stats.json()["total_entities"] == 1

    brands = client.get("/brands", headers=tenant_a["headers"])
    assert brands.status_code == 200
    assert brands.json() == [{"name": "Brand A", "count": 1}]

    dashboard = client.get("/dashboard/summary", headers=tenant_a["headers"])
    assert dashboard.status_code == 200
    assert dashboard.json()["kpis"]["total_entities"] == 1

    topics = client.get("/analyzers/topics/default?top_n=10", headers=tenant_a["headers"])
    assert topics.status_code == 200
    concepts = {item["concept"] for item in topics.json()["topics"]}
    assert "AI" in concepts
    assert "Biology" not in concepts


def test_workflows_are_scoped_by_org(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory, role="admin", with_org=True)
    tenant_b = _tenant_user(session_factory, role="admin", with_org=True)

    entity_a = _entity(db_session, org_id=tenant_a["org_id"], primary_label="Workflow Entity A")

    create_response = client.post(
        "/workflows",
        json=_workflow_payload("Tenant Workflow A"),
        headers=tenant_a["headers"],
    )
    assert create_response.status_code == 201
    workflow_id = create_response.json()["id"]
    assert create_response.json()["org_id"] == tenant_a["org_id"]

    list_a = client.get("/workflows", headers=tenant_a["headers"])
    assert list_a.status_code == 200
    assert [item["id"] for item in list_a.json()["items"]] == [workflow_id]

    list_b = client.get("/workflows", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    assert list_b.json()["items"] == []

    cross_fetch = client.get(f"/workflows/{workflow_id}", headers=tenant_b["headers"])
    assert cross_fetch.status_code == 404

    run_response = client.post(
        f"/workflows/{workflow_id}/run",
        json={"entity_id": entity_a.id},
        headers=tenant_a["headers"],
    )
    assert run_response.status_code == 201
    assert run_response.json()["org_id"] == tenant_a["org_id"]

    cross_run = client.post(
        f"/workflows/{workflow_id}/run",
        json={"entity_id": entity_a.id},
        headers=tenant_b["headers"],
    )
    assert cross_run.status_code == 404


def test_authority_records_are_scoped_by_org(client, session_factory, db_session):
    tenant_a = _tenant_user(session_factory, role="admin", with_org=True)
    tenant_b = _tenant_user(session_factory, role="admin", with_org=True)

    record_a = _authority_record(
        db_session,
        org_id=tenant_a["org_id"],
        original_value="microsoft",
        canonical_label="Microsoft",
    )
    record_b = _authority_record(
        db_session,
        org_id=tenant_b["org_id"],
        original_value="google",
        canonical_label="Google",
    )

    list_a = client.get("/authority/records", headers=tenant_a["headers"])
    assert list_a.status_code == 200
    ids_a = {record["id"] for record in list_a.json()["records"]}
    assert ids_a == {record_a.id}

    list_b = client.get("/authority/records", headers=tenant_b["headers"])
    assert list_b.status_code == 200
    ids_b = {record["id"] for record in list_b.json()["records"]}
    assert ids_b == {record_b.id}

    cross_confirm = client.post(
        f"/authority/records/{record_a.id}/confirm",
        json={"also_create_rule": False},
        headers=tenant_b["headers"],
    )
    assert cross_confirm.status_code == 404
