"""Backfill: reconstruct ``canonical_id`` and ``entity_type`` on legacy
``RawEntity`` rows where these columns are NULL but the data is recoverable
from ``attributes_json``, ``normalized_json`` or ``enrichment_doi``.

Background
----------
Until the column-mapping expansion (2026-05-26), the auto-mapping table in
``backend/routers/column_maps.py`` only recognised a narrow set of English
header names for ``canonical_id`` (``ID``, ``DOI``, ``ORCID``, ...) and
``entity_type`` (``Type``, ``Category``, ``Kind``). Spanish or vendor-specific
headers (``Tipo``, ``Identificador``, ``PMID``, ``WoS ID``, ``Document Type``...)
fell through to ``normalized_json`` and the canonical columns stayed NULL.

Strategy
--------
For each entity with NULL ``canonical_id`` or NULL ``entity_type``:

1. Decode ``attributes_json`` and ``normalized_json``.
2. **canonical_id** — pick the first present, in priority order:
   ``enrichment_doi`` column → ``attrs.doi`` → ``attrs.orcid`` →
   ``attrs.ror`` → ``attrs.isbn`` → ``attrs.issn`` → ``attrs.pubmed_id`` →
   ``attrs.eid`` → ``attrs.scopus_id`` → ``attrs.openalex_id`` →
   any matching key inside ``normalized_json`` (case-insensitive match
   against the expanded ``COLUMN_MAPPING`` synonyms for ``canonical_id``).
3. **entity_type** — pick the first present, in priority order:
   ``attrs.document_type`` → ``attrs._entry_type`` → ``attrs._ris_type`` →
   ``attrs._plaintext_type`` → ``attrs.publication_type`` →
   any matching key inside ``normalized_json`` (case-insensitive match
   against the expanded ``COLUMN_MAPPING`` synonyms for ``entity_type``) →
   fallback ``"publication"`` **only** when the row came from a scientific
   import (``enrichment_source`` set or ``domain == "science"``).

Both writes are guarded: we never overwrite a non-NULL existing value, and
we record the source field for each fix in
``attrs["_canonical_backfill"] = {"canonical_id": "<source>",
"entity_type": "<source>"}`` so the change is auditable.

Usage
-----
    python -m backend.scripts.backfill_canonical_id_entity_type --dry-run
    python -m backend.scripts.backfill_canonical_id_entity_type
    python -m backend.scripts.backfill_canonical_id_entity_type --org-id 1 --limit 100
    python -m backend.scripts.backfill_canonical_id_entity_type --only canonical_id
    python -m backend.scripts.backfill_canonical_id_entity_type --only entity_type
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Iterable, Optional

from sqlalchemy import or_

from backend import models
from backend.database import SessionLocal
from backend.services.field_correspondence import resolve_field_mapping

logger = logging.getLogger(__name__)


# Ordered list of attribute keys to probe for canonical_id. The first match wins.
_CANONICAL_ID_ATTR_KEYS: tuple[str, ...] = (
    "doi",
    "orcid",
    "ror",
    "isbn",
    "issn",
    "eissn",
    "pubmed_id",
    "pmid",
    "eid",
    "scopus_id",
    "openalex_id",
    "wos_id",
    "ut",
    "local_id",
    "record_id",
    "accession_number",
)

# Ordered list of attribute keys to probe for entity_type. The first match wins.
_ENTITY_TYPE_ATTR_KEYS: tuple[str, ...] = (
    "document_type",
    "publication_type",
    "_entry_type",
    "_ris_type",
    "_plaintext_type",
    "raw_dt",
    "raw_pt",
)


def _synonym_set(target_field: str) -> set[str]:
    """Return the loose-matched header synonyms that map to ``target_field``."""
    candidates = {
        "ID", "UID", "DOI", "DOI Number", "Código", "Codigo", "Code",
        "Identifier", "Identificador", "Identificador único",
        "Identificador unico", "ID único", "ID unico", "ORCID", "ORCID ID",
        "ROR", "ROR ID", "ISBN", "ISSN", "PMID", "PubMed ID", "PubMed",
        "WOS ID", "WoS ID", "Scopus ID", "EID", "OpenAlex ID",
        "Accession Number", "Record ID", "Local ID", "canonical_id",
        "Type", "Tipo", "Tipo de entidad", "Tipo de Entidad", "Category",
        "Categoría", "Categoria", "Clase", "Class", "Kind", "Document Type",
        "Tipo de documento", "Tipo de Documento", "Publication Type",
        "Tipo de publicación", "Tipo de publicacion", "Subtype", "entity_type",
    }
    return {
        " ".join(header.lower().split())
        for header in candidates
        if resolve_field_mapping(header) == target_field
    }


_CANONICAL_ID_HEADER_SYNONYMS: set[str] = _synonym_set("canonical_id")
_ENTITY_TYPE_HEADER_SYNONYMS: set[str] = _synonym_set("entity_type")


def _decode_json(value: Optional[str]) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _pick_from_attrs(attrs: dict[str, Any], keys: Iterable[str]) -> tuple[Optional[str], Optional[str]]:
    """Return (value, source_key) — first non-empty attr value across ``keys``."""
    for key in keys:
        value = _clean(attrs.get(key))
        if value:
            return value, f"attributes_json.{key}"
    return None, None


def _pick_from_normalized(
    normalized: dict[str, Any], synonyms: set[str]
) -> tuple[Optional[str], Optional[str]]:
    """Return (value, source_key) — first cell in ``normalized_json`` whose
    header (loose-matched) is a known synonym for the target field."""
    for header, value in normalized.items():
        if not isinstance(header, str):
            continue
        key = " ".join(header.lower().split())
        if key in synonyms:
            cleaned = _clean(value)
            if cleaned:
                return cleaned, f"normalized_json.{header}"
    return None, None


def _resolve_canonical_id(entity: models.RawEntity, attrs: dict[str, Any], normalized: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    # 1) explicit enrichment_doi column
    direct = _clean(getattr(entity, "enrichment_doi", None))
    if direct:
        return direct, "enrichment_doi"
    # 2) known attribute keys
    value, source = _pick_from_attrs(attrs, _CANONICAL_ID_ATTR_KEYS)
    if value:
        return value, source
    # 3) raw_record nested under attributes_json (science imports)
    raw_record = attrs.get("raw_record")
    if isinstance(raw_record, dict):
        value, source = _pick_from_attrs(raw_record, _CANONICAL_ID_ATTR_KEYS)
        if value:
            return value, f"attributes_json.raw_record.{source.split('.')[-1]}"
    # 4) normalized_json with synonym-matched header
    return _pick_from_normalized(normalized, _CANONICAL_ID_HEADER_SYNONYMS)


def _resolve_entity_type(entity: models.RawEntity, attrs: dict[str, Any], normalized: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    # 1) known attribute keys
    value, source = _pick_from_attrs(attrs, _ENTITY_TYPE_ATTR_KEYS)
    if value:
        return value, source
    # 2) raw_record nested under attributes_json
    raw_record = attrs.get("raw_record")
    if isinstance(raw_record, dict):
        value, source = _pick_from_attrs(raw_record, _ENTITY_TYPE_ATTR_KEYS)
        if value:
            return value, f"attributes_json.raw_record.{source.split('.')[-1]}"
    # 3) normalized_json with synonym-matched header
    value, source = _pick_from_normalized(normalized, _ENTITY_TYPE_HEADER_SYNONYMS)
    if value:
        return value, source
    # 4) fallback "publication" for scientific imports only
    if _clean(getattr(entity, "enrichment_source", None)) or getattr(entity, "domain", None) == "science":
        return "publication", "fallback:science"
    return None, None


def _candidate_query(db, org_id: Optional[int], limit: Optional[int]):
    q = db.query(models.RawEntity).filter(
        or_(
            models.RawEntity.canonical_id.is_(None),
            models.RawEntity.entity_type.is_(None),
        )
    )
    if org_id is not None:
        q = q.filter(models.RawEntity.org_id == org_id)
    q = q.order_by(models.RawEntity.id.asc())
    if limit is not None:
        q = q.limit(limit)
    return q


def _fix_entity(
    entity: models.RawEntity,
    *,
    only: Optional[str],
) -> dict[str, Optional[str]]:
    """Mutate ``entity`` in place. Return a dict describing what was set."""
    attrs = _decode_json(getattr(entity, "attributes_json", None))
    normalized = _decode_json(getattr(entity, "normalized_json", None))
    result: dict[str, Optional[str]] = {"canonical_id": None, "entity_type": None}

    if only in (None, "canonical_id") and not _clean(entity.canonical_id):
        value, source = _resolve_canonical_id(entity, attrs, normalized)
        if value:
            entity.canonical_id = value
            result["canonical_id"] = source

    if only in (None, "entity_type") and not _clean(entity.entity_type):
        value, source = _resolve_entity_type(entity, attrs, normalized)
        if value:
            entity.entity_type = value
            result["entity_type"] = source

    if any(result.values()):
        backfill_meta = attrs.get("_canonical_backfill")
        if not isinstance(backfill_meta, dict):
            backfill_meta = {}
        for field_name, source in result.items():
            if source:
                backfill_meta[field_name] = source
        attrs["_canonical_backfill"] = backfill_meta
        entity.attributes_json = json.dumps(attrs, ensure_ascii=False)

    return result


def _would_violate_unique(
    db,
    entity: models.RawEntity,
    new_canonical_id: Optional[str],
    new_entity_type: Optional[str],
) -> bool:
    """Check whether applying the proposed values would violate the
    ``uq_raw_entities_canonical_global`` unique constraint on
    ``(domain, entity_type, canonical_id)``."""
    cid = new_canonical_id or entity.canonical_id
    etype = new_entity_type or entity.entity_type
    if not cid or not etype:
        return False
    existing = (
        db.query(models.RawEntity.id)
        .filter(
            models.RawEntity.domain == entity.domain,
            models.RawEntity.entity_type == etype,
            models.RawEntity.canonical_id == cid,
            models.RawEntity.id != entity.id,
        )
        .first()
    )
    return existing is not None


def run(
    *,
    dry_run: bool,
    only: Optional[str],
    org_id: Optional[int],
    limit: Optional[int],
) -> dict[str, int]:
    db = SessionLocal()
    scanned = 0
    fixed_canonical = 0
    fixed_entity_type = 0
    skipped_duplicates = 0
    # Track (domain, entity_type, canonical_id) tuples already claimed in this
    # run so we can detect in-batch collisions that the DB check would miss
    # (dirty reads inside the same transaction aren't visible to SQL queries).
    claimed: set[tuple[str, str, str]] = set()
    # Pre-populate with existing non-NULL rows so we also catch cross-batch dupes.
    for row in db.query(
        models.RawEntity.domain,
        models.RawEntity.entity_type,
        models.RawEntity.canonical_id,
    ).filter(
        models.RawEntity.canonical_id.isnot(None),
        models.RawEntity.entity_type.isnot(None),
    ):
        claimed.add((row[0] or "", row[1], row[2]))

    try:
        for entity in _candidate_query(db, org_id=org_id, limit=limit):
            scanned += 1
            result = _fix_entity(entity, only=only)
            if not any(result.values()):
                continue
            # Build the composite key that would result from this fix
            cid = entity.canonical_id
            etype = entity.entity_type
            if cid and etype:
                key = (entity.domain or "", etype, cid)
                if key in claimed:
                    db.expire(entity)
                    skipped_duplicates += 1
                    continue
                claimed.add(key)
            if result["canonical_id"]:
                fixed_canonical += 1
            if result["entity_type"]:
                fixed_entity_type += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return {
            "scanned": scanned,
            "fixed_canonical_id": fixed_canonical,
            "fixed_entity_type": fixed_entity_type,
            "skipped_duplicates": skipped_duplicates,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill canonical_id and entity_type on RawEntity rows where "
            "these columns are NULL but the data is recoverable from "
            "attributes_json / normalized_json / enrichment_doi. Safe to re-run."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without committing changes.",
    )
    parser.add_argument(
        "--only",
        choices=("canonical_id", "entity_type"),
        default=None,
        help="Limit the backfill to a single field.",
    )
    parser.add_argument("--org-id", type=int, default=None, help="Restrict to one org.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows scanned.")
    args = parser.parse_args()

    result = run(
        dry_run=args.dry_run,
        only=args.only,
        org_id=args.org_id,
        limit=args.limit,
    )
    mode = "dry run" if args.dry_run else "committed"
    print(
        f"{mode}: scanned={result['scanned']} "
        f"fixed_canonical_id={result['fixed_canonical_id']} "
        f"fixed_entity_type={result['fixed_entity_type']} "
        f"skipped_duplicates={result['skipped_duplicates']}"
    )


if __name__ == "__main__":
    main()
