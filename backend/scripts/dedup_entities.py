"""Deduplicate RawEntity records: fix wrong enrichment_doi assignments and
merge true duplicates.

Background
----------
After the canonical_id/entity_type backfill (2026-05-26), 163 records
remained with both fields NULL because the unique constraint
``uq_raw_entities_canonical_global (domain, entity_type, canonical_id)``
blocked them.  Analysis revealed two distinct problems:

1. **Wrong DOI (107 records)** — OpenAlex enrichment assigned a DOI that
   belongs to a different publication.  These are legitimate, distinct
   records whose ``enrichment_doi`` is simply wrong.

2. **True duplicates (56 records)** — The same publication was imported
   multiple times.  One copy already holds ``canonical_id``; the others
   are pure noise.

Strategy
--------
**Phase 1 — Fix wrong DOIs:**
For each both-NULL record whose ``primary_label`` differs from the
"winner" (the record that owns the DOI in ``canonical_id``):
  - Clear ``enrichment_doi`` (it's incorrect).
  - Set ``entity_type = "publication"`` (they are valid science records).
  - Set ``enrichment_status = "pending"`` so the worker retries.
  - Record the change in ``attrs._dedup_fix``.

**Phase 2 — Merge true duplicates:**
For each both-NULL record whose ``primary_label`` matches the winner:
  - Compare attribute richness (count of non-null fields in attrs).
  - If the duplicate has richer attrs than the winner, merge them into
    the winner first.
  - Hard-delete the duplicate.

Usage
-----
    python -m backend.scripts.dedup_entities --dry-run
    python -m backend.scripts.dedup_entities
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Optional

from backend import models
from backend.database import SessionLocal

logger = logging.getLogger(__name__)


def _decode_json(value: Optional[str]) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _attr_richness(attrs: dict[str, Any]) -> int:
    """Count non-null, non-empty leaf values as a proxy for data richness."""
    count = 0
    for v in attrs.values():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if isinstance(v, (list, dict)) and not v:
            continue
        count += 1
    return count


def _title_fingerprint(title: Optional[str]) -> str:
    if not title:
        return ""
    return " ".join(title.strip().lower().split())[:80]


def _find_winner(db, doi: str) -> Optional[models.RawEntity]:
    """Find the record that already owns this DOI in canonical_id."""
    return (
        db.query(models.RawEntity)
        .filter(
            models.RawEntity.canonical_id == doi,
            models.RawEntity.entity_type.isnot(None),
        )
        .first()
    )


def _merge_attrs_into_winner(winner: models.RawEntity, donor: models.RawEntity) -> bool:
    """If the donor has richer attributes, merge missing keys into the winner.
    Returns True if the winner was modified."""
    winner_attrs = _decode_json(winner.attributes_json)
    donor_attrs = _decode_json(donor.attributes_json)

    if _attr_richness(donor_attrs) <= _attr_richness(winner_attrs):
        return False

    merged = False
    for key, value in donor_attrs.items():
        if key.startswith("_"):
            continue
        if key not in winner_attrs or winner_attrs[key] in (None, "", [], {}):
            winner_attrs[key] = value
            merged = True

    if merged:
        winner_attrs["_dedup_merged_from"] = donor.id
        winner.attributes_json = json.dumps(winner_attrs, ensure_ascii=False)

    return merged


def run(*, dry_run: bool) -> dict[str, int]:
    db = SessionLocal()
    fixed_wrong_doi = 0
    merged_duplicates = 0
    deleted_duplicates = 0
    skipped = 0

    try:
        both_null = (
            db.query(models.RawEntity)
            .filter(
                models.RawEntity.canonical_id.is_(None),
                models.RawEntity.entity_type.is_(None),
            )
            .order_by(models.RawEntity.id.asc())
            .all()
        )

        for entity in both_null:
            doi = entity.enrichment_doi
            if not doi:
                skipped += 1
                continue

            winner = _find_winner(db, doi)
            if not winner:
                skipped += 1
                continue

            entity_fp = _title_fingerprint(entity.primary_label)
            winner_fp = _title_fingerprint(winner.primary_label)

            if entity_fp and winner_fp and entity_fp == winner_fp:
                # TRUE DUPLICATE — merge attrs if richer, then delete
                _merge_attrs_into_winner(winner, entity)
                db.delete(entity)
                deleted_duplicates += 1
            else:
                # WRONG DOI — clear bad enrichment, set entity_type, requeue
                attrs = _decode_json(entity.attributes_json)
                attrs["_dedup_fix"] = {
                    "action": "cleared_wrong_enrichment_doi",
                    "old_enrichment_doi": doi,
                    "reason": f"DOI belongs to entity id={winner.id}, title mismatch",
                }
                entity.enrichment_doi = None
                entity.entity_type = "publication"
                entity.enrichment_status = "pending"
                entity.attributes_json = json.dumps(attrs, ensure_ascii=False)
                fixed_wrong_doi += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()

        return {
            "total_processed": len(both_null),
            "fixed_wrong_doi": fixed_wrong_doi,
            "deleted_duplicates": deleted_duplicates,
            "skipped": skipped,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fix wrong enrichment_doi assignments and merge true duplicate "
            "RawEntity records. Safe to re-run (idempotent on both-NULL filter)."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without committing changes.",
    )
    args = parser.parse_args()

    result = run(dry_run=args.dry_run)
    mode = "dry run" if args.dry_run else "committed"
    print(
        f"{mode}: "
        f"total={result['total_processed']} "
        f"fixed_wrong_doi={result['fixed_wrong_doi']} "
        f"deleted_duplicates={result['deleted_duplicates']} "
        f"skipped={result['skipped']}"
    )


if __name__ == "__main__":
    main()
