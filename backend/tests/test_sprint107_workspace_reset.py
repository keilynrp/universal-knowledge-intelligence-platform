from datetime import datetime, timezone

from backend import models
from backend.auth import create_access_token, hash_password


def _admin_headers(db_session):
    admin = models.User(
        username="org_admin_reset",
        password_hash=hash_password("admin-pass-123"),
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()

    primary_org = models.Organization(
        name="Primary Org",
        slug="primary-org-reset",
        owner_id=admin.id,
        is_active=True,
    )
    secondary_org = models.Organization(
        name="Secondary Org",
        slug="secondary-org-reset",
        owner_id=admin.id,
        is_active=True,
    )
    db_session.add_all([primary_org, secondary_org])
    db_session.flush()

    db_session.add_all(
        [
            models.OrganizationMember(org_id=primary_org.id, user_id=admin.id, role="admin"),
            models.OrganizationMember(org_id=secondary_org.id, user_id=admin.id, role="admin"),
        ]
    )
    admin.org_id = primary_org.id
    db_session.commit()

    token = create_access_token(subject=admin.username, role="admin")
    return {"Authorization": f"Bearer {token}"}, admin, primary_org, secondary_org


def _seed_workspace_data(db_session, admin, primary_org, secondary_org):
    now = datetime.now(timezone.utc)

    entity_primary = models.RawEntity(primary_label="Primary Entity", org_id=primary_org.id, domain="science")
    entity_secondary = models.RawEntity(primary_label="Secondary Entity", org_id=secondary_org.id, domain="science")
    db_session.add_all([entity_primary, entity_secondary])
    db_session.flush()

    relationship_primary = models.EntityRelationship(
        org_id=primary_org.id,
        source_id=entity_primary.id,
        target_id=entity_primary.id,
        relation_type="related-to",
    )
    relationship_secondary = models.EntityRelationship(
        org_id=secondary_org.id,
        source_id=entity_secondary.id,
        target_id=entity_secondary.id,
        relation_type="related-to",
    )

    authority_primary = models.AuthorityRecord(
        org_id=primary_org.id,
        field_name="author",
        original_value="Primary Author",
        authority_source="orcid",
        authority_id="0000-0000-0000-0001",
        canonical_label="Primary Author",
    )
    authority_secondary = models.AuthorityRecord(
        org_id=secondary_org.id,
        field_name="author",
        original_value="Secondary Author",
        authority_source="orcid",
        authority_id="0000-0000-0000-0002",
        canonical_label="Secondary Author",
    )
    db_session.add_all([relationship_primary, relationship_secondary, authority_primary, authority_secondary])
    db_session.flush()

    rule_primary = models.NormalizationRule(
        org_id=primary_org.id,
        field_name="primary_label",
        original_value="Primary Entity",
        canonical_value="Primary Entity Canonical",
    )
    rule_secondary = models.NormalizationRule(
        org_id=secondary_org.id,
        field_name="primary_label",
        original_value="Secondary Entity",
        canonical_value="Secondary Entity Canonical",
    )
    db_session.add_all([rule_primary, rule_secondary])
    db_session.flush()

    harm_primary = models.HarmonizationLog(
        org_id=primary_org.id,
        step_id="step-1",
        step_name="Normalize primary",
        records_updated=1,
        fields_modified='["primary_label"]',
        executed_at=now,
    )
    harm_secondary = models.HarmonizationLog(
        org_id=secondary_org.id,
        step_id="step-2",
        step_name="Normalize secondary",
        records_updated=1,
        fields_modified='["primary_label"]',
        executed_at=now,
    )
    db_session.add_all([harm_primary, harm_secondary])
    db_session.flush()

    db_session.add_all(
        [
            models.HarmonizationChangeRecord(log_id=harm_primary.id, record_id=entity_primary.id, field="primary_label"),
            models.HarmonizationChangeRecord(log_id=harm_secondary.id, record_id=entity_secondary.id, field="primary_label"),
            models.Annotation(
                entity_id=entity_primary.id,
                authority_id=authority_primary.id,
                author_id=admin.id,
                author_name=admin.username,
                content="Primary annotation",
            ),
            models.Annotation(
                entity_id=entity_secondary.id,
                authority_id=authority_secondary.id,
                author_id=admin.id,
                author_name=admin.username,
                content="Secondary annotation",
            ),
            models.LinkDismissal(entity_a_id=entity_primary.id, entity_b_id=entity_primary.id),
            models.LinkDismissal(entity_a_id=entity_secondary.id, entity_b_id=entity_secondary.id),
        ]
    )

    store_primary = models.StoreConnection(
        org_id=primary_org.id,
        name="Primary Store",
        platform="custom",
        base_url="https://primary.example.com",
        created_at=now,
        entity_count=9,
    )
    store_secondary = models.StoreConnection(
        org_id=secondary_org.id,
        name="Secondary Store",
        platform="custom",
        base_url="https://secondary.example.com",
        created_at=now,
        entity_count=7,
    )
    db_session.add_all([store_primary, store_secondary])
    db_session.flush()

    db_session.add_all(
        [
            models.StoreSyncMapping(store_id=store_primary.id, local_entity_id=entity_primary.id, canonical_url="https://primary.example.com/p1", created_at=now),
            models.StoreSyncMapping(store_id=store_secondary.id, local_entity_id=entity_secondary.id, canonical_url="https://secondary.example.com/s1", created_at=now),
            models.SyncLog(store_id=store_primary.id, action="pull", status="success", executed_at=now),
            models.SyncLog(store_id=store_secondary.id, action="pull", status="success", executed_at=now),
            models.SyncQueueItem(store_id=store_primary.id, direction="pull", field="title", created_at=now),
            models.SyncQueueItem(store_id=store_secondary.id, direction="pull", field="title", created_at=now),
        ]
    )

    workflow_primary = models.Workflow(org_id=primary_org.id, name="Primary Workflow", trigger_type="manual", run_count=5, last_run_at=now, last_run_status="success")
    workflow_secondary = models.Workflow(org_id=secondary_org.id, name="Secondary Workflow", trigger_type="manual", run_count=4, last_run_at=now, last_run_status="success")
    db_session.add_all([workflow_primary, workflow_secondary])
    db_session.flush()

    db_session.add_all(
        [
            models.WorkflowRun(org_id=primary_org.id, workflow_id=workflow_primary.id, status="success"),
            models.WorkflowRun(org_id=secondary_org.id, workflow_id=workflow_secondary.id, status="success"),
            models.AnalysisContext(domain_id="science", user_id=admin.id, label="Primary Snapshot", context_snapshot="{}"),
            models.ScheduledImport(org_id=primary_org.id, store_id=store_primary.id, name="Primary Import", total_runs=3, total_entities_imported=12, last_status="success"),
            models.ScheduledImport(org_id=secondary_org.id, store_id=store_secondary.id, name="Secondary Import", total_runs=2, total_entities_imported=8, last_status="success"),
            models.ScheduledReport(org_id=primary_org.id, name="Primary Report", total_sent=6, last_status="success"),
            models.ScheduledReport(org_id=secondary_org.id, name="Secondary Report", total_sent=4, last_status="success"),
            models.WebScraperConfig(org_id=primary_org.id, name="Primary Scraper", url_template="https://example.com?q={primary_label}", selector="body", total_runs=7, total_enriched=11, last_run_status="ok"),
            models.WebScraperConfig(org_id=secondary_org.id, name="Secondary Scraper", url_template="https://example.com?q={primary_label}", selector="body", total_runs=3, total_enriched=5, last_run_status="ok"),
        ]
    )

    db_session.flush()

    audit_primary = models.AuditLog(action="CREATE", entity_type="entity", entity_id=entity_primary.id, username=admin.username)
    audit_secondary = models.AuditLog(action="CREATE", entity_type="entity", entity_id=entity_secondary.id, username=admin.username)
    db_session.add_all([audit_primary, audit_secondary])
    db_session.flush()

    db_session.add_all(
        [
            models.UserNotificationRead(user_id=admin.id, audit_log_id=audit_primary.id),
            models.UserNotificationRead(user_id=admin.id, audit_log_id=audit_secondary.id),
            models.UserNotificationState(user_id=admin.id, last_read_at=now),
        ]
    )
    db_session.commit()


def test_workspace_reset_preview_requires_admin(client, viewer_headers):
    response = client.get("/admin/workspace-reset/preview", headers=viewer_headers)
    assert response.status_code == 403


def test_workspace_reset_clears_only_active_org_scope(client, session_factory):
    seed_db = session_factory()
    try:
        admin_headers, admin, primary_org, secondary_org = _admin_headers(seed_db)
        _seed_workspace_data(seed_db, admin, primary_org, secondary_org)
        primary_org_id = primary_org.id
        primary_org_name = primary_org.name
        secondary_org_id = secondary_org.id
    finally:
        seed_db.close()

    preview = client.get("/admin/workspace-reset/preview", headers=admin_headers)
    assert preview.status_code == 200
    preview_data = preview.json()
    assert preview_data["scope_type"] == "organization"
    assert preview_data["scope_label"] == primary_org_name
    assert preview_data["counts"]["entities"] == 1
    assert preview_data["counts"]["authority_records"] == 1

    bad_confirm = client.post(
        "/admin/workspace-reset",
        json={"confirmation_text": "NOPE"},
        headers=admin_headers,
    )
    assert bad_confirm.status_code == 422

    response = client.post(
        "/admin/workspace-reset",
        json={"confirmation_text": "RESET"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["deleted"]["raw_entities"] == 1
    assert payload["deleted"]["authority_records"] == 1
    assert payload["reset_counters"]["scheduled_imports"] == 1

    verify_db = session_factory()
    try:
        assert verify_db.query(models.RawEntity).filter(models.RawEntity.org_id == primary_org_id).count() == 0
        assert verify_db.query(models.RawEntity).filter(models.RawEntity.org_id == secondary_org_id).count() == 1
        assert verify_db.query(models.AuthorityRecord).filter(models.AuthorityRecord.org_id == primary_org_id).count() == 0
        assert verify_db.query(models.AuthorityRecord).filter(models.AuthorityRecord.org_id == secondary_org_id).count() == 1
        assert verify_db.query(models.Annotation).count() == 1
        remaining_entity_audits = (
            verify_db.query(models.AuditLog)
            .filter(models.AuditLog.entity_type == "entity")
            .all()
        )
        assert len(remaining_entity_audits) == 1
        surviving_secondary = verify_db.query(models.RawEntity).filter(models.RawEntity.org_id == secondary_org_id).one()
        assert remaining_entity_audits[0].entity_id == surviving_secondary.id
        assert verify_db.query(models.StoreSyncMapping).count() == 1
        assert verify_db.query(models.WorkflowRun).filter(models.WorkflowRun.org_id == primary_org_id).count() == 0
        assert verify_db.query(models.WorkflowRun).filter(models.WorkflowRun.org_id == secondary_org_id).count() == 1

        primary_store = verify_db.query(models.StoreConnection).filter(models.StoreConnection.org_id == primary_org_id).one()
        secondary_store = verify_db.query(models.StoreConnection).filter(models.StoreConnection.org_id == secondary_org_id).one()
        assert primary_store.entity_count == 0
        assert secondary_store.entity_count == 7

        primary_import = verify_db.query(models.ScheduledImport).filter(models.ScheduledImport.org_id == primary_org_id).one()
        secondary_import = verify_db.query(models.ScheduledImport).filter(models.ScheduledImport.org_id == secondary_org_id).one()
        assert primary_import.total_runs == 0
        assert primary_import.total_entities_imported == 0
        assert secondary_import.total_runs == 2

        primary_report = verify_db.query(models.ScheduledReport).filter(models.ScheduledReport.org_id == primary_org_id).one()
        secondary_report = verify_db.query(models.ScheduledReport).filter(models.ScheduledReport.org_id == secondary_org_id).one()
        assert primary_report.total_sent == 0
        assert primary_report.last_status == "pending"
        assert secondary_report.total_sent == 4

        primary_workflow = verify_db.query(models.Workflow).filter(models.Workflow.org_id == primary_org_id).one()
        secondary_workflow = verify_db.query(models.Workflow).filter(models.Workflow.org_id == secondary_org_id).one()
        assert primary_workflow.run_count == 0
        assert primary_workflow.last_run_status is None
        assert secondary_workflow.run_count == 4

        primary_scraper = verify_db.query(models.WebScraperConfig).filter(models.WebScraperConfig.org_id == primary_org_id).one()
        secondary_scraper = verify_db.query(models.WebScraperConfig).filter(models.WebScraperConfig.org_id == secondary_org_id).one()
        assert primary_scraper.total_runs == 0
        assert primary_scraper.total_enriched == 0
        assert secondary_scraper.total_runs == 3
    finally:
        verify_db.close()
