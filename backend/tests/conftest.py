"""
Shared pytest fixtures for UKIP backend tests.
Supports both SQLite (local dev) and PostgreSQL (CI / production parity).
"""
import os
from contextlib import contextmanager
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Determine test DB mode ──────────────────────────────────────────────────
# CI sets UKIP_DB_MODE=postgres + DATABASE_URL=postgresql://...
# Local dev defaults to SQLite in-memory.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_USERNAME", "testadmin")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword")
os.environ.setdefault("ENCRYPTION_KEY", "vRHc0zVcTXbRfUBZEsKNal2lMCfINwDh90EXE8vu2Ew=")
os.environ.setdefault("UKIP_DB_MODE", "sqlite")
os.environ.setdefault("UKIP_SKIP_STARTUP_SIDE_EFFECTS", "1")
os.environ.setdefault("SENTRY_ENABLED", "0")
# Coauthorship V2 flags default ON in production (F5 cutover); pin them OFF for
# tests so suites are deterministic and opt in per-case via write_on/read_on.
os.environ.setdefault("COAUTHOR_V2_WRITE", "false")
os.environ.setdefault("COAUTHOR_V2_READ", "false")
os.environ.setdefault("COAUTHOR_V2_SHADOW", "false")

_DB_MODE = os.environ.get("UKIP_DB_MODE", "sqlite").lower()
_IS_POSTGRES = _DB_MODE == "postgres"


if _IS_POSTGRES:
    _TEST_DB_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://ukip_test:ukip_test_pw@localhost:5432/ukip_test",
    )
    os.environ["DATABASE_URL"] = _TEST_DB_URL
else:
    _TEST_DB_URL = "sqlite:///:memory:"
    os.environ.setdefault("DATABASE_URL", _TEST_DB_URL)


from backend import models, database  # noqa: E402 — env vars must be set first
from backend.main import app  # noqa: E402

# ── Create the test engine ──────────────────────────────────────────────────
if _IS_POSTGRES:
    test_engine = create_engine(_TEST_DB_URL, pool_pre_ping=True)
