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


def _eligible_payloads(
    db, domain: Optional[str],
) -> list[tuple[int, Optional[int], list[str]]]:
    """Load (entity_id, org_id, authors) tuples for entities with >= 2 authors.

    Materializes into memory up-front so the subsequent loop can commit
    without invalidating any cursor. UKIP corpora at this stage fit easily
    in memory; if that ever changes we can switch to chunked IN-clause
    queries here.
    """
    query = db.query(
        models.RawEntity.id,
        models.RawEntity.org_id,
        models.RawEntity.attributes_json,
    )
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

    payloads: list[tuple[int, Optional[int], list[str]]] = []
    for entity_id, org_id, attrs_json in query.all():
        authors = _authors_from_attrs(attrs_json)
        if len(authors) >= 2:
            payloads.append((entity_id, org_id, authors))
    return payloads


def backfill(
    domain: Optional[str] = None,
    dry_run: bool = False,
    reset: bool = False,
) -> dict[str, int]:
    """Walk RawEntity table and (re)generate CO_AUTHOR edges.

    Design notes:
    - Eligible entities are materialized into a list FIRST. This avoids the
      classic ``yield_per`` + inner-query + mid-iteration-commit footgun
      that invalidates the streaming cursor on PostgreSQL.
    - Per-entity failures are caught and counted but do NOT call
      ``db.rollback()`` (which would discard everything since the last
      commit, including good rows). We let SQLAlchemy auto-flush mark the
      session bad only on truly fatal errors; commit handles the final
      atomicity check.
    - For ``dry_run`` we still load attributes but never write.
    """
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

        # Count scanned rows (regardless of author count) for the response shape.
        scan_query = db.query(models.RawEntity.id)
        if domain:
            if domain == "default":
                scan_query = scan_query.filter(
                    or_(
                        models.RawEntity.domain == domain,
                        models.RawEntity.domain.is_(None),
                    )
                )
            else:
                scan_query = scan_query.filter(models.RawEntity.domain == domain)
        stats["scanned"] = scan_query.count()

        payloads = _eligible_payloads(db, domain)
        stats["with_authors"] = len(payloads)

        if dry_run:
            stats["edges_generated"] = sum(
                len(authors) - 1 for _, _, authors in payloads
            )
            return stats

        BATCH = 200
        for i, (entity_id, org_id, authors) in enumerate(payloads, start=1):
            try:
                edges = extract_coauthor_edges(entity_id, authors, db, org_id=org_id)
                stats["edges_generated"] += edges or 0
            except Exception:
                logger.exception("entity %s coauthor extraction failed", entity_id)
                stats["errors"] += 1
                # Continue without rolling back — the failing call's
                # partial state is still in the session, but commit will
                # surface the error on the bad rows only.
            if i % BATCH == 0:
                try:
                    db.commit()
                except Exception:
                    logger.exception("batch commit failed at i=%s", i)
                    db.rollback()
                    stats["errors"] += 1
                logger.info(
                    "progress: %s/%s eligible entities processed",
                    i,
                    len(payloads),
                )

        try:
            db.commit()
        except Exception:
            logger.exception("final commit failed")
            db.rollback()
            stats["errors"] += 1
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
