"""Backfill imported text fields that contain provider HTML artifacts.

Usage:
    python -m backend.scripts.normalize_imported_text --dry-run
    python -m backend.scripts.normalize_imported_text
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from backend import models
from backend.database import SessionLocal
from backend.services.text_normalization import normalize_import_value


_TEXT_FIELDS = (
    "primary_label",
    "secondary_label",
    "canonical_id",
    "enrichment_doi",
    "enrichment_concepts",
    "enrichment_source",
)


def _normalize_json_blob(raw: str | None) -> tuple[str | None, bool]:
    if not raw:
        return raw, False
    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError:
        normalized = normalize_import_value(raw)
        return normalized, normalized != raw

    normalized = normalize_import_value(parsed)
    if normalized == parsed:
        return raw, False
    return json.dumps(normalized, ensure_ascii=False, default=str), True


def normalize_entity(entity: models.RawEntity) -> bool:
    changed = False
    for field in _TEXT_FIELDS:
        current = getattr(entity, field)
        if current is None:
            continue
        normalized = normalize_import_value(current)
        if normalized != current:
            setattr(entity, field, normalized)
            changed = True

    for field in ("attributes_json", "normalized_json"):
        normalized_blob, blob_changed = _normalize_json_blob(getattr(entity, field))
        if blob_changed:
            setattr(entity, field, normalized_blob)
            changed = True

    return changed


def run(*, dry_run: bool = False, limit: int | None = None, org_id: int | None = None) -> dict[str, int]:
    db = SessionLocal()
    scanned = 0
    updated = 0
    try:
        query = db.query(models.RawEntity).order_by(models.RawEntity.id)
        if org_id is not None:
            query = query.filter(models.RawEntity.org_id == org_id)
        if limit is not None:
            query = query.limit(limit)

        for entity in query.yield_per(500):
            scanned += 1
            if normalize_entity(entity):
                updated += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()
        return {"scanned": scanned, "updated": updated}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize provider HTML artifacts in imported entity text.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without committing them.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of scanned entities.")
    parser.add_argument("--org-id", type=int, default=None, help="Only scan one organization.")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, limit=args.limit, org_id=args.org_id)
    mode = "dry run" if args.dry_run else "committed"
    print(f"{mode}: scanned={result['scanned']} updated={result['updated']}")


if __name__ == "__main__":
    main()
