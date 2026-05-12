"""
One-time backfill: extract and cache country codes for existing entities.

Usage:
    python -m scripts.backfill_country [--batch-size 500] [--dry-run]
"""
import argparse
import json
import logging
import sys

from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill extracted_country in attributes_json")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Import after parsing to avoid env issues when checking --help
    from backend.analyzers.geographic import extract_country
    from backend.database import engine

    updated = 0
    skipped = 0

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, attributes_json FROM raw_entities WHERE attributes_json IS NOT NULL"
        )).fetchall()

        batch: list[tuple[str, int]] = []

        for row in rows:
            entity_id = row[0]
            attrs_json = row[1]

            try:
                attrs = json.loads(attrs_json) if attrs_json else {}
            except (ValueError, TypeError):
                skipped += 1
                continue

            if not isinstance(attrs, dict):
                skipped += 1
                continue

            # Skip if already cached
            if attrs.get("extracted_country"):
                skipped += 1
                continue

            # Try to extract country from affiliation fields
            affiliation = None
            for key in ("affiliation", "affiliations", "institution", "institutions", "organization"):
                val = attrs.get(key)
                if val:
                    affiliation = str(val) if not isinstance(val, str) else val
                    break

            if not affiliation:
                skipped += 1
                continue

            country_code = extract_country(affiliation)
            if not country_code:
                skipped += 1
                continue

            attrs["extracted_country"] = country_code
            new_json = json.dumps(attrs)
            batch.append((new_json, entity_id))
            updated += 1

            if len(batch) >= args.batch_size:
                if not args.dry_run:
                    for new_attrs, eid in batch:
                        conn.execute(
                            text("UPDATE raw_entities SET attributes_json = :attrs WHERE id = :id"),
                            {"attrs": new_attrs, "id": eid},
                        )
                    conn.commit()
                logger.info("Committed batch of %d updates (total: %d)", len(batch), updated)
                batch = []

        # Final batch
        if batch and not args.dry_run:
            for new_attrs, eid in batch:
                conn.execute(
                    text("UPDATE raw_entities SET attributes_json = :attrs WHERE id = :id"),
                    {"attrs": new_attrs, "id": eid},
                )
            conn.commit()

    mode = "DRY RUN" if args.dry_run else "COMMITTED"
    logger.info("Done (%s). Updated: %d, Skipped: %d, Total scanned: %d", mode, updated, skipped, len(rows))


if __name__ == "__main__":
    main()
