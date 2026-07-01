"""Lake status — verify a scheduled refresh actually ran.

Prints the incremental watermark, per-table row counts, journal coverage and the
year span so the monthly cron can be checked at a glance:

    python -m backend.openalex_lake.status
"""
from __future__ import annotations

import json
import logging
import os

import duckdb

from backend.openalex_lake.config import LakeSettings
from backend.openalex_lake.store import LakeStore

logger = logging.getLogger(__name__)


def lake_status(store: LakeStore) -> dict:
    """A compact operational snapshot of the lake."""
    yr = store.con.execute(
        "SELECT min(publication_year), max(publication_year) FROM fact_works"
    ).fetchone()
    journals = store.con.execute("SELECT count(*) FROM v_source_coverage").fetchone()[0]
    return {
        "works_watermark": store.get_watermark("works"),
        "journals": journals,
        "year_min": yr[0],
        "year_max": yr[1],
        "tables": store.summary(),
    }


def resolve_status(db_path: str) -> dict:
    """Return the lake status, or a friendly marker when it can't be read.

    Two common non-error states: the lake file doesn't exist yet (no pull has
    run), or it's write-locked (a pull is running) — DuckDB can't open a
    read-only handle while another process holds the write lock.
    """
    if not os.path.exists(db_path):
        return {"lake": "not_initialized", "db_path": db_path,
                "hint": "run: python -m backend.openalex_lake.pull_works"}
    try:
        with LakeStore(db_path, read_only=True) as store:
            return lake_status(store)
    except duckdb.IOException:
        return {"lake": "locked", "db_path": db_path,
                "hint": "a pull is currently running; re-check once it finishes"}


def main() -> None:  # pragma: no cover - thin CLI wrapper
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(resolve_status(LakeSettings().db_path), indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
