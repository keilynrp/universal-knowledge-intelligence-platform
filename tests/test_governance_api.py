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
    db.query(models.FieldCorrespondenceRule).delete()
    db.query(models.MappingSuggestionRecord).delete()
    db.commit()
    db.close()
    yield
    gov_mod._mapping_service = None
    db = _TestSession()
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
