"""CI smoke test: exercise the REAL startup path against the configured database.

Why this exists
---------------
The unit suite runs with ``UKIP_SKIP_STARTUP_SIDE_EFFECTS=1``, so the FastAPI
lifespan's real bootstrap (``_run_db_bootstrap``: ``create_all`` of auxiliary
tables, super-admin provisioning, idempotent data migrations, template seeding)
is never executed in tests. The ``postgres-smoke`` job only ran
``alembic upgrade head`` — it never ran the lifespan bootstrap against Postgres.
That gap let a Postgres-only startup failure reach production as an opaque
"container unhealthy" deploy error.

This script closes the gap. Run it AFTER ``alembic upgrade head`` against the
target database (Postgres in CI):

    python scripts/ci_lifespan_smoke.py

Exit code 0 = startup is healthy on this dialect; non-zero = a real failure
(prints the offending traceback) so CI fails before a deploy can.

It is intentionally strict: ``_run_db_bootstrap`` is called directly (unguarded)
so a dialect/schema failure surfaces here, even though the production lifespan
now swallows such errors to keep serving ``/health``.
"""
from __future__ import annotations

import os
import sys
import traceback

# Ensure the repo root is importable when invoked as `python scripts/...`
# (the runner's CWD is the repo root but it is not on sys.path by default).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Force the real startup path on regardless of the inherited CI env.
os.environ["UKIP_SKIP_STARTUP_SIDE_EFFECTS"] = "0"
# Engine is not present in this job; the Python fallback path is what we test.
os.environ.pop("ENGINE_GRPC_URL", None)


def main() -> int:
    # 1. Strict: run the real DB bootstrap directly. Raises on a dialect/schema
    #    failure (the exact class of bug that broke the production deploy).
    from backend.main import _run_db_bootstrap

    try:
        _run_db_bootstrap()
    except Exception:
        print("FAIL: _run_db_bootstrap() raised against the target database:\n", file=sys.stderr)
        traceback.print_exc()
        return 1
    print("OK: lifespan DB bootstrap (create_all + seed + migrate) succeeded")

    # 2. Full app lifespan via TestClient, then assert /health serves and the DB
    #    probe is green — proving the whole startup path comes up on this dialect.
    from fastapi.testclient import TestClient

    from backend.main import app

    try:
        with TestClient(app) as client:
            resp = client.get("/health")
    except Exception:
        print("FAIL: app lifespan raised while starting via TestClient:\n", file=sys.stderr)
        traceback.print_exc()
        return 1

    if resp.status_code != 200:
        print(f"FAIL: /health returned HTTP {resp.status_code}", file=sys.stderr)
        return 1

    body = resp.json()
    print(f"OK: /health -> {body}")
    if body.get("database") != "ok":
        print(f"FAIL: /health reports database={body.get('database')!r}", file=sys.stderr)
        return 1

    print("OK: lifespan smoke passed on the target database dialect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
