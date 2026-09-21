"""CI rehearsal: run the newest Alembic migrations over a database with data in it.

Why this exists (issue #361)
----------------------------
The ``postgres-shard`` jobs run ``alembic upgrade head`` on an EMPTY database.
An empty table cannot violate a constraint, so a migration that rewrites rows
passes there and fails on the first real database it meets. That is how the
first cut of ``b8c9d0e1f2a3`` (#359) reached production: its backfill
``UPDATE`` hit the append-only trigger on ``backup_assurance_events`` and the
deploy stopped with the schema stale for about three hours.

What it does
------------
Against a fresh, empty PostgreSQL:

1. upgrade to the revision ``--steps`` below head;
2. put one synthetic row in every table that exists at that point;
3. upgrade one revision at a time up to head, topping up any table a migration
   created, so every migration in the window runs over rows;
4. downgrade one step and upgrade again, so the newest ``downgrade()`` is
   exercised with data instead of being code nobody runs.

Seeded rows cannot guess a migration's WHERE clause: #359's backfill only
matched rows whose provider mentioned "volume", so over one synthetic row it
touched nothing and passed. Every migration step therefore also runs under a
statement guard: an UPDATE, DELETE or TRUNCATE aimed at an append-only table
(one whose BEFORE trigger raises), or a statement that disables or drops that
trigger, fails the rehearsal whether or not it matches a row. The append-only
tables are read from the catalog, not hard-coded.

A downgrade may drop only the triggers its own migration created.

Known limits: the guard reads the append-only tables once per migration step,
so a migration that creates such a trigger and rewrites the same table in one
``upgrade()`` is not caught; and on a merge revision the window follows the
first parent only (the chain is linear today).

It fails if any migration fails, if the guard trips, or if a table still has
no row when the migrations run over it (a table the seeder cannot fill is a
table the rehearsal proves nothing about).

Usage (after starting an empty PostgreSQL and exporting ``DATABASE_URL``)::

    python scripts/ci_migration_rehearsal.py --steps 3

It downgrades, so it refuses to touch a database that already has tables, or a
host other than localhost.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import uuid
import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import (
    Column,
    MetaData,
    Table,
    create_engine,
    event,
    func,
    inspect,
    make_url,
    select,
    text,
)
from sqlalchemy import types as sqltypes
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SAWarning

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
SKIPPED_TABLES = {"alembic_version"}
_FIXED_DATETIME = dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
_UNSUPPORTED = object()


@dataclass
class SeedReport:
    seeded: list[str] = field(default_factory=list)
    already_populated: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def revision_window(script: Any, steps: int) -> list[str]:
    """Return ``[base, ..., head]``: head plus up to ``steps`` ancestors, oldest first.

    ``script`` is an ``alembic.script.ScriptDirectory``. A merge revision is
    followed through its first parent; the chain is linear today.
    """
    if steps < 1:
        raise ValueError("steps must be at least 1")
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"expected a single Alembic head, found {sorted(heads)}")
    chain: list[str] = []
    revision = script.get_revision(heads[0])
    while revision is not None and len(chain) <= steps:
        chain.append(revision.revision)
        parent = revision.down_revision
        if isinstance(parent, tuple):
            parent = parent[0]
        revision = script.get_revision(parent) if parent else None
    if len(chain) < 2:
        raise RuntimeError("need at least two revisions to rehearse an upgrade")
    return list(reversed(chain))


def sample_value(column: Column, n: int) -> Any:
    """A value of the column's type, or ``_UNSUPPORTED``. Order matters: subclasses first."""
    col_type = column.type
    if isinstance(col_type, sqltypes.Enum) and col_type.enums:
        return col_type.enums[0]
    if isinstance(col_type, sqltypes.Boolean):
        return False
    if isinstance(col_type, sqltypes.Integer):
        return n
    if isinstance(col_type, sqltypes.Numeric):
        return n
    if isinstance(col_type, sqltypes.DateTime):
        if getattr(col_type, "timezone", False):
            return _FIXED_DATETIME
        return _FIXED_DATETIME.replace(tzinfo=None)
    if isinstance(col_type, sqltypes.Date):
        return _FIXED_DATETIME.date()
    if isinstance(col_type, sqltypes.Time):
        return _FIXED_DATETIME.time()
    if isinstance(col_type, sqltypes.JSON):
        return {"seed": n}
    if isinstance(col_type, sqltypes.ARRAY):
        return []
    if isinstance(col_type, sqltypes.Uuid):
        return uuid.uuid5(uuid.NAMESPACE_OID, f"{column.table.name}.{column.name}.{n}")
    if isinstance(col_type, sqltypes.LargeBinary):
        return b"seed"
    if isinstance(col_type, sqltypes.String):
        value = f"seed-{column.name}-{n}"
        length = getattr(col_type, "length", None)
        return value[:length] if length else value
    return _UNSUPPORTED


