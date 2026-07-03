"""Backfill the ``journal`` attribute on science entities (issue #102).

Entities imported/enriched via OpenAlex store the journal's linking ISSN in the
physical ``enrichment_issn_l`` column, but the journal *name* was never written
onto the entity — it only lives in the ``journal_metrics`` table. The OLAP
``journal`` dimension therefore stayed empty for already-ingested works.

This script fills ``attributes_json["journal"]`` for science entities that have
an ``enrichment_issn_l`` but no journal name yet, resolving the display name from
``JournalMetric`` via the ISSN-L. It never overwrites an existing non-empty
``journal`` value and records provenance in
``attrs["_journal_backfill"] = {"issn_l": "<issn>", "source": "journal_metrics"}``.
Safe to re-run.

Usage
-----
    python -m backend.scripts.backfill_science_journal --dry-run
    python -m backend.scripts.backfill_science_journal
    python -m backend.scripts.backfill_science_journal --org-id 1 --limit 100
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Optional

from backend import models
from backend.database import SessionLocal

logger = logging.getLogger(__name__)


def _parse_attrs(raw: Optional[str]) -> dict:
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _build_issn_name_map(db) -> dict[str, str]:
    """issn_l → display_name from journal_metrics (non-empty names only)."""
    mapping: dict[str, str] = {}
    for issn_l, name in db.query(
        models.JournalMetric.issn_l, models.JournalMetric.display_name
    ).filter(
        models.JournalMetric.issn_l.isnot(None),
        models.JournalMetric.display_name.isnot(None),
    ):
        if issn_l and isinstance(name, str) and name.strip():
            mapping[issn_l] = name.strip()
    return mapping


def _candidates(db, org_id: Optional[int], limit: Optional[int]):
    q = db.query(models.RawEntity).filter(
        models.RawEntity.domain == "science",
        models.RawEntity.enrichment_issn_l.isnot(None),
    )
    if org_id is not None:
        q = q.filter(models.RawEntity.org_id == org_id)
    if limit is not None:
        q = q.limit(limit)
    return q


def run_backfill(
    dry_run: bool,
    org_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict[str, int]:
    db = SessionLocal()
    scanned = filled = already = no_metric = 0
    try:
        issn_name = _build_issn_name_map(db)
        for entity in _candidates(db, org_id=org_id, limit=limit):
            scanned += 1
            attrs = _parse_attrs(entity.attributes_json)
            existing = attrs.get("journal")
            if isinstance(existing, str) and existing.strip():
                already += 1
                continue
            name = issn_name.get(entity.enrichment_issn_l)
            if not name:
                no_metric += 1
                continue
            attrs["journal"] = name
            attrs["_journal_backfill"] = {
                "issn_l": entity.enrichment_issn_l,
                "source": "journal_metrics",
            }
            entity.attributes_json = json.dumps(attrs, ensure_ascii=False)
            filled += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()
        return {
            "scanned": scanned,
            "filled": filled,
            "already_present": already,
            "no_journal_metric": no_metric,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill attributes_json['journal'] on science entities from "
            "journal_metrics via enrichment_issn_l. Never overwrites an existing "
            "value. Safe to re-run."
        )
    )
    parser.add_argument("--dry-run", action="store_true", help="Report counts without committing.")
    parser.add_argument("--org-id", type=int, default=None, help="Restrict to a single org.")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of rows scanned.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run_backfill(dry_run=args.dry_run, org_id=args.org_id, limit=args.limit)
    mode = "DRY-RUN" if args.dry_run else "COMMIT"
    logger.info(
        "[%s] scanned=%d filled=%d already_present=%d no_journal_metric=%d",
        mode,
        result["scanned"],
        result["filled"],
        result["already_present"],
        result["no_journal_metric"],
    )


if __name__ == "__main__":
    main()
