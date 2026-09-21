"""Unit tests for scripts/ci_migration_rehearsal.py (issue #361).

The rehearsal itself needs PostgreSQL and runs in the `migration-rehearsal`
CI job. These tests pin the parts that decide what it can catch — the revision
window, the seeder, the append-only statement guard and the target safety
check — against SQLite and in-memory fakes, so they run in every shard.
"""

import datetime as dt
import sys
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import (
    Column,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    text,
)
from sqlalchemy import types as sqltypes

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import ci_migration_rehearsal as rehearsal

pytestmark = pytest.mark.unit

APPEND_ONLY = {"backup_assurance_events": {"UPDATE", "DELETE"}}


# ── revision window ──────────────────────────────────────────────────────────


def _script() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(REPO_ROOT / "alembic.ini")))


def test_window_ends_at_head_and_follows_down_revisions():
    script = _script()
    window = rehearsal.revision_window(script, 3)

    assert len(window) == 4
    assert window[-1] == script.get_current_head()
    for older, newer in pairwise(window):
        parent = script.get_revision(newer).down_revision
        parent = parent[0] if isinstance(parent, tuple) else parent
        assert parent == older


def test_window_rejects_zero_steps():
    with pytest.raises(ValueError):
        rehearsal.revision_window(_script(), 0)


def test_window_rejects_multiple_heads():
    fake = SimpleNamespace(get_heads=lambda: ["aaa", "bbb"])
    with pytest.raises(RuntimeError, match="single Alembic head"):
        rehearsal.revision_window(fake, 1)


# ── append-only statement guard ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "statement",
    [
        # The #359 backfill, verbatim: it matched no seeded row and still must fail.
        (
            "UPDATE backup_assurance_events SET scope = 'volume' "
            "WHERE lower(coalesce(provider, '')) LIKE '%volume%'"
        ),
        'UPDATE "public"."backup_assurance_events" SET scope = NULL',
        "update only backup_assurance_events set scope = 'x'",
        "DELETE FROM backup_assurance_events WHERE id < 0",
        "WITH x AS (SELECT 1) DELETE FROM public.backup_assurance_events",
        "ALTER TABLE backup_assurance_events DISABLE TRIGGER ALL",
        "ALTER TABLE ONLY public.backup_assurance_events DISABLE TRIGGER t_reject",
        "DROP TRIGGER IF EXISTS t_reject ON backup_assurance_events",
        "UPDATE audit.backup_assurance_events SET scope = 'x'",
        # Row triggers cannot fire on TRUNCATE, so it must be refused here.
        "TRUNCATE backup_assurance_events",
        "TRUNCATE TABLE ONLY raw_entities, public.backup_assurance_events CASCADE",
    ],
)
def test_guard_flags_rewrites_of_append_only_tables(statement):
    assert rehearsal.violation(statement, APPEND_ONLY) is not None


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE raw_entities SET domain = 'x'",
        "DELETE FROM audit_logs",
        "INSERT INTO backup_assurance_events (id) VALUES (1)",
        "ALTER TABLE backup_assurance_events ADD COLUMN scope VARCHAR(20)",
        # DDL that merely mentions the operation must not trip it.
        (
            "CREATE TRIGGER t BEFORE UPDATE ON backup_assurance_events "
            "FOR EACH ROW EXECUTE FUNCTION f()"
        ),
        "ALTER TABLE x ADD FOREIGN KEY (a) REFERENCES y (b) ON UPDATE CASCADE",
        "TRUNCATE raw_entities, audit_logs",
        # A statement that is only a comment executes nothing.
        "-- UPDATE backup_assurance_events SET scope = 'x'\nSELECT 1",
        "/* DELETE FROM backup_assurance_events */ SELECT 1",
    ],
)
def test_guard_allows_everything_else(statement):
    assert rehearsal.violation(statement, APPEND_ONLY) is None


def test_a_downgrade_may_drop_only_the_triggers_its_migration_created():
    drop_new = "DROP TRIGGER IF EXISTS trg_new ON backup_assurance_events"
    drop_old = "DROP TRIGGER IF EXISTS trg_old ON backup_assurance_events"
    allowed = frozenset({"trg_new"})

    assert rehearsal.violation(drop_new, APPEND_ONLY, allowed) is None
    assert rehearsal.violation(drop_old, APPEND_ONLY, allowed) is not None
    assert rehearsal.violation(drop_new, APPEND_ONLY) is not None
    disable = "ALTER TABLE backup_assurance_events DISABLE TRIGGER trg_new"
    assert rehearsal.violation(disable, APPEND_ONLY, allowed) is not None


def test_guard_only_refuses_the_operations_the_trigger_refuses():
    delete_only = {"events": {"DELETE"}}
    update_only = {"events": {"UPDATE"}}
    assert rehearsal.violation("UPDATE events SET a = 1", delete_only) is None
    assert rehearsal.violation("DELETE FROM events", delete_only) is not None
    assert rehearsal.violation("TRUNCATE events", delete_only) is not None
    assert rehearsal.violation("TRUNCATE events", update_only) is None


