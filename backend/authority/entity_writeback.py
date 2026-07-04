"""Write-back of confirmed authority identities onto derived graph entities.

When a reviewer confirms an :class:`~backend.models.AuthorityRecord`, the
resolved external identity (``authority_source`` + ``authority_id`` + ``uri``)
is promoted onto matching derived ``author`` / ``affiliation`` graph entities
whose ``canonical_id`` is still a *weak* internal, name-derived identifier.

Design guarantees (non-destructive by construction):
  * Only entities whose ``canonical_id`` is weak (``author:`` / ``affiliation:``
    prefixes produced by the graph materializer) are ever touched.
  * Strong external identifiers (``orcid:``, ``wikidata:``, ``viaf:``,
    ``openalex:``, ``dbpedia:``, ``ror:``, ``doi:``) are never overwritten.
  * Matching is exact on ``primary_label == original_value`` within the record's
    org scope, so an author string never collides with an institution row.
  * The function never raises — write-back is best-effort enrichment layered on
    top of the confirm flow and must not break it.

Human confirmation *is* the trust gate: by confirming, a reviewer has asserted
the candidate is the correct identity, so no additional score threshold is
required here. ``internal_nil`` (NIL) records are skipped.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend import models
from backend.tenant_access import scope_query_to_org

logger = logging.getLogger(__name__)

# canonical_id prefixes considered "weak" (internal, name/label-derived) and
# therefore safe to upgrade to an external authority identity.
_WEAK_PREFIXES = ("author:", "affiliation:")

# prefixes already representing a strong external identity — never overwritten.
_STRONG_PREFIXES = (
    "orcid:", "wikidata:", "viaf:", "openalex:", "dbpedia:", "ror:", "doi:",
)

# entity_types eligible for identity promotion (the derived graph nodes).
_ELIGIBLE_ENTITY_TYPES = ("author", "affiliation")

_NIL_SOURCE = "internal_nil"


def writeback_enabled() -> bool:
    """Feature flag — defaults ON. Set ``UKIP_AUTHORITY_WRITEBACK=0`` to disable."""
    return os.environ.get("UKIP_AUTHORITY_WRITEBACK", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _is_weak(canonical_id: str | None) -> bool:
    """A canonical_id is weak when it is empty or a name-derived internal id."""
    if not canonical_id:
        return True
    cid = canonical_id.strip().lower()
    if cid.startswith(_STRONG_PREFIXES):
        return False
    return cid.startswith(_WEAK_PREFIXES)


def build_authority_canonical_id(source: str | None, authority_id: str | None) -> str | None:
    """Compose the strong canonical id ``<source>:<authority_id>`` or None.

    Returns None for NIL / empty records so callers can no-op cleanly.
    """
    src = (source or "").strip().lower()
    aid = (authority_id or "").strip()
    if not src or not aid or src == _NIL_SOURCE or aid.upper() == "NIL":
        return None
    return f"{src}:{aid}"


def _merge_authority_provenance(entity: models.RawEntity, record: models.AuthorityRecord, new_cid: str) -> None:
    """Record the promotion in ``attributes_json`` for auditability (non-destructive)."""
    try:
        attrs = json.loads(entity.attributes_json) if entity.attributes_json else {}
        if not isinstance(attrs, dict):
            attrs = {}
    except (TypeError, json.JSONDecodeError):
        attrs = {}

    attrs["authority"] = {
        "canonical_id": new_cid,
        "source": record.authority_source,
        "authority_id": record.authority_id,
        "canonical_label": record.canonical_label,
        "uri": record.uri,
        "confidence": record.confidence,
        "authority_record_id": record.id,
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    }
    entity.attributes_json = json.dumps(attrs, ensure_ascii=False, default=str)


def promote_confirmed_identity(
    db: Session,
    record: models.AuthorityRecord,
    *,
    org_id: int | None = None,
) -> int:
    """Promote weak-id derived entities matching a confirmed authority record.

    Returns the number of entities whose ``canonical_id`` was upgraded. The
    caller is responsible for committing the surrounding transaction. Never
    raises: any failure is logged and reported as ``0`` updates so the confirm
    flow stays intact.
    """
    if not writeback_enabled():
        return 0
    try:
        new_cid = build_authority_canonical_id(record.authority_source, record.authority_id)
        if new_cid is None:
            return 0
        label = (record.original_value or "").strip()
        if not label:
            return 0

        scope = record.org_id if org_id is None else org_id
        rows = (
            scope_query_to_org(db.query(models.RawEntity), models.RawEntity, scope)
            .filter(
                models.RawEntity.entity_type.in_(_ELIGIBLE_ENTITY_TYPES),
                models.RawEntity.primary_label == label,
            )
            .all()
        )

        updated = 0
        for ent in rows:
            if ent.canonical_id == new_cid:
                continue
            if not _is_weak(ent.canonical_id):
                continue
            ent.canonical_id = new_cid
            _merge_authority_provenance(ent, record, new_cid)
            updated += 1

        if updated:
            logger.info(
                "authority write-back: promoted %d entit%s to %s (record=%s)",
                updated, "y" if updated == 1 else "ies", new_cid, record.id,
            )
        return updated
    except Exception as exc:  # defensive: write-back must never break confirm
        logger.warning(
            "authority write-back failed for record %s: %s",
            getattr(record, "id", None), exc,
        )
        return 0
