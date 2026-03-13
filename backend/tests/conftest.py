"""
Shared pytest fixtures for UKIP backend tests.
Uses an isolated in-memory SQLite database so tests never touch sql_app.db.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Use a clean in-memory DB for every test session ────────────────────────
# StaticPool ensures all sessions/connections share the SAME in-memory database.
TEST_DATABASE_URL = "sqlite:///:memory:"

# Patch the database URL before importing app modules.
# ADMIN_PASSWORD is the plain-text password used to bootstrap the super_admin
# on first startup. ADMIN_USERNAME identifies the account.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_USERNAME", "testadmin")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword")


from sqlalchemy import text  # noqa: E402
from backend import models, database  # noqa: E402 — env vars must be set first
from backend.main import app  # noqa: E402

# Override the database engine with the in-memory one
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create tables in the in-memory DB
models.Base.metadata.create_all(bind=test_engine)

# Override dependency — imported from database to match auth.py's import
from backend.database import get_db  # noqa: E402
app.dependency_overrides[get_db] = override_get_db

# Override the session factory used by AuditMiddleware so it writes to the
# same in-memory DB that tests read from via override_get_db.
import backend.audit as _audit_module  # noqa: E402
_audit_module.SessionLocal = TestingSessionLocal

# Seed the super_admin in the in-memory test DB so the login fixture works.
# (The lifespan bootstrap uses database.SessionLocal which hits the real DB;
#  this seeds the in-memory DB that test requests use via override_get_db.)
from backend.auth import hash_password as _hash_pw  # noqa: E402
with TestingSessionLocal() as _seed_db:
    if _seed_db.query(models.User).count() == 0:
        _seed_db.add(models.User(
            username=os.environ["ADMIN_USERNAME"],
            password_hash=_hash_pw(os.environ["ADMIN_PASSWORD"]),
            role="super_admin",
            is_active=True,
        ))
        _seed_db.commit()


@pytest.fixture(scope="session")
def client():
    """FastAPI test client with in-memory DB."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def auth_token(client):
    """Obtain a valid JWT token for the super_admin test account."""
    response = client.post(
        "/auth/token",
        data={"username": "testadmin", "password": "testpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, f"Auth failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="session")
def session_factory():
    """Expose the test SessionLocal factory as a fixture so test files
    don't need to import it from conftest (which causes conftest to be
    loaded a second time as 'backend.tests.conftest' module, creating a
    separate in-memory DB and overriding app.dependency_overrides)."""
    return TestingSessionLocal


# ── RBAC test users ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def editor_headers(client, auth_headers):
    """Create an editor user and return its auth headers (session-scoped).
    Token is generated directly (bypasses rate-limited /auth/token endpoint)."""
    from backend.auth import create_access_token as _cat
    resp = client.post(
        "/users",
        json={"username": "test_editor", "password": "editor1234", "role": "editor"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"Editor creation failed: {resp.text}"
    token = _cat(subject="test_editor", role="editor")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def viewer_headers(client, auth_headers):
    """Create a viewer user and return its auth headers (session-scoped).
    Token is generated directly (bypasses rate-limited /auth/token endpoint)."""
    from backend.auth import create_access_token as _cat
    resp = client.post(
        "/users",
        json={"username": "test_viewer", "password": "viewer1234", "role": "viewer"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"Viewer creation failed: {resp.text}"
    token = _cat(subject="test_viewer", role="viewer")
    return {"Authorization": f"Bearer {token}"}


# ── DB cleanup (function-scoped) ────────────────────────────────────────────

_TABLES_TO_CLEAN = [
    "raw_entities",
    "store_connections",
    "store_sync_mappings",
    "sync_logs",
    "sync_queue",
    "ai_integrations",
    "normalization_rules",
    "harmonization_logs",
    "harmonization_change_records",
    "authority_records",
    "annotations",
    "notification_settings",
    "branding_settings",
    "artifact_templates",
    "analysis_contexts",
    "audit_logs",
    # Note: "users" is intentionally excluded — the super_admin/editor/viewer
    # test accounts must persist across the entire test session.
]


@pytest.fixture()
def db_session():
    """
    Provide a DB session for each test, with table cleanup BEFORE and AFTER.

    Pre-test cleanup guarantees a known-clean state even when a prior test's
    endpoint created records outside the fixture's own session (e.g. via
    override_get_db).  Post-test cleanup keeps the DB tidy for tests that
    do NOT use this fixture.
    """
    # ── Pre-test cleanup ──────────────────────────────────────────────
    pre = TestingSessionLocal()
    try:
        for table in _TABLES_TO_CLEAN:
            pre.execute(text(f"DELETE FROM {table}"))
        pre.commit()
    finally:
        pre.close()

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # ── Post-test cleanup ─────────────────────────────────────────
        cleanup_db = TestingSessionLocal()
        try:
            for table in _TABLES_TO_CLEAN:
                cleanup_db.execute(text(f"DELETE FROM {table}"))
            cleanup_db.commit()
        finally:
            cleanup_db.close()
