"""
Backfill CO_AUTHOR edges in entity_relationships for entities that already
have `enrichment_authors` (or `authors`) populated in attributes_json but
were enriched before the coauthor-extraction hook landed in
enrichment_worker.py.

Usage:
  python -m backend.scripts.backfill_coauthor_edges                   # all domains
  python -m backend.scripts.backfill_coauthor_edges --domain default  # one domain
  python -m backend.scripts.backfill_coauthor_edges --dry-run         # preview only

Idempotent: extract_coauthor_edges() upserts on (relation_type='CO_AUTHOR',
notes='A||B'), so re-running just bumps weights — typically you want to
purge existing rows first when re-running for an audit. See --reset.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional

from sqlalchemy import and_, or_, text

from backend import models
from backend.analyzers.coauthorship import extract_coauthor_edges
from backend.database import SessionLocal

logger = logging.getLogger("backfill_coauthor_edges")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def _authors_from_attrs(attrs_json: Optional[str]) -> list[str]:
    if not attrs_json:
        return []
    try:
        attrs = json.loads(attrs_json) or {}
    except (ValueError, TypeError):
        return []
    raw = attrs.get("enrichment_authors") or attrs.get("authors")
    if not raw:
        return []
    if isinstance(raw, str):
        return [a.strip() for a in raw.split(";") if a.strip()]
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if a and str(a).strip()]
    return []


def backfill(
    domain: Optional[str] = None,
    dry_run: bool = False,
    reset: bool = False,
) -> dict[str, int]:
    """Walk RawEntity table and (re)generate CO_AUTHOR edges."""
    db = SessionLocal()
    stats = {"scanned": 0, "with_authors": 0, "edges_generated": 0, "errors": 0}
    try:
        if reset and not dry_run:
            deleted = (
                db.query(models.EntityRelationship)
                .filter(models.EntityRelationship.relation_type == "CO_AUTHOR")
                .delete(synchronize_session=False)
            )
            db.commit()
            logger.info("reset: deleted %d existing CO_AUTHOR rows", deleted)

        query = db.query(models.RawEntity)
        if domain:
            if domain == "default":
                query = query.filter(
                    or_(
                        models.RawEntity.domain == domain,
                        models.RawEntity.domain.is_(None),
                    )
                )
            else:
                query = query.filter(models.RawEntity.domain == domain)

        for entity in query.yield_per(500):
            stats["scanned"] += 1
            authors = _authors_from_attrs(entity.attributes_json)
            if len(authors) < 2:
                continue
            stats["with_authors"] += 1

            if dry_run:
                stats["edges_generated"] += len(authors) - 1  # rough estimate
                continue

            try:
                extract_coauthor_edges(
                    entity.id,
                    authors,
                    db,
                    org_id=getattr(entity, "org_id", None),
                )
                stats["edges_generated"] += 1
            except Exception:
                logger.exception("entity %s failed", entity.id)
                stats["errors"] += 1
                db.rollback()
                continue

            # Commit in batches to avoid one giant transaction
            if stats["with_authors"] % 100 == 0:
                db.commit()
                logger.info(
                    "progress: %s entities scanned, %s with co-authors",
                    stats["scanned"],
                    stats["with_authors"],
                )

        if not dry_run:
            db.commit()
    finally:
        db.close()
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", help="Restrict to a single domain id")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count entities + estimated edges without writing.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing CO_AUTHOR rows before backfilling.",
    )
    args = parser.parse_args(argv)

    stats = backfill(domain=args.domain, dry_run=args.dry_run, reset=args.reset)
    logger.info("done: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