def test_guard_listener_fires_on_any_engine_and_is_removed(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE events (id INTEGER PRIMARY KEY, a TEXT)"))
    monkeypatch.setattr(
        rehearsal, "refusing_tables", lambda conn: {"events": {"UPDATE"}}
    )
    other_engine = create_engine("sqlite://")  # as Alembic's env.py builds its own

    with rehearsal.append_only_guard(engine):
        with (
            pytest.raises(
                rehearsal.AppendOnlyViolation, match="append-only table 'events'"
            ),
            engine.begin() as conn,
        ):
            conn.execute(text("UPDATE events SET a = 'x'"))
        with pytest.raises(rehearsal.AppendOnlyViolation), other_engine.begin() as conn:
            conn.execute(text("UPDATE events SET a = 'x'"))

    with engine.begin() as conn:
        conn.execute(text("UPDATE events SET a = 'x'"))  # guard gone


# ── seeder ───────────────────────────────────────────────────────────────────


def _column(col_type) -> Column:
    table = Table("t", MetaData(), Column("c", col_type))
    return table.c.c


@pytest.mark.parametrize(
    ("col_type", "expected"),
    [
        (Integer(), 1),
        (sqltypes.Boolean(), False),
        (String(4), "seed"),
        (sqltypes.Text(), "seed-c-1"),
        (Enum("first", "second", name="e"), "first"),
        (sqltypes.JSON(), {"seed": 1}),
        (sqltypes.Numeric(10, 2), 1),
        (sqltypes.Date(), dt.date(2026, 1, 1)),
    ],
)
def test_sample_value_matches_the_column_type(col_type, expected):
    assert rehearsal.sample_value(_column(col_type), 1) == expected


def test_sample_value_keeps_timezone_awareness():
    aware = rehearsal.sample_value(_column(sqltypes.DateTime(timezone=True)), 1)
    naive = rehearsal.sample_value(_column(sqltypes.DateTime()), 1)
    assert aware.tzinfo is not None and naive.tzinfo is None


def test_sample_value_reports_unknown_types():
    assert (
        rehearsal.sample_value(_column(sqltypes.NullType()), 1)
        is rehearsal._UNSUPPORTED
    )


def _cycle_schema(engine) -> None:
    """organizations.owner_id -> users (NOT NULL), users.org_id -> organizations (nullable)."""
    metadata = MetaData()
    Table(
        "organizations",
        metadata,
        Column("id", Integer, primary_key=True),
        Column(
            "owner_id", Integer, ForeignKey("users.id", use_alter=True), nullable=False
        ),
        Column("name", String(20), nullable=False),
    )
    Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("org_id", Integer, ForeignKey("organizations.id"), nullable=True),
    )
    Table(
        "members",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("org_id", Integer, ForeignKey("organizations.id"), nullable=False),
    )
    metadata.create_all(engine)


def test_seeder_fills_every_table_through_a_foreign_key_cycle():
    engine = create_engine("sqlite://")
    _cycle_schema(engine)

    report = rehearsal.seed_empty_tables(engine)

    assert report.failed == {}
    assert sorted(report.seeded) == ["members", "organizations", "users"]
    with engine.connect() as conn:
        owner = conn.execute(text("SELECT owner_id FROM organizations")).scalar()
        user = conn.execute(text("SELECT id FROM users")).scalar()
    assert owner == user


def test_seeder_leaves_populated_tables_alone():
    engine = create_engine("sqlite://")
    _cycle_schema(engine)
    rehearsal.seed_empty_tables(engine)

    again = rehearsal.seed_empty_tables(engine)

    assert again.seeded == []
    assert sorted(again.already_populated) == ["members", "organizations", "users"]


def test_seeder_reports_a_table_it_cannot_fill():
    """A constraint the synthetic row breaks is reported, and so is every child of it."""
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE parents (id INTEGER PRIMARY KEY, "
                "code TEXT NOT NULL CHECK (code = 'fixed'))"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE orphans (id INTEGER PRIMARY KEY, parent_id INTEGER "
                "NOT NULL REFERENCES parents(id))"
            )
        )

    report = rehearsal.seed_empty_tables(engine)

    assert set(report.failed) == {"orphans", "parents"}
    assert "IntegrityError" in report.failed["parents"]
    assert "parent_id" in report.failed["orphans"]


def test_build_row_names_a_required_column_it_has_no_value_for():
    table = Table(
        "t",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("shape", sqltypes.NullType(), nullable=False),
    )
    with (
        create_engine("sqlite://").connect() as conn,
        pytest.raises(ValueError, match="shape"),
    ):
        rehearsal.build_row(conn, table)


# ── target safety ────────────────────────────────────────────────────────────


def test_refuses_a_remote_host_without_connecting():
    engine = create_engine("postgresql+psycopg2://u:p@db.example.com:5432/ukip")
    with pytest.raises(SystemExit, match="non-local host"):
        rehearsal.assert_safe_target(engine)


def test_refuses_a_dialect_other_than_postgresql():
    with pytest.raises(SystemExit, match="targets PostgreSQL"):
        rehearsal.assert_safe_target(create_engine("sqlite://"))
