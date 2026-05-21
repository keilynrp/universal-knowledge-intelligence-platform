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
  alembic upgrade head
fi

# One-time text normalization (fixes mojibake + inline HTML in existing entities)
python -m backend.scripts.normalize_imported_text || true

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
