"""Tests for governance API endpoints — Priority 1."""
import os
import pytest

# Must set env BEFORE importing backend modules
os.environ.setdefault("UKIP_SKIP_STARTUP_SIDE_EFFECTS", "1")
os.environ.setdefault("UKIP_DB_MODE", "sqlite")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_USERNAME", "testadmin")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword")
os.environ.setdefault("ENCRYPTION_KEY", "vRHc0zVcTXbRfUBZEsKNal2lMCfINwDh90EXE8vu2Ew=")
os.environ.setdefault("SENTRY_ENABLED", "0")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import models, database
from backend.main import app
from backend.database import get_db

# In-memory SQLite for tests
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
models.Base.metadata.create_all(bind=_test_engine)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


def _seed_users():
    """Seed test users into the in-memory DB."""
    import bcrypt
    db = _TestSession()
    pw_hash = bcrypt.hashpw(b"testpassword", bcrypt.gensalt()).decode()
    for username, role in [("testadmin", "super_admin"), ("editor1", "editor"), ("viewer1", "viewer")]:
        if not db.query(models.User).filter(models.User.username == username).first():
            db.add(models.User(username=username, password_hash=pw_hash, role=role, is_active=True))
    db.commit()
    db.close()


_seed_users()


@pytest.fixture(autouse=True)
def _reset_mapping_service():
    """Reset mapping service singleton between tests."""
    import backend.routers.governance as gov_mod
    gov_mod._mapping_service = None
    db = _TestSession()
    db.query(models.AuditLog).filter(models.AuditLog.entity_type == "field_correspondence_rule").delete()
    db.query(models.HarmonizationChangeRecord).delete()
    db.query(models.HarmonizationLog).filter(models.HarmonizationLog.step_id.like("field_correspondence_rule:%")).delete()
    db.query(models.RawEntity).delete()
    db.query(models.FieldCorrespondenceRule).delete()
    db.query(models.MappingSuggestionRecord).delete()
    db.commit()
    db.close()
    yield
    gov_mod._mapping_service = None
    db = _TestSession()
    db.query(models.AuditLog).filter(models.AuditLog.entity_type == "field_correspondence_rule").delete()
    db.query(models.HarmonizationChangeRecord).delete()
    db.query(models.HarmonizationLog).filter(models.HarmonizationLog.step_id.like("field_correspondence_rule:%")).delete()
    db.query(models.RawEntity).delete()
    db.query(models.FieldCorrespondenceRule).delete()
    db.query(models.MappingSuggestionRecord).delete()
    db.commit()
    db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_headers(client):
    from backend.auth import create_access_token
    token = create_access_token(subject="testadmin", role="super_admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def editor_headers(client):
    from backend.auth import create_access_token
    token = create_access_token(subject="editor1", role="editor")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_headers(client):
    from backend.auth import create_access_token
    token = create_access_token(subject="viewer1", role="viewer")
    return {"Authorization": f"Bearer {token}"}


class TestSourceProfileAPI:
    def test_create_profile(self, client, auth_headers):
        resp = client.post("/sources/profile", json={
            "source_id": "test_upload_1",
            "field_names": ["title", "doi", "author"],
            "sample_values": {
                "title": ["Machine Learning in Biology", "Deep Learning for NLP"],
                "doi": ["10.1234/abc", "10.5678/def"],
                "author": ["Smith, J.", "Jones, A."],
            },
            "payload_type": "csv",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_id"] == "test_upload_1"
        assert "field_profiles" in data
        assert "semantic_candidates" in data

    def test_get_profile_not_found(self, client, auth_headers):
        resp = client.get("/sources/nonexistent/profile", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_profile_after_create(self, client, auth_headers):
        client.post("/sources/profile", json={
            "source_id": "test_get_1",
            "field_names": ["name"],
            "sample_values": {"name": ["Alice", "Bob"]},
        }, headers=auth_headers)
        resp = client.get("/sources/test_get_1/profile", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["source_id"] == "test_get_1"

    def test_get_candidates(self, client, auth_headers):
        client.post("/sources/profile", json={
            "source_id": "cand_test",
            "field_names": ["orcid"],
            "sample_values": {"orcid": ["0000-0001-2345-6789"]},
        }, headers=auth_headers)
        resp = client.get("/sources/cand_test/candidates", headers=auth_headers)
        assert resp.status_code == 200
        assert "candidate_identifiers" in resp.json()

    def test_create_requires_auth(self, client):
        resp = client.post("/sources/profile", json={
            "source_id": "x",
            "field_names": ["a"],
            "sample_values": {"a": ["1"]},
        })
        assert resp.status_code == 401

    def test_create_requires_editor(self, client, viewer_headers):
        resp = client.post("/sources/profile", json={
            "source_id": "x",
            "field_names": ["a"],
            "sample_values": {"a": ["1"]},
        }, headers=viewer_headers)
        assert resp.status_code == 403


class TestMappingSuggestionsAPI:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/mapping-suggestions", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_accept_not_found(self, client, auth_headers):
        resp = client.post("/mapping-suggestions/999/accept", headers=auth_headers)
        assert resp.status_code == 404

    def test_reject_not_found(self, client, auth_headers):
        resp = client.post(
            "/mapping-suggestions/999/reject",
            json={"rationale": "Not relevant"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_reject_requires_rationale(self, client, auth_headers):
        resp = client.post(
            "/mapping-suggestions/1/reject",
            json={"rationale": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_list_requires_auth(self, client):
        resp = client.get("/mapping-suggestions")
        assert resp.status_code == 401

    def test_accept_requires_editor(self, client, viewer_headers):
        resp = client.post("/mapping-suggestions/1/accept", headers=viewer_headers)
        assert resp.status_code == 403

    def test_bulk_accept_suggestions(self, client, auth_headers, db_session):
        suggestions = [
            models.MappingSuggestionRecord(
                source_id=f"source:{idx}",
                source_schema="csv",
                source_field=f"Field {idx}",
                canonical_target="canonical_id",
                confidence=0.8,
                status="review_required",
                evidence_samples='["sample"]',
                evidence='["test"]',
            )
            for idx in range(2)
        ]
        db_session.add_all(suggestions)
        db_session.commit()
        ids = [suggestion.id for suggestion in suggestions]

        resp = client.post("/mapping-suggestions/bulk/accept", json={
            "suggestion_ids": ids + [9999],
        }, headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json() == {"action": "accept", "reviewed": 2, "not_found": [9999]}
        db_session.expire_all()
        statuses = [
            db_session.get(models.MappingSuggestionRecord, suggestion_id).status
            for suggestion_id in ids
        ]
        assert statuses == ["accepted", "accepted"]

    def test_bulk_reject_requires_rationale(self, client, auth_headers):
        resp = client.post("/mapping-suggestions/bulk/reject", json={
            "suggestion_ids": [1, 2],
            "rationale": "",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_list_includes_field_correspondence_metadata(self, client, auth_headers, db_session):
        from backend.services.mapping_suggestions import MappingSuggestionService
        from backend.services.source_profiler import FieldProfile, SourceProfile

        service = MappingSuggestionService(db=db_session)
        service.generate_suggestions(SourceProfile(
            source_id="wos-src",
            source_format="wos",
            total_rows=10,
            field_profiles=[
                FieldProfile(field_name="DI", sample_values=["10.1000/example"]),
            ],
        ))
        db_session.commit()

        resp = client.get("/mapping-suggestions", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["canonical_target"] == "canonical_id"
        assert data[0]["semantic_concept"] == "persistent_identifier"
        assert data[0]["identifier_scheme"] == "doi"
        assert "wos_schema_rule" in data[0]["evidence"]
        assert data[0]["requires_review"] is False

    def test_accept_persists_field_correspondence_rule(self, client, auth_headers, db_session):
        from backend import models
        from backend.services.mapping_suggestions import MappingSuggestionService
        from backend.services.source_profiler import FieldProfile, SourceProfile

        service = MappingSuggestionService(db=db_session)
        suggestion = service.generate_suggestions(SourceProfile(
            source_id="wos-src",
            source_format="wos",
            total_rows=10,
            field_profiles=[
                FieldProfile(field_name="DI", sample_values=["10.1000/example"]),
            ],
        ))[0]
        db_session.commit()

        resp = client.post(f"/mapping-suggestions/{suggestion.id}/accept", headers=auth_headers)

        assert resp.status_code == 200
        rule = db_session.query(models.FieldCorrespondenceRule).filter_by(source_field="DI").one()
        assert rule.canonical_target == "canonical_id"
        assert rule.identifier_scheme == "doi"
        assert rule.is_active is True


class TestFieldCorrespondenceRulesAPI:
    def test_create_and_list_rule(self, client, auth_headers):
        payload = {
            "source_schema": "wos",
            "source_field": "ID",
            "canonical_target": "canonical_id",
            "semantic_concept": "persistent_identifier",
            "identifier_scheme": "local",
            "confidence": 1.0,
            "evidence": ["manual_admin_rule"],
        }
        create = client.post("/field-correspondence-rules", json=payload, headers=auth_headers)
        assert create.status_code == 201
        created = create.json()
        assert created["source_field"] == "ID"
        assert created["identifier_scheme"] == "local"
        assert created["is_active"] is True

        listed = client.get("/field-correspondence-rules?source_schema=wos&active=true", headers=auth_headers)
        assert listed.status_code == 200
        data = listed.json()
        assert len(data) == 1
        assert data[0]["canonical_target"] == "canonical_id"
        assert "manual_admin_rule" in data[0]["evidence"]

    def test_rule_create_writes_audit_log(self, client, auth_headers, db_session):
        resp = client.post("/field-correspondence-rules", json={
            "source_schema": "wos",
            "source_field": "ID",
            "canonical_target": "canonical_id",
            "semantic_concept": "persistent_identifier",
            "identifier_scheme": "local",
        }, headers=auth_headers)

        assert resp.status_code == 201
        audit = db_session.query(models.AuditLog).filter_by(
            entity_type="field_correspondence_rule",
            action="CREATE",
        ).one()
        import json
        details = json.loads(audit.details)
        assert details["before"] is None
        assert details["after"]["source_field"] == "ID"
        assert details["after"]["canonical_target"] == "canonical_id"
        assert audit.username == "testadmin"

    def test_governance_metrics_summarize_rules_and_suggestions(self, client, auth_headers, db_session):
        active_rule = models.FieldCorrespondenceRule(
            source_schema="wos",
            source_field="DI",
            canonical_target="canonical_id",
            is_active=True,
        )
        inactive_rule = models.FieldCorrespondenceRule(
            source_schema="ris",
            source_field="DO",
            canonical_target="canonical_id",
            is_active=False,
        )
        suggestions = [
            models.MappingSuggestionRecord(
                source_id="wos:1",
                source_schema="wos",
                source_field="ID",
                canonical_target="canonical_id",
                confidence=0.7,
                status="review_required",
            ),
            models.MappingSuggestionRecord(
                source_id="wos:2",
                source_schema="wos",
                source_field="UT",
                canonical_target="canonical_id",
                confidence=0.7,
                status="auto_acceptable",
            ),
            models.MappingSuggestionRecord(
                source_id="ris:1",
                source_schema="ris",
                source_field="XX",
                canonical_target="canonical_id",
                confidence=0.4,
                status="rejected",
            ),
        ]
        db_session.add_all([active_rule, inactive_rule, *suggestions])
        db_session.commit()

        resp = client.get("/field-correspondence-rules/governance-metrics", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["active_rules"] == 1
        assert data["inactive_rules"] == 1
        assert data["pending_suggestions"] == 2
        assert data["rejected_false_positives"] == 1
        assert data["ambiguous_sources"][0] == {"source_schema": "wos", "pending_suggestions": 2}

    def test_seed_preventive_rules_creates_inactive_candidates(self, client, auth_headers, db_session):
        resp = client.post("/field-correspondence-rules/preventive-seed", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] > 0
        assert data["total_candidates"] == data["created"]
        doi_rule = db_session.query(models.FieldCorrespondenceRule).filter_by(
            source_schema="wos",
            source_field="DI",
        ).one()
        assert doi_rule.canonical_target == "canonical_id"
        assert doi_rule.identifier_scheme == "doi"
        assert doi_rule.is_active is False

        again = client.post("/field-correspondence-rules/preventive-seed", headers=auth_headers)
        assert again.status_code == 200
        assert again.json()["created"] == 0
        assert again.json()["updated"] == data["total_candidates"]

    def test_evidence_scores_prioritize_rules_with_records_and_suggestions(self, client, auth_headers, db_session):
        rule = models.FieldCorrespondenceRule(
            source_schema="wos",
            source_field="ID",
            canonical_target="canonical_id",
            identifier_scheme="local",
            is_active=False,
        )
        entity = models.RawEntity(
            primary_label="Imported candidate",
            canonical_id=None,
            normalized_json='{"ID": "LOCAL-42"}',
            attributes_json="{}",
            import_batch_id=7,
        )
        suggestion = models.MappingSuggestionRecord(
            source_id="import_batch:7",
            source_schema="wos",
            source_field="ID",
            canonical_target="canonical_id",
            confidence=0.78,
            status="review_required",
        )
        db_session.add_all([rule, entity, suggestion])
        db_session.commit()

        resp = client.get("/field-correspondence-rules/evidence-scores?active=false", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        scored = next(item for item in data if item["rule_id"] == rule.id)
        assert scored["score"] == "medium"
        assert scored["affected_records"] == 1
        assert scored["matching_suggestions"] == 1
        assert scored["sample_values"] == ["LOCAL-42"]

    def test_preview_rule_impact_counts_records_and_suggestions(self, client, auth_headers, db_session):
        from backend import models

        entity = models.RawEntity(
            primary_label="Imported candidate",
            canonical_id=None,
            normalized_json='{"ID": "LOCAL-42"}',
            attributes_json="{}",
            import_batch_id=7,
        )
        suggestion = models.MappingSuggestionRecord(
            source_id="import_batch:7",
            source_schema="wos",
            source_field="ID",
            canonical_target="canonical_id",
            confidence=0.78,
            status="review_required",
            evidence_samples='["LOCAL-42"]',
            evidence='["generic_identifier_header"]',
        )
        db_session.add_all([entity, suggestion])
        db_session.commit()

        resp = client.post("/field-correspondence-rules/impact", json={
            "source_schema": "wos",
            "source_field": "ID",
            "canonical_target": "canonical_id",
            "semantic_concept": "persistent_identifier",
            "identifier_scheme": "local",
        }, headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["affected_records"] == 1
        assert data["affected_import_batches"] == 1
        assert data["matching_suggestions"] == 1
        assert data["examples"][0]["current_value"] == "LOCAL-42"

    def test_deactivate_and_reactivate_rule(self, client, auth_headers):
        create = client.post("/field-correspondence-rules", json={
            "source_schema": "ris",
            "source_field": "DO",
            "canonical_target": "canonical_id",
            "identifier_scheme": "doi",
        }, headers=auth_headers)
        assert create.status_code == 201
        rule_id = create.json()["id"]

        off = client.post(f"/field-correspondence-rules/{rule_id}/deactivate", headers=auth_headers)
        assert off.status_code == 200
        assert off.json()["is_active"] is False

        on = client.post(f"/field-correspondence-rules/{rule_id}/reactivate", headers=auth_headers)
        assert on.status_code == 200
        assert on.json()["is_active"] is True

    def test_update_rule(self, client, auth_headers):
        create = client.post("/field-correspondence-rules", json={
            "source_schema": "csv",
            "source_field": "Identifier",
            "canonical_target": "canonical_id",
            "identifier_scheme": "local",
        }, headers=auth_headers)
        assert create.status_code == 201
        rule_id = create.json()["id"]

        update = client.patch(f"/field-correspondence-rules/{rule_id}", json={
            "source_schema": "csv",
            "source_field": "Identifier",
            "canonical_target": "canonical_id",
            "semantic_concept": "persistent_identifier",
            "identifier_scheme": "doi",
            "confidence": 0.99,
            "evidence": ["corrected_admin_rule"],
        }, headers=auth_headers)

        assert update.status_code == 200
        data = update.json()
        assert data["identifier_scheme"] == "doi"
        assert data["confidence"] == 0.99
        assert "corrected_admin_rule" in data["evidence"]

    def test_rule_update_and_deactivate_write_audit_before_after(self, client, auth_headers, db_session):
        import json

        create = client.post("/field-correspondence-rules", json={
            "source_schema": "csv",
            "source_field": "Identifier",
            "canonical_target": "canonical_id",
            "identifier_scheme": "local",
        }, headers=auth_headers)
        assert create.status_code == 201
        rule_id = create.json()["id"]

        update = client.patch(f"/field-correspondence-rules/{rule_id}", json={
            "source_schema": "csv",
            "source_field": "Identifier",
            "canonical_target": "canonical_id",
            "semantic_concept": "persistent_identifier",
            "identifier_scheme": "doi",
            "confidence": 0.99,
            "evidence": ["corrected_admin_rule"],
        }, headers=auth_headers)
        assert update.status_code == 200

        off = client.post(f"/field-correspondence-rules/{rule_id}/deactivate", headers=auth_headers)
        assert off.status_code == 200

        audits = db_session.query(models.AuditLog).filter_by(
            entity_type="field_correspondence_rule",
        ).order_by(models.AuditLog.id.asc()).all()
        assert [audit.action for audit in audits] == ["CREATE", "UPDATE", "DEACTIVATE"]

        update_details = json.loads(audits[1].details)
        assert update_details["before"]["identifier_scheme"] == "local"
        assert update_details["after"]["identifier_scheme"] == "doi"

        deactivate_details = json.loads(audits[2].details)
        assert deactivate_details["before"]["is_active"] is True
        assert deactivate_details["after"]["is_active"] is False

    def test_rule_audit_endpoint_returns_history(self, client, auth_headers):
        create = client.post("/field-correspondence-rules", json={
            "source_schema": "csv",
            "source_field": "Identifier",
            "canonical_target": "canonical_id",
            "identifier_scheme": "local",
        }, headers=auth_headers)
        assert create.status_code == 201
        rule_id = create.json()["id"]

        update = client.patch(f"/field-correspondence-rules/{rule_id}", json={
            "source_schema": "csv",
            "source_field": "Identifier",
            "canonical_target": "canonical_id",
            "identifier_scheme": "doi",
        }, headers=auth_headers)
        assert update.status_code == 200

        resp = client.get(f"/field-correspondence-rules/{rule_id}/audit", headers=auth_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert [entry["action"] for entry in data[:2]] == ["UPDATE", "CREATE"]
        assert data[0]["before"]["identifier_scheme"] == "local"
        assert data[0]["after"]["identifier_scheme"] == "doi"

    def test_apply_rule_defaults_to_dry_run_then_updates_existing_records(self, client, auth_headers, db_session):
        entity = models.RawEntity(
            primary_label="Imported candidate",
            canonical_id=None,
            normalized_json='{"ID": "LOCAL-42"}',
            attributes_json="{}",
            import_batch_id=7,
        )
        db_session.add(entity)
        db_session.commit()

        create = client.post("/field-correspondence-rules", json={
            "source_schema": "wos",
            "source_field": "ID",
            "canonical_target": "canonical_id",
            "identifier_scheme": "local",
        }, headers=auth_headers)
        assert create.status_code == 201
        rule_id = create.json()["id"]

        preview = client.post(f"/field-correspondence-rules/{rule_id}/apply", json={
            "dry_run": True,
        }, headers=auth_headers)
        assert preview.status_code == 200
        assert preview.json()["updated_records"] == 1
        db_session.expire_all()
        assert db_session.get(models.RawEntity, entity.id).canonical_id is None

        apply = client.post(f"/field-correspondence-rules/{rule_id}/apply", json={
            "dry_run": False,
        }, headers=auth_headers)

        assert apply.status_code == 200
        data = apply.json()
        assert data["affected_records"] == 1
        assert data["updated_records"] == 1
        db_session.expire_all()
        assert db_session.get(models.RawEntity, entity.id).canonical_id == "LOCAL-42"

        audit = db_session.query(models.AuditLog).filter_by(
            entity_type="field_correspondence_rule",
            action="APPLY",
        ).one()
        assert audit.entity_id == rule_id
        job = db_session.query(models.HarmonizationLog).filter_by(
            step_id=f"field_correspondence_rule:{rule_id}",
        ).one()
        assert job.records_updated == 1
        assert job.reverted is False

    def test_field_correspondence_jobs_and_rollback(self, client, auth_headers, db_session):
        entity = models.RawEntity(
            primary_label="Imported candidate",
            canonical_id=None,
            normalized_json='{"ID": "LOCAL-42"}',
            attributes_json="{}",
            import_batch_id=7,
        )
        db_session.add(entity)
        db_session.commit()

        create = client.post("/field-correspondence-rules", json={
            "source_schema": "wos",
            "source_field": "ID",
            "canonical_target": "canonical_id",
            "identifier_scheme": "local",
        }, headers=auth_headers)
        assert create.status_code == 201
        rule_id = create.json()["id"]

        apply = client.post(f"/field-correspondence-rules/{rule_id}/apply", json={
            "dry_run": False,
        }, headers=auth_headers)
        assert apply.status_code == 200
        job_id = apply.json()["job_id"]

        jobs = client.get("/field-correspondence-rules/jobs", headers=auth_headers)
        assert jobs.status_code == 200
        data = jobs.json()
        assert data[0]["id"] == job_id
        assert data[0]["rule_id"] == rule_id
        assert data[0]["records_updated"] == 1
        assert data[0]["username"] == "testadmin"
        assert data[0]["reverted"] is False

        rollback = client.post(f"/field-correspondence-rules/jobs/{job_id}/rollback", headers=auth_headers)
        assert rollback.status_code == 200
        assert rollback.json()["records_restored"] == 1
        db_session.expire_all()
        assert db_session.get(models.RawEntity, entity.id).canonical_id is None

        jobs_after = client.get("/field-correspondence-rules/jobs", headers=auth_headers)
        assert jobs_after.json()[0]["reverted"] is True

    def test_create_requires_admin(self, client, viewer_headers):
        resp = client.post("/field-correspondence-rules", json={
            "source_field": "ID",
            "canonical_target": "canonical_id",
        }, headers=viewer_headers)
        assert resp.status_code == 403


class TestAuthorityReadinessAPI:
    def test_get_readiness(self, client, auth_headers):
        resp = client.get("/governance/authority-readiness/dataset_1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset_id"] == "dataset_1"
        assert data["state"] == "not_started"
        assert "families" in data

    def test_readiness_requires_auth(self, client):
        resp = client.get("/governance/authority-readiness/x")
        assert resp.status_code == 401


class TestJSONLDExportAPI:
    def test_export_not_found(self, client, auth_headers):
        resp = client.get("/exports/99999/jsonld", headers=auth_headers)
        assert resp.status_code == 404

    def test_export_invalid_vocabulary(self, client, auth_headers):
        resp = client.get("/exports/1/jsonld?vocabulary=invalid", headers=auth_headers)
        assert resp.status_code == 422

    def test_export_requires_auth(self, client):
        resp = client.get("/exports/1/jsonld")
        assert resp.status_code == 401
