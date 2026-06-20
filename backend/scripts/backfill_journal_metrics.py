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


def _configure_logging() -> None:
    """Operator-friendly logging: keep our INFO output, but quiet httpx's
    per-request INFO lines (e.g. the 429s the OpenAlex adapter already retries),
    which otherwise look alarming. Warnings/errors still surface, and the adapter
    logs its own clear "rate-limited — retrying" message when a retry happens.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill journal metrics from stored DOIs.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N works (omit for all).")
    parser.add_argument("--all", action="store_true",
                        help="Re-process works that already have enrichment_issn_l "
                             "(default: only works still missing it).")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="Seconds to sleep between works (polite-pool throttle "
                             "to avoid OpenAlex 429s; default 0.2).")
    parser.add_argument("--refresh", action="store_true",
                        help="Clear the cached OpenAlex /sources metrics first so a "
                             "changed nif_field resolver is recomputed (the source "
                             "cache is Redis-backed and survives deploys).")
    args = parser.parse_args()

    _configure_logging()

    db = SessionLocal()
    try:
        result = backfill_all(db, only_missing=not args.all, limit=args.limit,
                              delay=args.delay, refresh=args.refresh)
    finally:
        db.close()

    print(
        "journal backfill done: "
        f"processed={result['processed']} written={result['written']} "
        f"skipped={result['skipped']} errors={result['errors']}"
    )


if __name__ == "__main__":
    main()
