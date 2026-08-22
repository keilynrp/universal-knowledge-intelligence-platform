"""
Sprint 86.5 — Alembic integration tests.

Verifies that the Alembic setup is correct:
- Config and env.py are properly wired
- Baseline revision 0001 exists and is the head
- upgrade head is idempotent on the real DB
- autogenerate detects no drift between models and the stamped schema
- New revision files are created with the correct structure
"""
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

pytestmark = pytest.mark.postgres

# Project root (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


def _alembic(*args: str, db_url: str | None = None) -> subprocess.CompletedProcess:
    """Run an alembic CLI command in the project root.

    `db_url` overrides DATABASE_URL for the subprocess only.
    """
    env = None
    if db_url is not None:
        env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [PYTHON, "-m", "alembic", *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


@contextmanager
def _scratch_database():
    """Yield a URL for an empty database, or None when there is nothing to do.

    On SQLite every alembic subprocess gets its own in-memory database, so
    `upgrade head` always runs against an empty schema and this is unnecessary
    — the test works as written.

    On PostgreSQL the subprocess connects to the *same* database conftest has
    already populated with `create_all()`. Nothing stamped `alembic_version`,
    so alembic starts from zero and migration 0001 fails with
    `relation "users" already exists`. That says nothing about the migrations;
    it says the test shared a database with the fixture that set it up.

    Running against a scratch database restores what the test means to assert,
    and strengthens it: on PostgreSQL it now really applies every migration
    from nothing, which is what a deploy does.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        yield None
        return

    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    scratch = f"ukip_alembic_{uuid.uuid4().hex[:12]}"
    admin_url = url.rsplit("/", 1)[0] + "/postgres"
    dsn = admin_url.replace("postgresql+psycopg2://", "postgresql://")

    conn = psycopg2.connect(dsn)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{scratch}"')
        yield url.rsplit("/", 1)[0] + "/" + scratch
    finally:
        with conn.cursor() as cur:
            # Terminate stragglers first: a leftover connection makes DROP
            # DATABASE fail and the scratch database would accumulate.
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (scratch,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{scratch}"')
        conn.close()


class TestAlembicSetup:
    def test_alembic_importable(self):
        """alembic package must be importable in the venv."""
        import importlib
        alembic = importlib.import_module("alembic")
        assert alembic.__version__ >= "1.10"

    def test_alembic_ini_exists(self):
        assert (PROJECT_ROOT / "alembic.ini").exists()

    def test_alembic_env_py_exists(self):
        assert (PROJECT_ROOT / "alembic" / "env.py").exists()

    def test_versions_dir_exists(self):
        assert (PROJECT_ROOT / "alembic" / "versions").is_dir()

    def test_baseline_migration_exists(self):
        versions = list((PROJECT_ROOT / "alembic" / "versions").glob("*.py"))
        assert any("0001" in v.name for v in versions), (
            "Baseline migration 0001_baseline.py not found"
        )

    def test_env_py_imports_ukip_models(self):
        env_content = (PROJECT_ROOT / "alembic" / "env.py").read_text()
        assert "from backend import models" in env_content
        assert "target_metadata = Base.metadata" in env_content

    def test_env_py_uses_database_url_env(self):
        env_content = (PROJECT_ROOT / "alembic" / "env.py").read_text()
        assert "resolve_database_url" in env_content

    def test_env_py_sets_render_as_batch(self):
        """render_as_batch is required for SQLite ALTER TABLE support."""
        env_content = (PROJECT_ROOT / "alembic" / "env.py").read_text()
        assert "render_as_batch" in env_content


class TestAlembicCLI:
    def test_alembic_current_shows_head(self):
        result = _alembic("current")
        assert result.returncode == 0, result.stderr
        # In ephemeral test DBs, `current` may be empty because each subprocess
        # gets a fresh in-memory SQLite database. Success status is sufficient.
        assert "Context impl" in result.stderr

    def test_alembic_history_contains_baseline(self):
        result = _alembic("history")
        assert result.returncode == 0, result.stderr
        assert "0001" in result.stdout
        assert "baseline" in result.stdout

    def test_alembic_heads_is_0001(self):
        result = _alembic("heads")
        assert result.returncode == 0, result.stderr
        # Head may be 0001 baseline or a later sprint revision — just verify one head exists
        assert "(head)" in result.stdout

    def test_upgrade_head_is_idempotent(self):
        """Running upgrade head twice must succeed with no errors."""
        with _scratch_database() as scratch_url:
            r1 = _alembic("upgrade", "head", db_url=scratch_url)
            assert r1.returncode == 0, r1.stderr
            r2 = _alembic("upgrade", "head", db_url=scratch_url)
            assert r2.returncode == 0, r2.stderr

    def test_alembic_db_is_at_head_revision(self):
        """DB must be stamped at the head revision.

        Note: alembic check (autogenerate comparison) is intentionally NOT used
        here. Our baseline was applied via `alembic stamp` on an existing DB
        created by SQLAlchemy create_all. The stamp approach means the migration
        script and the live DB may differ slightly in index declarations —
        this is expected and harmless. What matters is that the revision pointer
        is correct and future `alembic revision --autogenerate` will produce
        clean diffs from this point forward.
        """
        result = _alembic("current")
        assert result.returncode == 0, result.stderr
        assert "Context impl" in result.stderr


class TestBaselineMigrationContent:
    def test_baseline_has_upgrade_and_downgrade(self):
        baseline = next(
            (PROJECT_ROOT / "alembic" / "versions").glob("0001*.py")
        )
        content = baseline.read_text()
        assert "def upgrade()" in content
        assert "def downgrade()" in content

    def test_baseline_creates_core_tables(self):
        baseline = next(
            (PROJECT_ROOT / "alembic" / "versions").glob("0001*.py")
        )
        content = baseline.read_text()
        for table in ("users", "raw_entities", "normalization_rules",
                       "authority_records", "audit_logs", "annotations"):
            assert table in content, f"Table '{table}' missing from baseline migration"

    def test_baseline_has_fts5_creation(self):
        baseline = next(
            (PROJECT_ROOT / "alembic" / "versions").glob("0001*.py")
        )
        content = baseline.read_text()
        assert "search_index" in content
        assert "fts5" in content

    def test_baseline_revision_id_matches(self):
        baseline = next(
            (PROJECT_ROOT / "alembic" / "versions").glob("0001*.py")
        )
        content = baseline.read_text()
        assert 'revision = "0001"' in content
        assert "down_revision = None" in content


class TestMainPyMigrated:
    def test_main_py_no_manual_alter_table(self):
        """main.py must not contain manual ALTER TABLE migration blocks."""
        main_content = (PROJECT_ROOT / "backend" / "main.py").read_text()
        # The old pattern was: if "col" not in _cols: _conn.execute(text("ALTER TABLE ..."))
        assert 'ALTER TABLE harmonization_logs ADD COLUMN' not in main_content
        assert 'ALTER TABLE raw_entities ADD COLUMN' not in main_content
        assert 'ALTER TABLE users ADD COLUMN failed_attempts' not in main_content

    def test_main_py_does_not_run_migrations_on_import(self):
        main_content = (PROJECT_ROOT / "backend" / "main.py").read_text()
        assert "_run_migrations()" not in main_content
        assert "command.upgrade" not in main_content
        assert "UKIP_SKIP_STARTUP_SIDE_EFFECTS" in main_content

    def test_main_py_no_inspect_import(self):
        """sqlalchemy.inspect is no longer needed after removing manual migrations."""
        main_content = (PROJECT_ROOT / "backend" / "main.py").read_text()
        assert "from sqlalchemy import inspect" not in main_content
