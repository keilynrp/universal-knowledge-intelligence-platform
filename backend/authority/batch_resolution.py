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


def _distinct_values(
    db: Session, field: str, org_id, entity_type_filter: str | None = None
) -> list[str]:
    query_text = (
        f'SELECT DISTINCT "{field}" FROM raw_entities '
        f"WHERE \"{field}\" IS NOT NULL AND \"{field}\" != ''"
    )
    params: dict[str, object] = {}
    where_clauses: list[str] = []
    add_org_sql_filter(where_clauses, params, org_id)
    # Optionally restrict to rows of a given entity_type (e.g. resolve only
    # 'author' labels as persons, 'affiliation' labels as institutions).
    if entity_type_filter:
        where_clauses.append('"entity_type" = :entity_type_filter')
        params["entity_type_filter"] = entity_type_filter
    if where_clauses:
        query_text += " AND " + " AND ".join(where_clauses)
    rows = db.execute(text(query_text), params).fetchall()
    return [row[0] for row in rows if row[0]]


# Value sources that read author/affiliation names out of publication
# ``attributes_json`` instead of a raw_entities column. This is how the OpenAlex
# / api_import path exposes authors (as structured attributes on the publication
# row) — there are no derived author/affiliation node rows for that path.
VALUE_SOURCE_PUB_AUTHORS = "publication_authors"
VALUE_SOURCE_PUB_AFFILIATIONS = "publication_affiliations"
_PUB_SCAN_LIMIT = 2000


def _names_from_attrs(attrs: dict, value_source: str) -> list[str]:
    """Extract author or affiliation display names from one publication's attrs."""
    names: list[str] = []
    if value_source == VALUE_SOURCE_PUB_AUTHORS:
        for aa in attrs.get("author_affiliations") or []:
            if isinstance(aa, dict):
                n = aa.get("author_name")
                if isinstance(n, str) and n.strip():
                    names.append(n.strip())
    elif value_source == VALUE_SOURCE_PUB_AFFILIATIONS:
        for ca in attrs.get("canonical_affiliations") or []:
            if isinstance(ca, dict):
                n = ca.get("name")
                if isinstance(n, str) and n.strip():
                    names.append(n.strip())
    return names


def _distinct_values_from_publication_attrs(
    db: Session, org_id, value_source: str, scan_limit: int = _PUB_SCAN_LIMIT
) -> list[str]:
    """Distinct author/affiliation names across publication ``attributes_json``.

    Python-side JSON parsing keeps this portable across SQLite/Postgres. The
    scan is bounded by ``scan_limit`` publications; combined with the worker's
    ``skip_existing`` this drains large corpora progressively.
    """
    q = (
        scope_query_to_org(
            db.query(models.RawEntity.attributes_json), models.RawEntity, org_id
        )
        .filter(
            models.RawEntity.entity_type == "publication",
            models.RawEntity.attributes_json.isnot(None),
        )
        .limit(scan_limit)
    )
    seen: set[str] = set()
    out: list[str] = []
    for (raw,) in q:
        try:
            attrs = json.loads(raw) if raw else {}
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(attrs, dict):
            continue
        for name in _names_from_attrs(attrs, value_source):
            if name not in seen:
                seen.add(name)
                out.append(name)
    return out


def _publication_author_hints(
    db: Session, org_id, scan_limit: int = _PUB_SCAN_LIMIT
) -> dict[str, dict]:
    """Map author display name → resolution hints from publication attributes.

    Pulls the per-author ``author_orcid`` and first institution name out of
    ``author_affiliations`` so resolution can pass them as ``ResolveContext``
    (orcid_hint → exact-match score 1.0; affiliation → boosts the affil signal).
    First non-empty value wins per name. Only used for the authors value source.
    """
    q = (
        scope_query_to_org(
            db.query(models.RawEntity.attributes_json), models.RawEntity, org_id
        )
        .filter(
            models.RawEntity.entity_type == "publication",
            models.RawEntity.attributes_json.isnot(None),
        )
        .limit(scan_limit)
    )
    hints: dict[str, dict] = {}
    for (raw,) in q:
        try:
            attrs = json.loads(raw) if raw else {}
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(attrs, dict):
            continue
        for aa in attrs.get("author_affiliations") or []:
            if not isinstance(aa, dict):
                continue
            name = aa.get("author_name")
            if not (isinstance(name, str) and name.strip()):
                continue
            name = name.strip()
            entry = hints.setdefault(name, {"orcid_hint": None, "affiliation": None})
            if not entry["orcid_hint"]:
                orcid = aa.get("author_orcid")
                if isinstance(orcid, str) and orcid.strip():
                    entry["orcid_hint"] = orcid.strip()
            if not entry["affiliation"]:
                insts = aa.get("institutions") or []
                if insts and isinstance(insts[0], dict):
                    inst = insts[0].get("name")
                    if isinstance(inst, str) and inst.strip():
                        entry["affiliation"] = inst.strip()
    return hints


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
    entity_type_filter: str | None = None,
    value_source: str | None = None,
) -> tuple[dict, list[models.AuthorityRecord]]:
    """Resolve distinct values of ``field`` and persist AuthorityRecords.

    Returns ``(summary_dict, new_records)``. ``progress_cb(processed, total,
    records_created)`` is invoked after each value when provided (used by the
    async worker to update job counters). ``entity_type_filter`` optionally
    restricts the value pool to raw_entities rows of that entity_type.

    ``value_source`` selects where values come from: ``None`` (default) reads
    the raw_entities column ``field``; ``publication_authors`` /
    ``publication_affiliations`` extract names from publication attributes_json
    (the OpenAlex/api_import path). Persisted records are always tagged with
    ``field_name=field`` so they group cleanly in the review queue.
    """
    value_hints: dict[str, dict] = {}
    if value_source in (VALUE_SOURCE_PUB_AUTHORS, VALUE_SOURCE_PUB_AFFILIATIONS):
        all_values = _distinct_values_from_publication_attrs(db, org_id, value_source)
        # ORCID / affiliation hints only make sense for person resolution.
        if value_source == VALUE_SOURCE_PUB_AUTHORS:
            value_hints = _publication_author_hints(db, org_id)
    else:
        all_values = _distinct_values(db, field, org_id, entity_type_filter)

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
        # Only feed orcid_hint: an exact ORCID match scores the identifier
        # signal 1.0. We deliberately do NOT pass the affiliation here — the
        # scorer counts the affiliation weight (0.20) whenever a context
        # affiliation is present, even when it fuzzy-scores ~0 against the
        # candidate description, which would dilute an otherwise-perfect ORCID
        # match from 1.0 down to ~0.75.
        hint = value_hints.get(value)
        vctx = (
            ResolveContext(orcid_hint=hint.get("orcid_hint"))
            if hint and hint.get("orcid_hint")
            else ctx
        )
        candidates = resolve_fn(value, entity_type, vctx)
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