else:
    test_engine = create_engine(
        _TEST_DB_URL,
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


# ── Create tables ───────────────────────────────────────────────────────────
if _IS_POSTGRES:
    # Clean slate each run. Drop the *schema*, not the tables: `organizations`
    # and `users` reference each other, and `metadata.drop_all()` cannot order
    # the DROPs around that cycle — it raises CircularDependencyError before a
    # single test runs, so the suite only ever worked against a brand-new
    # database. CI got one per run and never noticed; locally it made the whole
    # PostgreSQL mode single-shot.
    with test_engine.begin() as _reset_conn:
        _reset_conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        _reset_conn.execute(text("CREATE SCHEMA public"))

models.Base.metadata.create_all(bind=test_engine)

# search_index: FTS5 on SQLite, regular table with GIN on PostgreSQL
with test_engine.connect() as _fts_conn:
    if _IS_POSTGRES:
        _fts_conn.execute(text("""
            CREATE TABLE IF NOT EXISTS search_index (
                doc_type TEXT,
                doc_id   INTEGER,
                title    TEXT,
                body     TEXT,
                href     TEXT
            )
        """))
        _fts_conn.execute(text("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = 'search_index'
                      AND indexname = 'ix_search_index_vector'
                ) THEN
                    CREATE INDEX ix_search_index_vector
                    ON search_index
                    USING GIN (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body,'')));
                END IF;
            END $$
        """))
    else:
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

# Seed the super_admin in the test DB so the login fixture works.
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


# ── Canonical tenants ───────────────────────────────────────────────────────
# Tests across the suite scope rows with small literal org ids (`org_id=1`,
# `org=2`) without creating the tenant. SQLite does not enforce foreign keys by
# default, so those rows inserted happily; PostgreSQL rejects them and 95
# violations surfaced across eight constraints the first time the suite was run
# against the dialect production uses.
#
# Seeding the tenants those literals refer to fixes the cause rather than each
# call site. Nothing in the suite queries or counts Organization, so
# materialising them changes no existing assertion.
#
# The set is measured, not guessed — a first attempt at range(1, 11) missed
# `org_id=12` and failed. Regenerate with:
#
#   grep -rhoE "org_id=-?[0-9]+|org=-?[0-9]+" backend/tests/ | grep -oE "\-?[0-9]+$" | sort -nu
#
# Three entries look like sentinels and still need to exist:
#   0     — "legacy/global scope" in the analyzer suites, a real scope value
#   -1    — `tenant_access.LEGACY_GLOBAL_ORG_ID`. Production uses it only as a
#           *read* scope (`scope_query_to_org`) and never writes it to a column,
#           so materialising it here masks no production constraint issue; the
#           journal-scope test does write it, which PostgreSQL then checks.
# 99999 is deliberately NOT seeded: `test_sprint85` asserts that fetching and
# switching to org 99999 returns 404, so it has to stay nonexistent. Seeding it
# turned those two into 200s — caught only by the full suite, after the affected
# files alone had gone green. A test needing "a different tenant" must use a
# seeded id; the background-job tenant tests now use 42.
#
# The grep below must include the minus sign — a first pass matched `[0-9]+`
# only, missed -1, and left exactly one test failing.
#
# A test that introduces a new literal org id must add it here. That coupling is
# the price of not rewriting 41 call sites; the alternative is a fixture per
# file, which duplicates this list eight times instead.
_CANONICAL_ORG_IDS = (-1, 0, 1, 2, 5, 7, 9, 12, 42, 99)
_ORG_OWNER_USERNAME = "canonical-org-owner"


def _seed_canonical_orgs(db) -> None:
    """(Re)create the canonical tenants on *db*, leaving existing rows alone.

    Called from `_reset_test_state` as well as at import: that reset truncates
    `organizations`, so seeding only once at import would last exactly until the
    first test that uses the `db_session` fixture.
    """
    # A dedicated owner, deliberately not the super_admin: the bootstrap tests
    # delete every super_admin row, and an organization owning one would block
    # that delete on `organizations_owner_id_fkey`. This user is not a
    # super_admin and no test deletes it. Nothing in the suite counts users.
    owner = (
        db.query(models.User)
        .filter(models.User.username == _ORG_OWNER_USERNAME)
        .first()
    )
    if owner is None:
        owner = models.User(
            username=_ORG_OWNER_USERNAME,
            password_hash=_hash_pw("canonical-org-owner-not-for-login"),
            role="viewer",
            is_active=False,
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

    existing = {row.id for row in db.query(models.Organization.id).all()}
    missing = [org_id for org_id in _CANONICAL_ORG_IDS if org_id not in existing]
    if not missing:
        return
    for org_id in missing:
        db.add(models.Organization(
            id=org_id,
            name=f"Test Org {org_id}",
            slug=f"test-org-{org_id}",
            owner_id=owner.id,
            is_active=True,
        ))
    db.commit()
    if _IS_POSTGRES:
        # Explicit ids bypass the sequence, so a later insert that omits id
        # would collide on the primary key. SQLite has no such sequence.
        db.execute(text(
            "SELECT setval('organizations_id_seq', "
            "(SELECT COALESCE(MAX(id), 1) FROM organizations))"
        ))
        db.commit()


with TestingSessionLocal() as _org_seed_db:
    _seed_canonical_orgs(_org_seed_db)


@pytest.fixture(scope="session")
def client():
    """FastAPI test client with test DB."""
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
    # Durable Background Job Runtime (ADR-007) — clean before organizations (org_id FK).
    "background_jobs",
    # Retrospective Intelligence Layer (ADR-006) — append-only history.
    # ORM listeners block update/delete but raw SQL DELETE (used here) bypasses
    # them, so no trigger suspension is needed for cleanup.
    "retrospective_events",
    "retrospective_snapshots",
    # Backup and restore assurance evidence (append-only outside tests)
    "backup_assurance_events",
    # EPIC-017: secret rotation evidence — clean first (no FK deps)
    "secret_rotation_events",
    # Journal NIF + APC metrics — clean before organizations (org_id FK)
    "journal_metrics",
    # EPIC-016: lifecycle + retention — clean before organizations
    "retention_policies",
    "data_lifecycle_events",
    # V2 coauthorship tables — must be cleaned before raw_entities / authors
    "coauthor_contributions",
    "coauthor_edges",
    "author_publications",
    "author_stats",
    "author_merge_suggestions",
    "author_merge_audit",
    "coauthor_dirty_scopes",
    "authors",
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
    # ── Children of `users` ──────────────────────────────────────────────
    # `users` is excluded below, but the bootstrap tests delete every
    # super_admin row directly. Any child row left behind by an earlier test
    # blocks that delete on PostgreSQL, which enforces the foreign key SQLite
    # ignores — and it fails in the bootstrap test, on a table that test never
    # touched.
    #
    # This list is the complete set, derived from the schema rather than from
    # whichever constraint a traceback happened to name: fixing
    # `password_reset_tokens` alone just moved the failure to `api_keys`.
    # `test_conftest_cleanup_coverage.py` asserts the set stays complete, so a
    # new table with a user FK fails there instead of somewhere unrelated.
    "api_keys",
    "embed_widgets",
    "field_correspondence_rules",
    "mapping_suggestions",
    "password_reset_tokens",
    "source_profiles",
    "user_dashboards",
    "organization_members",
    "organizations",
    "entity_relationships",
    "concept_nodes",
    # Note: "users" is intentionally excluded — the super_admin/editor/viewer
    # test accounts must persist across the entire test session.
]


@contextmanager
def _backup_assurance_test_cleanup(db):
    """Suspend append-only triggers only for pytest full-table cleanup."""
    from backend.backup_assurance_ddl import (
        POSTGRES_CREATE_DELETE_TRIGGER,
        POSTGRES_CREATE_UPDATE_TRIGGER,
        POSTGRES_DROP_DELETE_TRIGGER,
        POSTGRES_DROP_UPDATE_TRIGGER,
        SQLITE_CREATE_DELETE_TRIGGER,
        SQLITE_CREATE_UPDATE_TRIGGER,
        SQLITE_DELETE_TRIGGER,
        SQLITE_UPDATE_TRIGGER,
    )

    if _IS_POSTGRES:
        drop_statements = (
            POSTGRES_DROP_UPDATE_TRIGGER,
            POSTGRES_DROP_DELETE_TRIGGER,
        )
        create_statements = (
            POSTGRES_CREATE_UPDATE_TRIGGER,
            POSTGRES_CREATE_DELETE_TRIGGER,
        )
    else:
        drop_statements = (
            f"DROP TRIGGER IF EXISTS {SQLITE_UPDATE_TRIGGER}",
            f"DROP TRIGGER IF EXISTS {SQLITE_DELETE_TRIGGER}",
        )
        create_statements = (
            SQLITE_CREATE_UPDATE_TRIGGER,
            SQLITE_CREATE_DELETE_TRIGGER,
        )

    for statement in drop_statements:
        db.execute(text(statement))
    try:
        yield
    finally:
        for statement in create_statements:
            db.execute(text(statement))


def _delete_test_table(db, table):
    if table == "backup_assurance_events":
        with _backup_assurance_test_cleanup(db):
            db.execute(text(f"DELETE FROM {table}"))
        return
    db.execute(text(f"DELETE FROM {table}"))


def _reset_test_state(db):
    if _IS_POSTGRES:
        # Ensure we start with a clean transaction (prior test may have left it aborted)
        try:
            db.rollback()
        except Exception:
            pass
        # PostgreSQL: use savepoints so a missing table doesn't abort the tx
        backup_table = "backup_assurance_events"
        nested = db.begin_nested()
        _delete_test_table(db, backup_table)
        nested.commit()

        for table in _TABLES_TO_CLEAN:
            if table == backup_table:
                continue
            try:
                nested = db.begin_nested()
                _delete_test_table(db, table)
                nested.commit()
            except Exception:
                nested.rollback()
        try:
            nested = db.begin_nested()
            db.execute(text("UPDATE users SET org_id = NULL"))
            nested.commit()
        except Exception:
            nested.rollback()
        db.commit()
    else:
        # SQLite: all tables exist (StaticPool in-memory), no need for savepoints
        for table in _TABLES_TO_CLEAN:
            _delete_test_table(db, table)
        db.execute(text("UPDATE users SET org_id = NULL"))
        db.commit()

    # `organizations` is in _TABLES_TO_CLEAN, so the tenants tests scope rows to
    # have just been deleted. Put them back before the next test runs, or every
    # `org_id=<n>` insert violates its foreign key on PostgreSQL.
    _seed_canonical_orgs(db)

    # Same reasoning, for the same reason, about a row this function does *not*
    # delete: the bootstrap suite deletes every super_admin to prove bootstrap
    # recreates it. Until the cleanup list was completed, PostgreSQL refused
    # those deletes on a child-row foreign key — so the suite's admin survived
    # by accident, and later tests that reference it kept working by accident
    # too. Fixing the cleanup let the deletes through and broke them
    # (`workflows_created_by_fkey`, avatar lookups, upload ownership).
    #
    # Restoring the admin here rather than in each affected test keeps the
    # invariant where the rest of the reset lives: after this function returns,
    # the deterministic accounts exist. `auth_token` also calls it, which was
    # enough only while nothing actually managed to delete the row.
    _ensure_test_admin()


def _join_webhook_dispatch_threads() -> None:
    """Join fire-and-forget webhook dispatch threads at test boundaries.

    On the StaticPool in-memory SQLite engine every session multiplexes ONE
    DBAPI connection, so a dispatch thread surviving into the next test can
    commit/rollback the shared connection mid-transaction and silently discard
    that test's in-flight writes (observed as `Could not refresh instance
    '<WorkflowRun ...>'` in test_sprint92).
    """
    from backend.routers import deps as _deps
    for t in list(_deps._webhook_dispatch_threads):
        if t.is_alive():
            t.join(timeout=15)
    _deps._webhook_dispatch_threads[:] = [
        t for t in _deps._webhook_dispatch_threads if t.is_alive()
    ]


@pytest.fixture(autouse=True)
def isolate_test_state():
    """Isolate endpoint tests that do not explicitly request db_session."""
    _join_webhook_dispatch_threads()
    _analytics_router._analytics_cache.invalidate()
    _analytics_router._dashboard_cache.invalidate()
    pre = TestingSessionLocal()
    try:
        _reset_test_state(pre)
    finally:
        pre.close()

    yield

    _join_webhook_dispatch_threads()
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


@pytest.fixture()
def db():
    """Session fixture for the coauthorship V2 engine tests (plan F2.x).

    Same semantics as ``db_session`` (StaticPool in-memory SQLite, pre-cleaned
    by the autouse ``isolate_test_state``) but exposed under the shorter name
    the V2 plan's tests request.
    """
    pre = TestingSessionLocal()
    try:
        _reset_test_state(pre)
    finally:
        pre.close()

    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def db_factory():
    """Return a factory producing fresh Sessions on the same engine.

    Caveat: UKIP's test engine uses StaticPool, so every session multiplexes a
    single SQLite connection — real OS-level concurrency is NOT exercised. This
    fixture is sufficient to verify the ``IntegrityError`` -> refetch code path
    of ``get_or_create_author`` (F2.3) but cannot prove behavior under true
    multi-process contention.
    """
    sessions = []

    def factory():
        s = TestingSessionLocal()
        sessions.append(s)
        return s

    yield factory
    for s in sessions:
        s.close()
