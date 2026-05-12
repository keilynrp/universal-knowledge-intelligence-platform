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
os.environ.setdefault("ENCRYPTION_KEY", "vRHc0zVcTXbRfUBZEsKNal2lMCfINwDh90EXE8vu2Ew=")
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("UKIP_DB_MODE", "sqlite")
os.environ.setdefault("UKIP_SKIP_STARTUP_SIDE_EFFECTS", "1")
os.environ.setdefault("SENTRY_ENABLED", "0")


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

# FTS5 virtual table (not in ORM metadata — must be created manually)
with test_engine.connect() as _fts_conn:
    _fts_conn.execute(text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index
        USING fts5(
            doc_type,
            doc_id   UNINDEXED,
            title,
            body,
            href     UNINDEXED
        )
    """))
    _fts_conn.commit()

# Override dependency — imported from database to match auth.py's import
from backend.database import get_db  # noqa: E402
app.dependency_overrides[get_db] = override_get_db

# Rebind module-level engine/session factories that were captured at import
# time so analytics helpers and background threads use the shared test DB.
database.engine = test_engine
database.SessionLocal = TestingSessionLocal

# Override modules that imported engine/SessionLocal directly.
import backend.audit as _audit_module  # noqa: E402
import backend.analyzers.author_metrics as _author_metrics_module  # noqa: E402
import backend.analyzers.coauthorship as _coauthorship_module  # noqa: E402
import backend.analyzers.correlation as _correlation_module  # noqa: E402
import backend.analyzers.geographic as _geographic_module  # noqa: E402
import backend.analyzers.topic_modeling as _topic_modeling_module  # noqa: E402
import backend.olap as _olap_module  # noqa: E402
import backend.routers.analytics as _analytics_router  # noqa: E402
_audit_module.SessionLocal = TestingSessionLocal
_author_metrics_module.engine = test_engine
_coauthorship_module.engine = test_engine
_correlation_module.engine = test_engine
_geographic_module.engine = test_engine
_topic_modeling_module.engine = test_engine
_olap_module.engine = test_engine

# Seed the super_admin in the in-memory test DB so the login fixture works.
# Startup side effects are disabled in tests, so seeding must happen explicitly.
from backend.auth import hash_password as _hash_pw  # noqa: E402


def _ensure_test_admin() -> None:
    """Keep the session-scoped CI admin deterministic across test ordering."""
    with TestingSessionLocal() as db:
        admin = (
            db.query(models.User)
            .filter(models.User.username == os.environ["ADMIN_USERNAME"])
            .first()
        )
        if admin is None:
            db.add(models.User(
                username=os.environ["ADMIN_USERNAME"],
                password_hash=_hash_pw(os.environ["ADMIN_PASSWORD"]),
                role="super_admin",
                is_active=True,
                failed_attempts=0,
                locked_until=None,
            ))
        else:
            admin.password_hash = _hash_pw(os.environ["ADMIN_PASSWORD"])
            admin.role = "super_admin"
            admin.is_active = True
            admin.failed_attempts = 0
            admin.locked_until = None
        db.commit()


with TestingSessionLocal() as _seed_db:
    if _seed_db.query(models.User).count() == 0:
        _seed_db.add(models.User(
            username=os.environ["ADMIN_USERNAME"],
            password_hash=_hash_pw(os.environ["ADMIN_PASSWORD"]),
            role="super_admin",
            is_active=True,
        ))
        _seed_db.commit()
_ensure_test_admin()


@pytest.fixture(scope="session")
def client():
    """FastAPI test client with in-memory DB."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def auth_token():
    """Create a fresh JWT token for the deterministic super_admin test account."""
    _ensure_test_admin()
    from backend.auth import create_access_token as _cat
    return _cat(subject=os.environ["ADMIN_USERNAME"], role="super_admin")


@pytest.fixture()
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

def _ensure_role_user(username: str, role: str) -> None:
    with TestingSessionLocal() as db:
        user = db.query(models.User).filter(models.User.username == username).first()
        if user is None:
            db.add(models.User(
                username=username,
                password_hash=_hash_pw(f"{role}1234"),
                role=role,
                is_active=True,
                failed_attempts=0,
                locked_until=None,
            ))
        else:
            user.password_hash = _hash_pw(f"{role}1234")
            user.role = role
            user.is_active = True
            user.failed_attempts = 0
            user.locked_until = None
        db.commit()


@pytest.fixture()
def editor_headers():
    """Create an editor user and return fresh auth headers."""
    from backend.auth import create_access_token as _cat
    _ensure_role_user("test_editor", "editor")
    token = _cat(subject="test_editor", role="editor")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def viewer_headers():
    """Create a viewer user and return fresh auth headers."""
    from backend.auth import create_access_token as _cat
    _ensure_role_user("test_viewer", "viewer")
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
    "authority_record_links",
    "authority_records",
    "annotations",
    "notification_settings",
    "branding_settings",
    "artifact_templates",
    "analysis_contexts",
    "audit_logs",
    "alert_channels",
    "search_index",
    "link_dismissals",
    "user_notification_states",
    "user_notification_reads",
    "webhook_deliveries",
    "webhooks",
    "scheduled_imports",
    "scheduled_reports",
    "web_scraper_configs",
    "workflow_runs",
    "workflows",
    "catalog_portals",
    "import_batches",
    "organization_members",
    "organizations",
    "entity_relationships",
    # Note: "users" is intentionally excluded — the super_admin/editor/viewer
    # test accounts must persist across the entire test session.
]


def _reset_test_state(db):
    for table in _TABLES_TO_CLEAN:
        db.execute(text(f"DELETE FROM {table}"))
    db.execute(text("UPDATE users SET org_id = NULL"))
    db.commit()


@pytest.fixture(autouse=True)
def isolate_test_state():
    """Isolate endpoint tests that do not explicitly request db_session."""
    _analytics_router._analytics_cache.invalidate()
    _analytics_router._dashboard_cache.invalidate()
    pre = TestingSessionLocal()
    try:
        _reset_test_state(pre)
    finally:
        pre.close()

    yield

    _analytics_router._analytics_cache.invalidate()
    _analytics_router._dashboard_cache.invalidate()
    post = TestingSessionLocal()
    try:
        _reset_test_state(post)
    finally:
        post.close()


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
        _reset_test_state(pre)
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
            _reset_test_state(cleanup_db)
        finally:
            cleanup_db.close()
