"""Backfill works_2yr for existing journals, then recompute nif_bayes.

Usage: python -m backend.scripts.backfill_nif_bayes [--org-id N] [--refresh] [--delay 0.1]

Iterates journal_metrics rows directly (one OpenAlex /sources fetch per journal,
not per work), populates works_2yr, then runs the Empirical-Bayes batch.
Idempotent and org-scoped. With --refresh, clears the Redis-backed source cache
first (via clear_source_cache, #89) so stale cached dicts lacking works_2yr are
re-fetched. --delay throttles between fetches to stay in OpenAlex's polite pool.
"""
import argparse
import time
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import JournalMetric
from backend.adapters.enrichment.openalex import OpenAlexAdapter, clear_source_cache
from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes


def run_backfill(db: Session, org_id: Optional[int], refresh: bool = False,
                 adapter=None, delay: float = 0.0) -> int:
    """Populate works_2yr from OpenAlex per journal, then recompute nif_bayes.

    `adapter` is injectable for testing (must expose `fetch_source_metrics(source_id)`
    returning a JournalMetrics with `works_2yr`). Returns rows updated by the batch.
    """
    if refresh:
        clear_source_cache()                       # Redis: drop stale pre-works_2yr dicts
    adapter = adapter or OpenAlexAdapter()

    q = db.query(JournalMetric).filter(JournalMetric.source_id.isnot(None))
    if org_id is not None:
        q = q.filter(JournalMetric.org_id == org_id)

    for i, row in enumerate(q.all()):
        if delay and i:
            time.sleep(delay)
        jm = adapter.fetch_source_metrics(row.source_id)
        if jm is not None and getattr(jm, "works_2yr", None) is not None:
            row.works_2yr = jm.works_2yr
    db.flush()
    updated = normalize_impact_factors_bayes(db, org_id=org_id)
    db.commit()
    return updated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org-id", type=int, default=None)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--delay", type=float, default=0.0)
    args = ap.parse_args()
    db = SessionLocal()
    try:
        n = run_backfill(db, org_id=args.org_id, refresh=args.refresh, delay=args.delay)
        print(f"nif_bayes recomputed for {n} journals")
    finally:
        db.close()


if __name__ == "__main__":
    main()
