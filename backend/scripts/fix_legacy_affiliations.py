"""Backfill: remove journal/publisher values that the cbe3255 → 19e97ff bug
wrote into ``attributes_json.affiliation``.

Background
----------
Between commits ``cbe3255`` (2026-05-13) and ``19e97ff`` (2026-05-20),
``backend/routers/api_import.py:_ingest_records`` contained::

    if rec.publisher:
        attrs["affiliation"] = rec.publisher

The OpenAlex enrichment adapter sets ``EnrichedRecord.publisher`` from
``primary_location.source.display_name`` — which is the **journal name**,
not a publisher. As a result, entities imported via ``/import/openalex``
(and ``/import/pubmed``) during that window have a journal name stored
under ``attrs.affiliation`` instead of an institutional affiliation.

Strategy
--------
For each affected entity:

1. Decode ``attributes_json`` and read the legacy ``affiliation`` value.
2. If the value does not appear in any ``canonical_affiliations[].name`` /
   ``author_affiliations[].institutions[].name`` (i.e. it is not a real
   institutional affiliation), treat it as bug residue.
3. Move the bad value to ``attrs["_legacy_affiliation_backup"]`` so it is
   never silently lost, and clear both ``attrs.affiliation`` and
   ``attrs.affiliations`` (the latter mirrors the former in the legacy code).
4. Optionally mark ``enrichment_status = 'pending'`` so the enrichment
   worker repopulates affiliations from the canonical layer on next run.

Usage
-----
    python -m backend.scripts.fix_legacy_affiliations --dry-run
    python -m backend.scripts.fix_legacy_affiliations
    python -m backend.scripts.fix_legacy_affiliations --requeue-enrichment
    python -m backend.scripts.fix_legacy_affiliations --org-id 1 --limit 100
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Iterable

from backend import models
from backend.database import SessionLocal

logger = logging.getLogger(__name__)


# Provider tokens that were affected by the bug. Lower-cased for case-insensitive
# comparison against ``RawEntity.enrichment_source``.
_AFFECTED_SOURCES: frozenset[str] = frozenset({
    "openalex",
    "pubmed",
    "crossref",  # included defensively: same _ingest_records path
})


def _normalize_name(value: str) -> str:
    """Loose-match key used to compare a legacy affiliation against a real one."""
    return " ".join(value.lower().split())


def _collect_real_institution_names(attrs: dict[str, Any]) -> set[str]:
    """Return loose-matched names that are known to be real institutions for
    this entity (sourced from the structured canonical layer)."""
    names: set[str] = set()

    canonical = attrs.get("canonical_affiliations")
    if isinstance(canonical, list):
        for item in canonical:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    names.add(_normalize_name(name))

    author_affs = attrs.get("author_affiliations")
    if isinstance(author_affs, list):
        for item in author_affs:
            if not isinstance(item, dict):
                continue
            institutions = item.get("institutions")
            if not isinstance(institutions, list):
                continue
            for inst in institutions:
                if isinstance(inst, dict):
                    name = inst.get("name")
                    if isinstance(name, str) and name.strip():
                        names.add(_normalize_name(name))
                elif isinstance(inst, str) and inst.strip():
                    names.add(_normalize_name(inst))

    return names


def _is_legacy_affiliation_value(value: Any, real_names: set[str]) -> bool:
    """Return True if ``value`` looks like a legacy journal/publisher leak
    rather than a real institutional affiliation.

    Rule: any string whose normalized form is NOT present in the entity's
    canonical/author-level institutions is considered legacy residue.
    Lists are normalized element-wise; a single matching element keeps the
    record (we err on the side of not deleting).
    """
    if value is None or value == "":
        return False
    if isinstance(value, str):
        return _normalize_name(value) not in real_names
    if isinstance(value, list):
        return all(
            isinstance(item, str)
            and _normalize_name(item) not in real_names
            for item in value
            if item
        )
    return False


def _fix_entity(entity: models.RawEntity, *, requeue_enrichment: bool) -> bool:
    """Apply the fix to one entity. Return True if anything changed."""
    raw = entity.attributes_json
    if not raw:
        return False
    try:
        attrs = json.loads(raw)
    except (ValueError, TypeError):
        return False
    if not isinstance(attrs, dict):
        return False

    if "affiliation" not in attrs and "affiliations" not in attrs:
        return False

    real_names = _collect_real_institution_names(attrs)
    legacy_aff = attrs.get("affiliation")
    legacy_affs = attrs.get("affiliations")

    aff_is_legacy = _is_legacy_affiliation_value(legacy_aff, real_names)
    affs_is_legacy = _is_legacy_affiliation_value(legacy_affs, real_names)

    if not (aff_is_legacy or affs_is_legacy):
        return False

    backup: dict[str, Any] = {}
    if aff_is_legacy and legacy_aff is not None:
        backup["affiliation"] = legacy_aff
        attrs.pop("affiliation", None)
    if affs_is_legacy and legacy_affs is not None:
        backup["affiliations"] = legacy_affs
        attrs.pop("affiliations", None)

    if backup:
        attrs["_legacy_affiliation_backup"] = backup

    entity.attributes_json = json.dumps(attrs, ensure_ascii=False)
    if requeue_enrichment:
        entity.enrichment_status = "pending"
    return True


def _candidate_query(db, *, org_id: int | None, limit: int | None) -> Iterable[models.RawEntity]:
    query = db.query(models.RawEntity).order_by(models.RawEntity.id)
    if org_id is not None:
        query = query.filter(models.RawEntity.org_id == org_id)
    if limit is not None:
        query = query.limit(limit)
    return query.yield_per(500)


def _source_is_affected(entity: models.RawEntity) -> bool:
    src = (entity.enrichment_source or "").strip().lower()
    return src in _AFFECTED_SOURCES


def run(
    *,
    dry_run: bool = False,
    requeue_enrichment: bool = False,
    org_id: int | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    """Scan and (optionally) repair entities. Returns counters."""
    db = SessionLocal()
    scanned = 0
    matched = 0
    fixed = 0
    try:
        for entity in _candidate_query(db, org_id=org_id, limit=limit):
            scanned += 1
            if not _source_is_affected(entity):
                continue
            matched += 1
            if _fix_entity(entity, requeue_enrichment=requeue_enrichment):
                fixed += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return {"scanned": scanned, "matched": matched, "fixed": fixed}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Remove legacy journal/publisher values that were mistakenly "
            "stored under attributes_json.affiliation by the cbe3255 → 19e97ff "
            "bug. Safe to re-run."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without committing changes.",
    )
    parser.add_argument(
        "--requeue-enrichment",
        action="store_true",
        help="Mark fixed entities with enrichment_status='pending' so the "
             "worker repopulates affiliation from canonical institutions.",
    )
    parser.add_argument("--org-id", type=int, default=None, help="Restrict to one org.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows scanned.")
    args = parser.parse_args()

    result = run(
        dry_run=args.dry_run,
        requeue_enrichment=args.requeue_enrichment,
        org_id=args.org_id,
        limit=args.limit,
    )
    mode = "dry run" if args.dry_run else "committed"
    msg = (
        f"{mode}: scanned={result['scanned']} matched={result['matched']} "
        f"fixed={result['fixed']}"
    )
    if args.requeue_enrichment and not args.dry_run:
        msg += " (re-enrichment requested)"
    print(msg)


if __name__ == "__main__":
    main()
