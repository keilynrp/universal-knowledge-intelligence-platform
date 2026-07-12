"""Bounded backfill of retrospective events from trustworthy source timestamps.

Usage: python -m backend.scripts.backfill_retrospective_events [--org-id N]

Seeds the retrospective layer with history that predates event emission, using
only *trustworthy* source timestamps already stored on operational rows (task
3.5). Deliberately bounded to the two families that carry a reliable timestamp:

- ``journal_metric.computed`` from ``JournalMetric.nif_updated_at`` (rows that
  have a computed NIF), occurred_at = nif_updated_at.
- ``authority.accepted`` from ``AuthorityRecord.confirmed_at`` (confirmed rows),
  occurred_at = confirmed_at.

Not backfilled (no trustworthy per-event timestamp): enrichment lifecycle,
authority rejections, candidate creation. Idempotent — keys derive from the
source timestamp, matching live emission, so re-runs (and overlap with live
events) do not duplicate. This is an explicit admin action and is NOT gated by
``UKIP_RETRO_EVENTS``: running it is the intent.
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend import models
from backend.retrospective import writer

logger = logging.getLogger(__name__)


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def _try(fn) -> bool:
    try:
        fn()
        return True
    except Exception:  # noqa: BLE001 — one bad row must not abort the backfill
        logger.warning("retrospective backfill row failed; continuing", exc_info=True)
        return False


def backfill_journal_metrics(db: Session, org_id: Optional[int]) -> int:
    q = (
        db.query(models.JournalMetric)
        .filter(models.JournalMetric.normalized_impact_factor.isnot(None))
        .filter(models.JournalMetric.nif_updated_at.isnot(None))
    )
    if org_id is not None:
        q = q.filter(models.JournalMetric.org_id == org_id)
    written = 0
    for r in q.all():
        occurred = _naive(r.nif_updated_at)
        written += int(_try(lambda r=r, occurred=occurred: writer.record_event(
            db,
            event_type="journal_metric.computed",
            org_id=r.org_id,
            domain_object_type="journal",
            domain_object_id=f"issn:{r.issn_l}",
            occurred_at=occurred,
            source="journal_normalization",
            actor_type="job",
            idempotency_key=f"{r.issn_l}:{occurred.isoformat()}",
            payload={
                "nif": r.normalized_impact_factor,
                "prior_nif": None,
                "nif_field": r.nif_field,
                "field_median": None,
                "backfilled": True,
            },
            lineage={"source_id": r.source_id} if r.source_id else None,
        )))
    return written


def backfill_authority_accepted(db: Session, org_id: Optional[int]) -> int:
    q = (
        db.query(models.AuthorityRecord)
        .filter(models.AuthorityRecord.status == "confirmed")
        .filter(models.AuthorityRecord.confirmed_at.isnot(None))
    )
    if org_id is not None:
        q = q.filter(models.AuthorityRecord.org_id == org_id)
    written = 0
    for r in q.all():
        occurred = _naive(r.confirmed_at)
        written += int(_try(lambda r=r, occurred=occurred: writer.record_event(
            db,
            event_type="authority.accepted",
            org_id=r.org_id,
            domain_object_type="authority_record",
            domain_object_id=str(r.id),
            occurred_at=occurred,
            source="authority_review",
            actor_type="user",
            idempotency_key=f"{r.id}:accepted:{occurred.isoformat()}",
            payload={
                "decision": "accepted",
                "field_name": r.field_name,
                "authority_source": r.authority_source,
                "authority_id": r.authority_id,
                "canonical_label": r.canonical_label,
                "confidence": r.confidence,
                "backfilled": True,
            },
        )))
    return written


def run_backfill(db: Session, org_id: Optional[int] = None) -> dict[str, int]:
    """Backfill both families and commit. Returns per-family counts written."""
    result = {
        "journal_metric": backfill_journal_metrics(db, org_id),
        "authority_accepted": backfill_authority_accepted(db, org_id),
    }
    db.commit()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org-id", type=int, default=None)
    args = ap.parse_args()
    db = SessionLocal()
    try:
        result = run_backfill(db, org_id=args.org_id)
        print(f"retrospective backfill: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
