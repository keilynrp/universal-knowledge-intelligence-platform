"""
Sprint 94 — PostgreSQL Hardening tests.

Tests run against whichever dialect `UKIP_DB_MODE` selects — in-memory SQLite by
default, PostgreSQL in CI and when checking production parity. The dialect
assertions below follow that setting instead of assuming SQLite, which is the
whole point of a hardening suite.

They verify:
  - database.py sets correct engine kwargs per dialect
  - search.py dialect flag is derived correctly
  - _rebuild + global_search work on SQLite (FTS5 path)
  - Migration helpers use cross-DB inspect.has_table() (not sqlite_master)
  - Boolean server_defaults in baseline use sa.text("true"/"false")
  - docker-compose.yml declares a postgres service
  - Dockerfile.backend exists and references requirements.txt
"""
from __future__ import annotations

import os
import pathlib

import pytest
from fastapi.testclient import TestClient

from backend import models
from backend.database import SQLALCHEMY_DATABASE_URL

pytestmark = pytest.mark.postgres

# Which dialect this run is meant to exercise. Mirrors conftest.
_EXPECT_POSTGRES = os.environ.get("UKIP_DB_MODE", "sqlite").lower() == "postgres"


# ── 1. Database engine configuration ─────────────────────────────────────────

class TestDatabaseConfig:
    def test_url_matches_the_configured_dialect(self):
        """The module URL follows UKIP_DB_MODE rather than being assumed SQLite.

        This asserted `startswith("sqlite")` unconditionally, which encoded the
        very assumption we are trying to remove: it fails against PostgreSQL for
        being right about the dialect.
        """
        expected = "postgresql" if _EXPECT_POSTGRES else "sqlite"
        assert SQLALCHEMY_DATABASE_URL.startswith(expected)

    def test_pg_url_branch_in_database_py(self):
        """database.py source must contain pool_size / pool_pre_ping for PG branch."""
        src = pathlib.Path("backend/database.py").read_text()
        assert "pool_size" in src
        assert "pool_pre_ping" in src
        assert "check_same_thread" in src  # SQLite branch also present

    def test_engine_pooling_matches_the_dialect(self):
        """SQLite gets connect_args and no pool sizing; PostgreSQL gets the pool.

        The old version asserted only `url.startswith("sqlite")` — a restatement
        of its own premise that never looked at the engine it claimed to check.
        """
        from backend.database import engine

        if _EXPECT_POSTGRES:
            assert engine.pool.size() > 0
        else:
            # SQLite pools carry no configurable size; the branch sets
            # connect_args={"check_same_thread": False} instead.
            assert engine.dialect.name == "sqlite"
            assert "check_same_thread" in str(engine.dialect.create_connect_args(engine.url))


# ── 2. Search router dialect flag ─────────────────────────────────────────────

class TestSearchDialect:
    def test_is_sqlite_flag_agrees_with_the_url(self):
        """The router's dialect flag must track the URL, either way."""
        from backend.routers.search import _IS_SQLITE
        assert _IS_SQLITE is (not _EXPECT_POSTGRES)

    def test_fts_query_produces_quoted_tokens(self):
        from backend.routers.search import _fts_query
        result = _fts_query("machine learning")
        assert '"machine"*' in result
        assert '"learning"*' in result

    def test_fts_query_empty_returns_quoted_empty(self):
        from backend.routers.search import _fts_query
        result = _fts_query("   ")
        assert result == '""'

    def test_search_rebuild_endpoint(self, client: TestClient, auth_headers: dict):
        resp = client.post("/search/rebuild", headers=auth_headers)
        assert resp.status_code == 200
        assert "indexed" in resp.json()

    def test_search_returns_results(self, client: TestClient, auth_headers: dict, db_session):
        # Seed an entity and rebuild index
        e = models.RawEntity(primary_label="PostgreSQL Hardening Test", domain="default")
        db_session.add(e)
        db_session.commit()
        client.post("/search/rebuild", headers=auth_headers)
        resp = client.get("/search?q=PostgreSQL", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data


# ── 3. Migration cross-DB pattern (inspect.has_table) ─────────────────────────

class TestMigrationHelpers:
    def test_sprint90_migration_uses_inspect(self):
        src = pathlib.Path("alembic/versions/8ac20d60f654_sprint_90_web_scraper_configs.py").read_text()
        assert "sqlite_master" not in src
        assert "has_table" in src

    def test_sprint92_migration_uses_inspect(self):
        src = pathlib.Path("alembic/versions/92a1b2c3d4e5_sprint_92_workflow_automation.py").read_text()
        assert "sqlite_master" not in src
        assert "has_table" in src

    def test_sprint93_migration_uses_inspect(self):
        src = pathlib.Path("alembic/versions/93b2c3d4e5f6_sprint_93_embed_widgets.py").read_text()
        assert "sqlite_master" not in src
        assert "has_table" in src

    def test_baseline_has_no_bare_bool_string_defaults(self):
        src = pathlib.Path("alembic/versions/0001_baseline.py").read_text()
        # The Boolean-specific bad patterns must be gone
        assert 'sa.Boolean' not in src or 'server_default="1"' not in src
        # Cross-DB Boolean patterns must be present
        assert 'sa.text("true")' in src
        assert 'sa.text("false")' in src
        # Integer server_default="0" (failed_attempts, citation_count) are fine for PG
        import re
        bool_defaults = re.findall(r'sa\.Boolean.*?server_default="[01]"', src)
        assert len(bool_defaults) == 0, f"Found bare Boolean defaults: {bool_defaults}"

    def test_baseline_fts5_is_conditional(self):
        src = pathlib.Path("alembic/versions/0001_baseline.py").read_text()
        assert 'dialect.name == "sqlite"' in src
        assert "to_tsvector" in src  # PG branch present


# ── 4. Docker / deployment artifacts ─────────────────────────────────────────

class TestDeploymentArtifacts:
    def test_dockerfile_backend_exists(self):
        assert pathlib.Path("Dockerfile.backend").exists()

    def test_dockerfile_references_requirements(self):
        content = pathlib.Path("Dockerfile.backend").read_text()
        assert "requirements.txt" in content
        assert "backend-entrypoint.sh" in content
        entrypoint = pathlib.Path("docker/backend-entrypoint.sh").read_text()
        assert "alembic upgrade head" in entrypoint

    def test_docker_compose_has_postgres_service(self):
        content = pathlib.Path("docker-compose.yml").read_text()
        assert "postgres" in content
        assert "postgresql" in content.lower()

    def test_docker_compose_has_healthcheck(self):
        content = pathlib.Path("docker-compose.yml").read_text()
        assert "healthcheck" in content
        assert "pg_isready" in content

    def test_psycopg2_in_requirements(self):
        content = pathlib.Path("requirements.txt").read_text()
        assert "psycopg2" in content
