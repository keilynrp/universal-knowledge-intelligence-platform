"""Write a confirmed author identity back into publication attributes (Phase 3).

The OpenAlex/api_import path stores authors as structured entries inside each
publication's ``attributes_json`` (``author_affiliations[].author_name``), not
as RawEntity nodes — so :func:`entity_writeback.promote_confirmed_identity` has
no target there. This closes that loop at the data level: when an ``author``
AuthorityRecord is confirmed, the resolved identity (source / authority_id /
canonical label / uri) is stamped into ``attrs["canonical_authors"]`` (a dict
keyed by the original author name) on every publication that lists that author.

Non-destructive: merges one key per confirmed author, leaving other authors and
attributes untouched. Best-effort — never raises, so it cannot break confirm.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend import models
from backend.authority.batch_resolution import _PUB_SCAN_LIMIT
from backend.authority.entity_writeback import build_authority_canonical_id, writeback_enabled
from backend.tenant_access import scope_query_to_org

logger = logging.getLogger(__name__)


def _author_names(attrs: dict) -> set[str]:
    return {
        aa.get("author_name", "").strip()
        for aa in attrs.get("author_affiliations") or []
        if isinstance(aa, dict) and isinstance(aa.get("author_name"), str)
    }


def promote_confirmed_author_to_publications(
    db: Session,
    record: models.AuthorityRecord,
    *,
    org_id: int | None = None,
) -> int:
    """Stamp a confirmed author identity into matching publications' attributes.

    Returns the number of publications updated. The caller owns the transaction
    (changes are flushed via the ORM but not committed here). Never raises.
    """
    if not writeback_enabled():
        return 0
    try:
        if (record.field_name or "") != "author":
            return 0
        label = (record.original_value or "").strip()
        canonical_id = build_authority_canonical_id(record.authority_source, record.authority_id)
        if not label or canonical_id is None:
            return 0

        scope = record.org_id if org_id is None else org_id
        # Cheap LIKE pre-filter on the raw JSON, then verify in Python (portable
        # across SQLite/Postgres, avoids JSON-path dialect differences).
        rows = (
            scope_query_to_org(db.query(models.RawEntity), models.RawEntity, scope)
            .filter(
                models.RawEntity.entity_type == "publication",
                models.RawEntity.attributes_json.isnot(None),
                models.RawEntity.attributes_json.like(f"%{label}%"),
            )
            .limit(_PUB_SCAN_LIMIT)
            .all()
        )

        entry = {
            "canonical_id": canonical_id,
            "source": record.authority_source,
            "authority_id": record.authority_id,
            "canonical_label": record.canonical_label,
            "uri": record.uri,
            "confidence": record.confidence,
            "authority_record_id": record.id,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }

        updated = 0
        for ent in rows:
            try:
                attrs = json.loads(ent.attributes_json) if ent.attributes_json else {}
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(attrs, dict) or label not in _author_names(attrs):
                continue
            canonical_authors = attrs.get("canonical_authors")
            if not isinstance(canonical_authors, dict):
                canonical_authors = {}
            existing = canonical_authors.get(label)
            # Idempotent on identity (ignore the confirmed_at timestamp): if the
            # same author already carries this canonical_id, leave it untouched.
            if isinstance(existing, dict) and existing.get("canonical_id") == canonical_id:
                continue
            canonical_authors[label] = entry
            attrs["canonical_authors"] = canonical_authors
            ent.attributes_json = json.dumps(attrs, ensure_ascii=False, default=str)
            updated += 1

        if updated:
            logger.info(
                "publication write-back: stamped '%s' → %s on %d publication(s)",
                label, canonical_id, updated,
            )
        return updated
    except Exception as exc:  # defensive: must never break confirm
        logger.warning(
            "publication write-back failed for record %s: %s",
            getattr(record, "id", None), exc,
        )
        return 0
