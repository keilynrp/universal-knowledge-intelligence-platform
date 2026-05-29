"""One-shot cleanup: delete legacy entity_relationships CO_AUTHOR rows after the
V2 coauthorship cutover.

Run ONLY after:
  1. migrate_coauthor_graph has populated the V2 tables, and
  2. COAUTHOR_V2_READ has served from V2 stably (spec §F5 precondition), and
  3. /diagnostics reports coverage_pct == 100.

Usage:
  python -m backend.scripts.cleanup_legacy_coauthor            # delete
  python -m backend.scripts.cleanup_legacy_coauthor --dry-run  # count only

Only touches relation_type='CO_AUTHOR'; all other edge types are untouched.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from backend import models
from backend.database import SessionLocal

logger = logging.getLogger("cleanup_legacy_coauthor")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def run(db, *, dry_run: bool = False) -> int:
    """Delete legacy CO_AUTHOR edges. Returns the number of rows affected
    (the count that would be deleted in dry-run)."""
    q = db.query(models.EntityRelationship).filter(
        models.EntityRelationship.relation_type == "CO_AUTHOR"
    )
    if dry_run:
        return q.count()
    deleted = q.delete(synchronize_session=False)
    db.commit()
    logger.info("deleted %d legacy CO_AUTHOR rows", deleted)
    return deleted


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count without deleting.")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        n = run(db, dry_run=args.dry_run)
    finally:
        db.close()
    logger.info("%s: %d CO_AUTHOR rows", "would delete" if args.dry_run else "deleted", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
