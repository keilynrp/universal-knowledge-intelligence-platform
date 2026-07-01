"""Lake status — verify a scheduled refresh actually ran.

Prints the incremental watermark, per-table row counts, journal coverage and the
year span so the monthly cron can be checked at a glance:

    python -m backend.openalex_lake.status
"""
from __future__ import annotations

import json
import logging

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


def main() -> None:  # pragma: no cover - thin CLI wrapper
    logging.basicConfig(level=logging.INFO)
    settings = LakeSettings()
    with LakeStore(settings.db_path, read_only=True) as store:
        print(json.dumps(lake_status(store), indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