def _database_generates(column: Column) -> bool:
    """True for integer primary keys the database fills (serial / identity)."""
    return (
        column.primary_key
        and isinstance(column.type, sqltypes.Integer)
        and (column.server_default is not None or column.identity is not None)
    )


def _parent_value(conn: Connection, column: Column) -> Any:
    """The referenced value of an existing parent row, or None when there is none."""
    foreign_key = next(iter(column.foreign_keys))
    target = foreign_key.column
    return conn.execute(select(target).limit(1)).scalar()


def build_row(conn: Connection, table: Table, n: int = 1) -> dict[str, Any]:
    """One row for ``table``. Raises ``ValueError`` naming the column it cannot fill."""
    row: dict[str, Any] = {}
    for column in table.columns:
        if _database_generates(column):
            continue
        if column.foreign_keys:
            value = _parent_value(conn, column)
            if value is None and not column.nullable:
                raise ValueError(f"{column.name}: referenced table has no row")
            row[column.name] = value
            continue
        value = sample_value(column, n)
        if value is _UNSUPPORTED:
            if column.nullable or column.server_default is not None:
                continue
            raise ValueError(f"{column.name}: no sample for type {column.type!r}")
        row[column.name] = value
    return row


def _is_empty(conn: Connection, table: Table) -> bool:
    return conn.execute(select(func.count()).select_from(table)).scalar() == 0


