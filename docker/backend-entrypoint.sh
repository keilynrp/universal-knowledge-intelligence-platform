#!/bin/sh
set -eu

DB_CONNECT_RETRIES="${DB_CONNECT_RETRIES:-30}"
DB_CONNECT_SLEEP_SECONDS="${DB_CONNECT_SLEEP_SECONDS:-2}"

python - <<'PY'
import os
import sys
import time

from sqlalchemy import create_engine, text

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    print("DATABASE_URL is not set", file=sys.stderr)
    sys.exit(1)

retries = int(os.environ.get("DB_CONNECT_RETRIES", "30"))
sleep_seconds = float(os.environ.get("DB_CONNECT_SLEEP_SECONDS", "2"))
last_error = None

for attempt in range(1, retries + 1):
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"Database is reachable after {attempt} attempt(s)")
        break
    except Exception as exc:
        last_error = exc
        print(
            f"Database not ready ({attempt}/{retries}): {exc}",
            file=sys.stderr,
        )
        time.sleep(sleep_seconds)
else:
    print(f"Database did not become reachable: {last_error}", file=sys.stderr)
    sys.exit(1)
PY

if [ "${RUN_DB_MIGRATIONS_ON_START:-1}" = "1" ]; then
  # Run migrations, but do not let a failure silently kill the container before
  # uvicorn starts (which surfaces only as an opaque "unhealthy" deploy error).
  # On failure: log loudly and continue so /health comes up and the real error
  # is visible in the logs. Set MIGRATIONS_FATAL=1 to restore strict aborting.
  if ! alembic upgrade head; then
    echo "============================================================" >&2
    echo "ERROR: 'alembic upgrade head' FAILED." >&2
    echo "Continuing startup so the service serves /health and this error" >&2
    echo "is visible in the container logs. The schema may be stale — run the" >&2
    echo "ukip-migrate ops service to apply migrations deliberately." >&2
    echo "Set MIGRATIONS_FATAL=1 to make this abort startup instead." >&2
    echo "============================================================" >&2
    if [ "${MIGRATIONS_FATAL:-0}" = "1" ]; then
      exit 1
    fi
  fi

  # Verify the schema actually reached head — even if 'alembic upgrade head'
  # exited 0. Catches silent drift (partial/failed upgrade that still returned
  # 0). Emits a greppable MIGRATION_DRIFT marker for log-based alerting; runtime
  # drift is also reported by /ops/checks (ops.check_failed fan-out).
  if ! python -m backend.db_revision --check; then
    echo "============================================================" >&2
    echo "ERROR: database schema is NOT at the latest migration head (drift)." >&2
    echo "Starting fail-open so /health responds, but the schema is STALE." >&2
    echo "Apply migrations via the ukip-migrate ops service." >&2
    echo "Set MIGRATIONS_FATAL=1 to abort startup on drift instead." >&2
    echo "============================================================" >&2
    if [ "${MIGRATIONS_FATAL:-0}" = "1" ]; then
      exit 1
    fi
  fi
fi

# One-time text normalization (fixes mojibake + inline HTML in existing entities)
python -m backend.scripts.normalize_imported_text || true

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
