"""CLI for the one-shot legacy -> V2 coauthorship migration.

Usage:
  python -m backend.scripts.migrate_coauthor_graph --dry-run
  python -m backend.scripts.migrate_coauthor_graph --domain default
  python -m backend.scripts.migrate_coauthor_graph            # full run, all domains

Idempotent — safe to re-run. Pair with a prod-replica --dry-run first to audit
name_key collapse and edge counts (see spec §10 cutover).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional

from backend.coauthorship.migration import migrate_coauthor_graph
from backend.database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", help="Restrict to a single domain id.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan + report counts without writing anything.",
    )
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        stats = migrate_coauthor_graph(db, dry_run=args.dry_run, domain=args.domain)
    finally:
        db.close()

    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
