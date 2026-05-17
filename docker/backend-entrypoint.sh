#!/bin/sh
set -eu

if [ "${RUN_DB_MIGRATIONS_ON_START:-1}" = "1" ]; then
  alembic upgrade head
fi

# One-time text normalization (fixes mojibake + inline HTML in existing entities)
python -m backend.scripts.normalize_imported_text || true

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
