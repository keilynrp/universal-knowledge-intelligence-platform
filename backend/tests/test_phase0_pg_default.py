# backend/tests/test_phase0_pg_default.py
"""Phase 0 — Postgres-only default contract.

These tests assert behaviour of the pure resolution functions in isolation by
manipulating os.environ directly. They do NOT import backend.database (whose
module-level URL is already frozen to the test sqlite URL by conftest).
"""
import importlib
import os


def _reload_db_config():
    import backend.db_config as db_config
    return importlib.reload(db_config)


def test_default_url_is_postgres_when_db_mode_unset(monkeypatch):
    monkeypatch.delenv("UKIP_DB_MODE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_config = _reload_db_config()
    url = db_config.default_database_url()
    assert url.startswith("postgresql+psycopg2://")


def test_default_url_is_postgres_even_when_db_mode_sqlite(monkeypatch):
    """UKIP_DB_MODE=sqlite no longer forces a sqlite default — the SQLite
    fallback was removed. Tests/dev must pass an explicit DATABASE_URL instead."""
    monkeypatch.setenv("UKIP_DB_MODE", "sqlite")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_config = _reload_db_config()
    url = db_config.default_database_url()
    assert url.startswith("postgresql+psycopg2://")
    assert "sqlite" not in url


def test_explicit_database_url_is_still_honoured(monkeypatch):
    """resolve_database_url() must pass an explicit DATABASE_URL through
    untouched — this is what keeps the SQLite test harness working."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    db_config = _reload_db_config()
    assert db_config.resolve_database_url() == "sqlite:///:memory:"