def _ordered_tables(metadata: MetaData) -> list[Table]:
    """Parents before children, as far as the foreign keys allow.

    ``organizations`` and ``users`` reference each other, so SQLAlchemy warns
    that it cannot order them; ``seed_empty_tables`` resolves that cycle by
    retrying, so the warning is expected here and silenced.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SAWarning)
        return [t for t in metadata.sorted_tables if t.name not in SKIPPED_TABLES]


def _try_insert(conn: Connection, table: Table) -> str | None:
    """Insert one row in its own savepoint. Returns the failure, or None."""
    try:
        with conn.begin_nested():
            conn.execute(table.insert().values(**build_row(conn, table)))
    except Exception as exc:  # noqa: BLE001 — returned to the caller and reported
        return f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
    return None


def seed_empty_tables(engine: Engine) -> SeedReport:
    """Give every empty table one row, parents before children.

    Each insert runs in its own savepoint, so one table that cannot be filled
    does not undo the others. Tables that fail are retried while any pass
    makes progress, which fills a foreign-key cycle once one side has a row;
    whatever is left is reported.
    """
    report = SeedReport()
    metadata = MetaData()
    with engine.begin() as conn:
        metadata.reflect(bind=conn)
        pending: list[Table] = []
        for table in _ordered_tables(metadata):
            if _is_empty(conn, table):
                pending.append(table)
            else:
                report.already_populated.append(table.name)
        while pending:
            failures = {table.name: _try_insert(conn, table) for table in pending}
            filled = [table for table in pending if failures[table.name] is None]
            report.seeded.extend(table.name for table in filled)
            pending = [table for table in pending if failures[table.name] is not None]
            if not filled:
                report.failed = {table.name: failures[table.name] for table in pending}
                break
    return report


# pg_trigger.tgtype bits (src/include/catalog/pg_trigger.h).
_TRIGGER_BEFORE = 1 << 1
_TRIGGER_OPS = {"DELETE": 1 << 3, "UPDATE": 1 << 4, "TRUNCATE": 1 << 5}

# Any schema qualifier is accepted and ignored: over-matching a same-named
# table elsewhere is the safe direction for a guard.
_NAME = r'(?:"?[A-Za-z_][A-Za-z0-9_]*"?\.)?"?([A-Za-z_][A-Za-z0-9_]*)"?'
_ROW_WRITE_RE = re.compile(
    r"\b(UPDATE|DELETE\s+FROM)\s+(?:ONLY\s+)?" + _NAME,
    re.IGNORECASE,
)
_TRUNCATE_RE = re.compile(
    r"\bTRUNCATE\s+(?:TABLE\s+)?((?:(?:ONLY\s+)?[\w\".]+\s*,\s*)*(?:ONLY\s+)?[\w\".]+)",
    re.IGNORECASE,
)
_TRIGGER_DISABLE_RE = re.compile(
    r"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?"
    + _NAME
    + r"\s+DISABLE\s+TRIGGER",
    re.IGNORECASE,
)
_TRIGGER_DROP_RE = re.compile(
    r'\bDROP\s+TRIGGER\s+(?:IF\s+EXISTS\s+)?"?([A-Za-z_][A-Za-z0-9_]*)"?'
    r"\s+ON\s+(?:ONLY\s+)?" + _NAME,
    re.IGNORECASE,
)
_SQL_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
# plpgsql: `RAISE EXCEPTION ...` and a bare `RAISE 'msg'` both abort the statement.
_RAISES = r"\mraise\s+(exception\M|')"


_RAISING_TRIGGERS_SQL = (
    "SELECT c.relname, t.tgname, t.tgtype FROM pg_trigger t "
    "JOIN pg_class c ON c.oid = t.tgrelid "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "JOIN pg_proc p ON p.oid = t.tgfoid "
    "WHERE NOT t.tgisinternal AND n.nspname = 'public' "
    "AND p.prosrc ~* :raises"
)


def raising_triggers(conn: Connection) -> set[str]:
    """Names of the triggers that make tables append-only."""
    rows = conn.execute(text(_RAISING_TRIGGERS_SQL), {"raises": _RAISES})
    return {name for _table, name, tgtype in rows if tgtype & _TRIGGER_BEFORE}


def refusing_tables(conn: Connection) -> dict[str, set[str]]:
    """Tables whose BEFORE triggers raise on UPDATE/DELETE/TRUNCATE, with those ops.

    These are the append-only tables. A migration may not rewrite their rows,
    and it may not switch the trigger off to do so. A trigger that raises only
    under some condition is treated as always raising: the guard would rather
    stop a legitimate migration for review than let an unsafe one through.
    """
    rows = conn.execute(text(_RAISING_TRIGGERS_SQL), {"raises": _RAISES})
    refused: dict[str, set[str]] = {}
    for table, _name, tgtype in rows:
        if tgtype & _TRIGGER_BEFORE:
            ops = {op for op, bit in _TRIGGER_OPS.items() if tgtype & bit}
            refused.setdefault(table, set()).update(ops)
    return refused


def _truncated_tables(statement: str) -> list[str]:
    names: list[str] = []
    for match in _TRUNCATE_RE.finditer(statement):
        for item in match.group(1).split(","):
            item = re.sub(r"(?i)^\s*ONLY\s+", "", item).strip()
            names.append(item.split(".")[-1].strip('"'))
    return names


def violation(
    statement: str,
    refused: dict[str, set[str]],
    allowed_drops: frozenset[str] = frozenset(),
) -> str | None:
    """Why ``statement`` rewrites or unguards an append-only table, or None.

    Row count does not matter: an UPDATE that matches no row here matches the
    rows production has. That is exactly how #359 passed on seeded data.

    TRUNCATE counts as a DELETE. Row-level triggers cannot fire on TRUNCATE
    (PostgreSQL rejects ``FOR EACH ROW ... ON TRUNCATE``), so a table that
    refuses DELETE row by row can still be emptied with one TRUNCATE; the
    trigger does not stop it, and so this guard must.

    ``allowed_drops`` names triggers a downgrade may remove: the ones the
    migration being reverted created. Reverting a migration that added a
    protection takes that protection away and nothing else; dropping any trigger
    that was there before it is still a violation. DISABLE TRIGGER never is
    allowed.
    """
    statement = _SQL_COMMENT_RE.sub(" ", statement)
    for match in _ROW_WRITE_RE.finditer(statement):
        op = match.group(1).split()[0].upper()
        table = match.group(2)
        if op in refused.get(table, set()):
            return f"{op} on append-only table {table!r}"
    for table in _truncated_tables(statement):
        if refused.get(table, set()) & {"DELETE", "TRUNCATE"}:
            return f"TRUNCATE on append-only table {table!r} (bypasses its row trigger)"
    for match in _TRIGGER_DISABLE_RE.finditer(statement):
        if match.group(1) in refused:
            return f"disables the trigger that makes {match.group(1)!r} append-only"
    for match in _TRIGGER_DROP_RE.finditer(statement):
        trigger, table = match.group(1), match.group(2)
        if table in refused and trigger not in allowed_drops:
            return f"drops trigger {trigger!r}, which makes {table!r} append-only"
    return None


class AppendOnlyViolation(RuntimeError):
    pass


@contextmanager
def append_only_guard(
    engine: Engine, allowed_drops: frozenset[str] = frozenset()
) -> Iterator[None]:
    """Fail any statement, on any engine, that would rewrite an append-only table.

    Alembic's ``env.py`` builds its own engine, so the listener goes on the
    ``Engine`` class for the duration of one Alembic command.
    """
    with engine.connect() as conn:
        refused = refusing_tables(conn)

    def check(_conn, _cursor, statement, _params, _context, _many):
        reason = violation(statement, refused, allowed_drops)
        if reason:
            shown = " ".join(statement.split())[:300]
            raise AppendOnlyViolation(f"{reason}\n  statement: {shown}")

    event.listen(Engine, "before_cursor_execute", check)
    try:
        yield
    finally:
        event.remove(Engine, "before_cursor_execute", check)


def assert_safe_target(engine: Engine) -> None:
    """Refuse anything but an empty database on this machine: the rehearsal downgrades."""
    host = make_url(str(engine.url)).host or "localhost"
    if host not in LOCAL_HOSTS:
        raise SystemExit(f"refusing to rehearse against non-local host {host!r}")
    if engine.dialect.name != "postgresql":
        raise SystemExit(
            f"the rehearsal targets PostgreSQL, got {engine.dialect.name!r}"
        )
    existing = inspect(engine).get_table_names()
    if existing:
        raise SystemExit(
            f"refusing to rehearse on a non-empty database ({len(existing)} tables)"
        )


def _seed_and_check(engine: Engine, label: str) -> None:
    report = seed_empty_tables(engine)
    total = len(report.seeded) + len(report.already_populated) + len(report.failed)
    print(
        f"  seed at {label}: {len(report.seeded)} new, "
        f"{len(report.already_populated)} already had rows, "
        f"{len(report.failed)} could not be filled (of {total})"
    )
    for name, reason in sorted(report.failed.items()):
        print(f"    ✗ {name}: {reason}")
    if report.failed:
        raise SystemExit(
            "every table must hold a row before the next migration runs over it"
        )
    with engine.connect() as conn:
        refused = refusing_tables(conn)
    if refused:
        listed = ", ".join(
            f"{t} ({'/'.join(sorted(ops))})" for t, ops in sorted(refused.items())
        )
        print(f"  append-only tables: {listed}")


def _step(
    engine: Engine,
    label: str,
    action: Callable[[], None],
    allowed_drops: frozenset[str] = frozenset(),
) -> None:
    print(label)
    try:
        with append_only_guard(engine, allowed_drops):
            action()
    except AppendOnlyViolation as exc:
        raise SystemExit(f"migration rewrites append-only evidence: {exc}") from None


def _raising_triggers(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        return raising_triggers(conn)


def rehearse(steps: int) -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from alembic import command
    from backend.db_config import resolve_database_url

    config = Config(os.path.join(_REPO_ROOT, "alembic.ini"))
    window = revision_window(ScriptDirectory.from_config(config), steps)
    engine = create_engine(resolve_database_url())
    assert_safe_target(engine)
    print(f"rehearsing {len(window) - 1} migration(s): {' -> '.join(window)}")

    command.upgrade(config, window[0])
    _seed_and_check(engine, window[0])
    for revision in window[1:]:
        if revision == window[-1]:
            before_head = _raising_triggers(engine)
        _step(
            engine,
            f"upgrade -> {revision} (over seeded rows)",
            lambda rev=revision: command.upgrade(config, rev),
        )
        _seed_and_check(engine, revision)
    created_by_head = frozenset(_raising_triggers(engine) - before_head)
    if created_by_head:
        print(f"  the newest migration added: {', '.join(sorted(created_by_head))}")
    _step(
        engine,
        f"downgrade {window[-1]} -> {window[-2]} (over seeded rows)",
        lambda: command.downgrade(config, "-1"),
        allowed_drops=created_by_head,
    )
    _step(
        engine,
        f"upgrade -> {window[-1]} again",
        lambda: command.upgrade(config, window[-1]),
    )
    engine.dispose()
    print("migration rehearsal passed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--steps",
        type=int,
        default=3,
        help="how many of the newest migrations to run over seeded data (default 3)",
    )
    args = parser.parse_args(argv)
    rehearse(args.steps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
