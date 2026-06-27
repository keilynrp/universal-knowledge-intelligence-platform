"""Backfill enrichment_work_type for existing entities that have a DOI but no work type.

Usage: python -m backend.scripts.backfill_work_type [--org-id N] [--delay S]

Queries RawEntity rows where enrichment_doi IS NOT NULL and enrichment_work_type IS NULL,
then re-fetches each from OpenAlex by DOI to populate work_type.
Idempotent: only processes rows missing the value. Org-scoped when --org-id is provided.
--delay throttles between API calls to stay in OpenAlex's polite pool.
"""
import argparse
import time
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import RawEntity
from backend.adapters.enrichment.openalex import OpenAlexAdapter


def run_backfill(
    db: Session,
    org_id: Optional[int],
    adapter=None,
    delay: float = 0.0,
) -> int:
    """Populate enrichment_work_type from OpenAlex for rows that lack it.

    `adapter` is injectable for testing (must expose `search_by_doi(doi)`
    returning an object with a `work_type` attribute, or None).
    Returns the count of rows updated.
    """
    adapter = adapter or OpenAlexAdapter()

    q = db.query(RawEntity).filter(
        RawEntity.enrichment_doi.isnot(None),
        RawEntity.enrichment_work_type.is_(None),
    )
    if org_id is not None:
        q = q.filter(RawEntity.org_id == org_id)

    updated = 0
    for i, row in enumerate(q.all()):
        if delay and i:
            time.sleep(delay)
        rec = adapter.search_by_doi(row.enrichment_doi)
        if rec is not None and getattr(rec, "work_type", None) is not None:
            row.enrichment_work_type = rec.work_type
            updated += 1

    db.commit()
    return updated


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Backfill enrichment_work_type from OpenAlex for entities with a DOI."
    )
    ap.add_argument("--org-id", type=int, default=None, help="Limit backfill to one org")
    ap.add_argument("--delay", type=float, default=0.0, help="Seconds to wait between API calls")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        n = run_backfill(db, org_id=args.org_id, delay=args.delay)
        print(f"work_type backfilled for {n} entities")
    finally:
        db.close()


if __name__ == "__main__":
    main()
