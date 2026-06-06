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
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

logger = logging.getLogger(__name__)

# Greppable marker for log-based alerting (Dokploy / Sentry / log drains).
DRIFT_MARKER = "MIGRATION_DRIFT"

# alembic.ini lives at the repo root (one level above this package). Resolve it
# relative to this file so the check works regardless of the process CWD.
_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _alembic_config() -> Config:
    return Config(str(_ALEMBIC_INI))


def evaluate_drift(current: str | None, heads: "list[str] | tuple[str, ...]") -> dict[str, Any]:
    """Pure decision: is *current* one of the migration script *heads*?

    Extracted from I/O so it can be unit-tested without a live database. A NULL
    current (no alembic_version row) or a revision not present in heads both
    count as stale.
    """
    heads_list = sorted(heads)
    is_stale = current is None or current not in heads_list
    return {"current": current, "heads": heads_list, "is_stale": is_stale}


def migration_drift(engine) -> dict[str, Any]:
    """Inspect *engine*'s database and report whether it is at an Alembic head.

    Returns ``{current, heads, is_stale, error}``. If the state cannot be
    determined (bad config, DB unreachable), ``error`` is set and ``is_stale``
    defaults to True — fail-safe: surface a problem rather than hide it.
    """
    try:
        script = ScriptDirectory.from_config(_alembic_config())
        heads = script.get_heads()
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        result = evaluate_drift(current, heads)
        result["error"] = None
        return result
    except Exception as exc:  # noqa: BLE001 — never raise out of a health probe
        logger.exception("migration_drift_inspection_failed")
        return {"current": None, "heads": [], "is_stale": True, "error": str(exc)}


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
