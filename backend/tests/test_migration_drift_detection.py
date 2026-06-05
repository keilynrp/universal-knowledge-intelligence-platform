"""EPIC-016 follow-up — migration drift detection.

Mitigates the fail-open entrypoint: `alembic upgrade head` failing (or silently
leaving the schema behind) must be DETECTABLE at runtime, not silent.

Covers:
- backend.db_revision.evaluate_drift  (pure decision)
- backend.db_revision.migration_drift (live DB inspection)
- backend.ops_checks._migrations_check (ops-check + alert fan-out wiring)
"""
from __future__ import annotations

from sqlalchemy import create_engine, text

from backend.db_revision import (
    _alembic_config,
    evaluate_drift,
    migration_drift,
)


# ── Pure decision ────────────────────────────────────────────────────────────

def test_evaluate_drift_current_in_heads_is_not_stale():
    result = evaluate_drift("abc123", ["abc123"])
    assert result["is_stale"] is False
    assert result["current"] == "abc123"
    assert result["heads"] == ["abc123"]


def test_evaluate_drift_none_current_is_stale():
    result = evaluate_drift(None, ["abc123"])
    assert result["is_stale"] is True


def test_evaluate_drift_unknown_revision_is_stale():
    result = evaluate_drift("oldrev", ["newhead"])
    assert result["is_stale"] is True


# ── Live DB inspection (real SQLite engine) ──────────────────────────────────

def _head_revision() -> str:
    from alembic.script import ScriptDirectory
    return ScriptDirectory.from_config(_alembic_config()).get_heads()[0]


def test_migration_drift_fresh_db_is_stale():
    # A DB with no alembic_version table reports current=None → stale.
    engine = create_engine("sqlite:///:memory:")
    result = migration_drift(engine)
    assert result["is_stale"] is True
    assert result["error"] is None
    assert result["current"] is None
    assert len(result["heads"]) >= 1


def test_migration_drift_at_head_is_not_stale():
    engine = create_engine("sqlite:///:memory:")
    head = _head_revision()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL)"))
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": head}
        )
    result = migration_drift(engine)
    assert result["is_stale"] is False
    assert result["current"] == head
    assert result["error"] is None


def test_migration_drift_inspection_error_is_failsafe_stale():
    # An engine that cannot connect must surface a problem (stale + error),
    # never silently report "ok".
    engine = create_engine("postgresql+psycopg2://x:x@127.0.0.1:1/none",
                           connect_args={"connect_timeout": 1})
    result = migration_drift(engine)
    assert result["is_stale"] is True
    assert result["error"] is not None


# ── ops_checks integration ───────────────────────────────────────────────────

def test_migrations_check_skipped_when_side_effects_disabled(monkeypatch):
    monkeypatch.setenv("UKIP_SKIP_STARTUP_SIDE_EFFECTS", "1")
    from backend.ops_checks import _migrations_check
    check = _migrations_check()
    assert check["id"] == "migrations"
    assert check["status"] == "skipped"


def test_migrations_check_critical_when_stale(monkeypatch):
    monkeypatch.setenv("UKIP_SKIP_STARTUP_SIDE_EFFECTS", "0")
    import backend.ops_checks as ops
    monkeypatch.setattr(
        ops, "migration_drift",
        lambda engine: {"current": "old", "heads": ["new"], "is_stale": True, "error": None},
    )
    check = ops._migrations_check()
    assert check["status"] == "critical"
    assert check["details"]["current"] == "old"


def test_migrations_check_ok_when_at_head(monkeypatch):
    monkeypatch.setenv("UKIP_SKIP_STARTUP_SIDE_EFFECTS", "0")
    import backend.ops_checks as ops
    monkeypatch.setattr(
        ops, "migration_drift",
        lambda engine: {"current": "head", "heads": ["head"], "is_stale": False, "error": None},
    )
    check = ops._migrations_check()
    assert check["status"] == "ok"


def test_run_operational_checks_includes_migrations(db_session):
    from backend.ops_checks import run_operational_checks
    report = run_operational_checks(db_session)
    ids = {c["id"] for c in report["checks"]}
    assert "migrations" in ids
