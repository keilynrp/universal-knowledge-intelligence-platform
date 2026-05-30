"""Shared batch authority-resolution core (Phase 1, Task 3).

Used by both the synchronous endpoint path and the async batch worker so the
value-fetch / resolve / persist logic lives in one place. The resolver function
is injected so the sync endpoint can keep its patchable module-level reference
while the worker supplies its own.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend import models
from backend.authority.base import ResolveContext
from backend.authority.hierarchical_fallback import apply_hierarchical_fallback
from backend.tenant_access import add_org_sql_filter, scope_query_to_org

_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class InvalidFieldError(ValueError):
    """Raised when the requested field is not a safe / existing entity column."""


def validate_field(db: Session, field: str) -> None:
    """Reject field names that are unsafe or absent from raw_entities."""
    if not _FIELD_RE.match(field):
        raise InvalidFieldError(f"Invalid field name: {field!r}")
    from sqlalchemy import inspect as _inspect

    cols = {c["name"] for c in _inspect(db.get_bind()).get_columns("raw_entities")}
    if field not in cols:
        raise InvalidFieldError(f"Field '{field}' not found in entity table")


def _distinct_values(db: Session, field: str, org_id) -> list[str]:
    query_text = (
        f'SELECT DISTINCT "{field}" FROM raw_entities '
        f"WHERE \"{field}\" IS NOT NULL AND \"{field}\" != ''"
    )
    params: dict[str, object] = {}
    where_clauses: list[str] = []
    add_org_sql_filter(where_clauses, params, org_id)
    if where_clauses:
        query_text += " AND " + " AND ".join(where_clauses)
    rows = db.execute(text(query_text), params).fetchall()
    return [row[0] for row in rows if row[0]]


def execute_batch_resolution(
    db: Session,
    *,
    org_id,
    record_org_id,
    field: str,
    entity_type: str,
    limit: int,
    skip_existing: bool,
    resolve_fn: Callable,
    progress_cb: Optional[Callable[[int, int, int], None]] = None,
) -> tuple[dict, list[models.AuthorityRecord]]:
    """Resolve distinct values of ``field`` and persist AuthorityRecords.

    Returns ``(summary_dict, new_records)``. ``progress_cb(processed, total,
    records_created)`` is invoked after each value when provided (used by the
    async worker to update job counters).
    """
    all_values = _distinct_values(db, field, org_id)

    already_existed = 0
    if skip_existing and all_values:
        existing_values = {
            r.original_value
            for r in scope_query_to_org(
                db.query(models.AuthorityRecord.original_value),
                models.AuthorityRecord,
                org_id,
            )
            .filter(
                models.AuthorityRecord.field_name == field,
                models.AuthorityRecord.status.in_(["pending", "confirmed"]),
            )
            .all()
        }
        filtered = [v for v in all_values if v not in existing_values]
        already_existed = len(all_values) - len(filtered)
        all_values = filtered

    to_resolve = all_values[:limit]
    skipped = len(all_values) - len(to_resolve)

    ctx = ResolveContext()
    new_records: list[models.AuthorityRecord] = []
    total = len(to_resolve)

    for idx, value in enumerate(to_resolve, start=1):
        candidates = resolve_fn(value, entity_type, ctx)
        candidates = apply_hierarchical_fallback(value, entity_type, candidates)
        for c in candidates:
            rec = models.AuthorityRecord(
                org_id=record_org_id,
                field_name=field,
                original_value=value,
                authority_source=c.authority_source,
                authority_id=c.authority_id,
                canonical_label=c.canonical_label,
                aliases=json.dumps(c.aliases),
                description=c.description,
                confidence=c.confidence,
                uri=c.uri,
                status="pending",
                resolution_status=c.resolution_status,
                score_breakdown=json.dumps(c.score_breakdown),
                evidence=json.dumps(c.evidence),
                merged_sources=json.dumps(c.merged_sources),
                hierarchy_distance=c.hierarchy_distance,
            )
            db.add(rec)
            new_records.append(rec)
        if progress_cb is not None:
            progress_cb(idx, total, len(new_records))

    summary = {
        "field_name": field,
        "entity_type": entity_type,
        "resolved_count": len(to_resolve),
        "skipped_count": skipped,
        "already_existed_count": already_existed,
        "records_created": len(new_records),
    }
    return summary, new_records
