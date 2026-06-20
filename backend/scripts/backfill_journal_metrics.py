"""Backfill ``journal_metrics`` for works enriched before the journal feature.

Looks up each completed work's OpenAlex source via its stored DOI and upserts
the journal's NIF base + APC, WITHOUT running the full enrichment worker (whose
legacy co-author edge path is not idempotent and would roll the transaction
back). Safe to re-run.

Run from the ops container (off HTTP):
    python -m backend.scripts.backfill_journal_metrics            # missing only
    python -m backend.scripts.backfill_journal_metrics --limit 5  # small test batch
    python -m backend.scripts.backfill_journal_metrics --all      # re-touch every DOI work

After it finishes, run "Recompute NIF" (POST /journals/normalize) so the
normalized_impact_factor column is populated.
"""
from __future__ import annotations

import argparse
import logging

from backend.database import SessionLocal
from backend.services.journal_backfill import backfill_all

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill journal metrics from stored DOIs.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N works (omit for all).")
    parser.add_argument("--all", action="store_true",
                        help="Re-process works that already have enrichment_issn_l "
                             "(default: only works still missing it).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    db = SessionLocal()
    try:
        result = backfill_all(db, only_missing=not args.all, limit=args.limit)
    finally:
        db.close()

    print(
        "journal backfill done: "
        f"processed={result['processed']} written={result['written']} "
        f"skipped={result['skipped']} errors={result['errors']}"
    )


if __name__ == "__main__":
    main()
