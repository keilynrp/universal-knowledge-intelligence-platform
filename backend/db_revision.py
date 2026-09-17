"""Single source of truth for "is the DB schema at the latest Alembic head?".

The production entrypoint (`docker/backend-entrypoint.sh`) runs migrations
fail-open: if `alembic upgrade head` fails it logs and starts uvicorn anyway so
/health stays reachable. That keeps deploys alive but can leave the schema
stale *silently*. This module makes the drift detectable in two places that
share one implementation:

- boot time: `python -m backend.db_revision --check` verifies the schema right
  after the upgrade attempt and prints a greppable marker on drift.
- runtime: `backend.ops_checks._migrations_check` surfaces drift through
  /ops/checks and the existing alert fan-out.
- health: `schema_state` gives the public /health probe a coarse verdict, so a
  service running on a stale or missing schema no longer reports "ok".
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

# Greppable marker for log-based alerting (Dokploy / Sentry / log drains).
DRIFT_MARKER = "MIGRATION_DRIFT"

# alembic.ini lives at the repo root (one level above this package). Resolve it
# relative to this file so the check works regardless of the process CWD.
_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _alembic_config() -> Config:
    return Config(str(_ALEMBIC_INI))


def evaluate_drift(current: str | None, heads: list[str] | tuple[str, ...]) -> dict[str, Any]:
    """Pure decision: is *current* one of the migration script *heads*?

    Extracted from I/O so it can be unit-tested without a live database. A NULL
    current (no alembic_version row) or a revision not present in heads both
    count as stale.
    """
    heads_list = sorted(heads)
    is_stale = current is None or current not in heads_list
    return {"current": current, "heads": heads_list, "is_stale": is_stale}


def migration_drift(bind) -> dict[str, Any]:
    """Inspect *bind*'s database and report whether it is at an Alembic head.

    *bind* may be an Engine or an already-checked-out Connection. Passing a
    Connection matters for /health: that request already holds one pool slot for
    its `SELECT 1`, and opening a second one here would make concurrent probes
    wait on the pool while holding a slot each — a public endpoint that can
    deadlock the pool when it is small (`DB_POOL_SIZE=1`, no overflow).

    Returns ``{current, heads, is_stale, error}``. If the state cannot be
    determined (bad config, DB unreachable), ``error`` is set and ``is_stale``
    defaults to True — fail-safe: surface a problem rather than hide it.
    """
    try:
        script = ScriptDirectory.from_config(_alembic_config())
        heads = script.get_heads()
        if isinstance(bind, Connection):
            current = MigrationContext.configure(bind).get_current_revision()
        else:
            with bind.connect() as conn:
                current = MigrationContext.configure(conn).get_current_revision()
        result = evaluate_drift(current, heads)
        result["error"] = None
        return result
    except Exception as exc:  # never raise out of a health probe
        logger.exception("migration_drift_inspection_failed")
        return {"current": None, "heads": [], "is_stale": True, "error": str(exc)}


# Coarse verdicts for /health. That endpoint is unauthenticated, so it gets one
# of these words only; revisions and error text stay in the logs and in the
# authenticated /ops/checks.
SCHEMA_CURRENT = "current"
SCHEMA_STALE = "stale"
SCHEMA_UNVERSIONED = "unversioned"
SCHEMA_UNKNOWN = "unknown"


def classify_drift(drift: dict[str, Any]) -> str:
    """Map a ``migration_drift`` result to a coarse schema verdict.

    ``evaluate_drift`` counts a missing ``alembic_version`` table as stale, which
    is right for the entrypoint gate but too blunt for a health probe: a
    database built with ``create_all`` (tests, local dev) has no version table
    and is not broken. It gets its own verdict, ``unversioned``. An inspection
    error is ``unknown`` whatever else the result says.
    """
    if drift.get("error"):
        return SCHEMA_UNKNOWN
    if drift.get("current") is None:
        return SCHEMA_UNVERSIONED
    return SCHEMA_STALE if drift.get("is_stale") else SCHEMA_CURRENT


def schema_state(bind) -> str:
    """Inspect *bind* and return a coarse schema verdict. Never raises.

    Prefer passing the caller's existing Connection over an Engine — see
    ``migration_drift`` for why /health must not take a second pool slot.
    """
    return classify_drift(migration_drift(bind))


def _main(argv: list[str]) -> int:
    """CLI entrypoint. Exit 1 (+ marker on stderr) when the schema is stale."""
    from backend.database import engine

    drift = migration_drift(engine)
    heads = ",".join(drift["heads"])
    if drift["is_stale"]:
        print(
            f"{DRIFT_MARKER} is_stale=true current={drift['current']} "
            f"heads={heads} error={drift['error']}",
            file=sys.stderr,
        )
        return 1
    print(f"{DRIFT_MARKER} is_stale=false current={drift['current']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
