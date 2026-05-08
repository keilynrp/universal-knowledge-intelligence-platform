"""
Authority resolution layer endpoints.
  POST /authority/resolve
  POST /authority/resolve/batch
  GET  /authority/queue/summary
  POST /authority/records/bulk-confirm
  POST /authority/records/bulk-reject
  GET  /authority/records
  POST /authority/records/{record_id}/confirm
  POST /authority/records/{record_id}/reject
  DELETE /authority/records/{record_id}
  GET  /authority/metrics
  GET  /authority/{field}
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from backend import database, models, schemas
from backend.auth import get_current_user, require_role
from backend.authority.author_resolution import summarize_author_resolution
from backend.authority.base import ResolveContext as _AuthorityContext
from backend.authority.hierarchical_fallback import apply_hierarchical_fallback
from backend.authority.query_reformulation import run_author_query_reformulation
from backend.authority.resolver import resolve_all as _authority_resolve_all
from backend.database import get_db
from backend.routers.deps import (
    _audit,
    _build_disambig_groups,
    _serialize_authority_record,
    _serialize_authority_record_link,
)
from backend.routers.limiter import limiter
from backend.tenant_access import (
    add_org_sql_filter,
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["authority"])

_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_AFFILIATION_LINK_TYPE = "affiliated-with"


# ── Authority resolution ──────────────────────────────────────────────────────

def _persist_authority_candidates(
    *,
    db: Session,
    org_id: int | None,
    field_name: str,
    original_value: str,
    candidates: list,
    status: str = "pending",
    resolution_route: str | None = None,
    complexity_score: float | None = None,
    review_required: bool = False,
    nil_reason: str | None = None,
    nil_score: float | None = None,
    reformulation_trace=None,
) -> list[models.AuthorityRecord]:
    records: list[models.AuthorityRecord] = []
    for idx, c in enumerate(candidates):
        rec = models.AuthorityRecord(
            org_id=org_id,
            field_name=field_name,
            original_value=original_value,
            authority_source=c.authority_source,
            authority_id=c.authority_id,
            canonical_label=c.canonical_label,
            aliases=json.dumps(c.aliases),
            description=c.description,
            confidence=c.confidence,
            uri=c.uri,
            status=status,
            resolution_status=c.resolution_status,
            score_breakdown=json.dumps(c.score_breakdown),
            evidence=json.dumps(c.evidence),
            merged_sources=json.dumps(c.merged_sources),
            hierarchy_distance=c.hierarchy_distance,
            resolution_route=resolution_route,
            complexity_score=complexity_score,
            review_required=review_required,
            nil_reason=nil_reason,
            nil_score=nil_score,
            reformulation_applied=(
                bool(reformulation_trace.applied) if reformulation_trace is not None and idx == 0 else False
            ),
            reformulation_gain=(
                reformulation_trace.retrieval_gain if reformulation_trace is not None and idx == 0 else None
            ),
            reformulation_cost_estimate=(
                reformulation_trace.estimated_cost_usd if reformulation_trace is not None and idx == 0 else None
            ),
            reformulation_trace=(
                reformulation_trace.to_json()
                if reformulation_trace is not None and reformulation_trace.attempted and idx == 0
                else None
            ),
        )
        db.add(rec)
        records.append(rec)
    return records


def _make_nil_authority_record(
    *,
    org_id: int | None,
    field_name: str,
    original_value: str,
    description: str,
    evidence: list[str],
    resolution_route: str | None,
    complexity_score: float | None,
    review_required: bool,
    nil_reason: str,
    nil_score: float,
    reformulation_trace=None,
) -> models.AuthorityRecord:
    return models.AuthorityRecord(
        org_id=org_id,
        field_name=field_name,
        original_value=original_value,
        authority_source="internal_nil",
        authority_id="NIL",
        canonical_label=original_value,
        aliases="[]",
        description=description,
        confidence=0.0,
        uri=None,
        status="pending",
        resolution_status="unresolved",
        score_breakdown="{}",
        evidence=json.dumps(evidence),
        merged_sources="[]",
        resolution_route=resolution_route,
        complexity_score=complexity_score,
        review_required=review_required,
        nil_reason=nil_reason,
        nil_score=nil_score,
        reformulation_applied=bool(reformulation_trace.applied) if reformulation_trace is not None else False,
        reformulation_gain=reformulation_trace.retrieval_gain if reformulation_trace is not None else None,
        reformulation_cost_estimate=reformulation_trace.estimated_cost_usd if reformulation_trace is not None else None,
        reformulation_trace=reformulation_trace.to_json()
        if reformulation_trace is not None and reformulation_trace.attempted
        else None,
    )


def _link_confidence(author_record: models.AuthorityRecord, institution_record: models.AuthorityRecord) -> float:
    try:
        author_breakdown = json.loads(author_record.score_breakdown or "{}")
    except Exception:
        author_breakdown = {}
    affiliation_score = float(author_breakdown.get("affiliation") or 0.0)
    return round(
        0.50 * float(author_record.confidence or 0.0)
        + 0.40 * float(institution_record.confidence or 0.0)
        + 0.10 * affiliation_score,
        3,
    )


def _resolve_author_affiliation(
    *,
    db: Session,
    org_id: int | None,
    author_record: models.AuthorityRecord | None,
    affiliation_value: str | None,
    affiliation_field_name: str,
) -> dict:
    if not affiliation_value or not affiliation_value.strip():
        return {"attempted": False, "reason": "missing_context_affiliation"}
    if author_record is None or author_record.authority_source == "internal_nil":
        return {"attempted": False, "reason": "missing_author_record"}
    if not _FIELD_RE.match(affiliation_field_name):
        raise HTTPException(status_code=422, detail=f"Invalid affiliation field name: {affiliation_field_name!r}")

    candidates = _authority_resolve_all(affiliation_value, "institution", _AuthorityContext())
    candidates = apply_hierarchical_fallback(affiliation_value, "institution", candidates)
    records = _persist_authority_candidates(
        db=db,
        org_id=org_id,
        field_name=affiliation_field_name,
        original_value=affiliation_value,
        candidates=candidates,
    )
    if not records:
        nil_record = _make_nil_authority_record(
            org_id=org_id,
            field_name=affiliation_field_name,
            original_value=affiliation_value,
            description="No external authority candidates were returned for this institution affiliation query.",
            evidence=["nil_reason:no_candidates", f"context_affiliation:{affiliation_value}"],
            resolution_route=None,
            complexity_score=None,
            review_required=True,
            nil_reason="no_candidates",
            nil_score=1.0,
        )
        db.add(nil_record)
        records = [nil_record]

    db.flush()
    institution_record = records[0]
    link = None
    if institution_record.authority_source != "internal_nil":
        confidence = _link_confidence(author_record, institution_record)
        evidence = [
            f"context_affiliation:{affiliation_value}",
            f"author_record:{author_record.authority_source}:{author_record.authority_id}",
            f"institution_record:{institution_record.authority_source}:{institution_record.authority_id}",
            f"author_confidence:{float(author_record.confidence or 0.0):.3f}",
            f"institution_confidence:{float(institution_record.confidence or 0.0):.3f}",
            f"author_affiliation_score:{json.loads(author_record.score_breakdown or '{}').get('affiliation', 0.0)}",
            f"institution_resolution_status:{institution_record.resolution_status or 'unresolved'}",
        ]
        link = models.AuthorityRecordLink(
            org_id=org_id,
            source_authority_record_id=author_record.id,
            target_authority_record_id=institution_record.id,
            link_type=_AFFILIATION_LINK_TYPE,
            confidence=confidence,
            status="pending",
            evidence=json.dumps(evidence),
        )
        db.add(link)

    return {
        "attempted": True,
        "records": records,
        "link": link,
    }

@router.post("/authority/resolve", status_code=201, tags=["authority"])
@limiter.limit("60/minute")
def resolve_authority(
    request: Request,
    payload: schemas.AuthorityResolveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Query all authority sources in parallel for a given value and persist
    the candidates with status='pending'. Returns the persisted records.
    """
    org_id = resolve_request_org_id(db, current_user)
    record_org_id = persisted_org_id(org_id)
    ctx = _AuthorityContext(
        affiliation=payload.context_affiliation,
        orcid_hint=payload.context_orcid_hint,
        doi=payload.context_doi,
        year=payload.context_year,
    )
    candidates = _authority_resolve_all(payload.value, payload.entity_type.value, ctx)
    candidates = apply_hierarchical_fallback(payload.value, payload.entity_type.value, candidates)

    records = []
    for c in candidates:
        rec = models.AuthorityRecord(
            org_id=record_org_id,
            field_name=payload.field_name,
            original_value=payload.value,
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
        records.append(rec)

    db.commit()
    for rec in records:
        db.refresh(rec)

    return [_serialize_authority_record(r) for r in records]


@router.post("/authority/authors/resolve", status_code=201, tags=["authority"])
@limiter.limit("60/minute")
def resolve_author_profile(
    request: Request,
    payload: schemas.AuthorResolveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Author-only adaptive resolution baseline.

    Reuses the existing authority resolver/scoring pipeline, then adds a
    deterministic routing heuristic that classifies the case as fast/hybrid/LLM
    or manual review. The response keeps all persisted records for auditability.
    """
    org_id = resolve_request_org_id(db, current_user)
    record_org_id = persisted_org_id(org_id)
    ctx = _AuthorityContext(
        affiliation=payload.context_affiliation,
        orcid_hint=payload.context_orcid_hint,
        doi=payload.context_doi,
        year=payload.context_year,
    )
    candidates = _authority_resolve_all(payload.value, "person", ctx)
    summary = summarize_author_resolution(candidates, ctx)
    candidates, summary, reformulation_trace = run_author_query_reformulation(
        value=payload.value,
        context=ctx,
        base_candidates=candidates,
        base_summary=summary,
        resolver_fn=_authority_resolve_all,
    )

    records: list[models.AuthorityRecord] = []
    if candidates:
        for idx, c in enumerate(candidates):
            rec = models.AuthorityRecord(
                org_id=record_org_id,
                field_name=payload.field_name,
                original_value=payload.value,
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
                resolution_route=summary.resolution_route,
                complexity_score=summary.complexity_score,
                review_required=summary.review_required,
                nil_reason=summary.nil_reason,
                nil_score=summary.nil_score,
                reformulation_applied=reformulation_trace.applied if idx == 0 else False,
                reformulation_gain=reformulation_trace.retrieval_gain if idx == 0 else None,
                reformulation_cost_estimate=reformulation_trace.estimated_cost_usd if idx == 0 else None,
                reformulation_trace=reformulation_trace.to_json() if reformulation_trace.attempted and idx == 0 else None,
            )
            db.add(rec)
            records.append(rec)
    else:
        nil_record = models.AuthorityRecord(
            org_id=record_org_id,
            field_name=payload.field_name,
            original_value=payload.value,
            authority_source="internal_nil",
            authority_id="NIL",
            canonical_label=payload.value,
            aliases="[]",
            description="No external authority candidates were returned for this author query.",
            confidence=0.0,
            uri=None,
            status="pending",
            resolution_status="unresolved",
            score_breakdown="{}",
            evidence=json.dumps([f"nil_reason:{summary.nil_reason or 'no_candidates'}"]),
            merged_sources="[]",
            resolution_route=summary.resolution_route,
            complexity_score=summary.complexity_score,
            review_required=summary.review_required,
            nil_reason=summary.nil_reason or "no_candidates",
            nil_score=summary.nil_score,
            reformulation_applied=reformulation_trace.applied,
            reformulation_gain=reformulation_trace.retrieval_gain,
            reformulation_cost_estimate=reformulation_trace.estimated_cost_usd,
            reformulation_trace=reformulation_trace.to_json() if reformulation_trace.attempted else None,
        )
        db.add(nil_record)
        records.append(nil_record)

    db.flush()
    affiliation_resolution = (
        _resolve_author_affiliation(
            db=db,
            org_id=record_org_id,
            author_record=records[0] if records else None,
            affiliation_value=payload.context_affiliation,
            affiliation_field_name=payload.affiliation_field_name,
        )
        if payload.resolve_affiliation
        else {"attempted": False, "reason": "disabled"}
    )

    db.commit()
    for rec in records:
        db.refresh(rec)
    for rec in affiliation_resolution.get("records", []):
        db.refresh(rec)
    if affiliation_resolution.get("link") is not None:
        db.refresh(affiliation_resolution["link"])

    serialized = [_serialize_authority_record(r) for r in records]
    winning = serialized[0] if serialized else None
    runner_up = serialized[1] if len(serialized) > 1 else None

    if affiliation_resolution.get("attempted"):
        affiliation_payload = {
            "attempted": True,
            "records_created": len(affiliation_resolution.get("records", [])),
            "winning_record": _serialize_authority_record(affiliation_resolution["records"][0])
            if affiliation_resolution.get("records")
            else None,
            "records": [
                _serialize_authority_record(r)
                for r in affiliation_resolution.get("records", [])
            ],
            "link": _serialize_authority_record_link(affiliation_resolution["link"])
            if affiliation_resolution.get("link") is not None
            else None,
        }
    else:
        affiliation_payload = {
            "attempted": False,
            "reason": affiliation_resolution.get("reason", "not_attempted"),
        }

    return {
        "query": {
            "field_name": payload.field_name,
            "value": payload.value,
            "entity_type": "person",
        },
        "resolution_route": summary.resolution_route,
        "complexity_score": summary.complexity_score,
        "review_required": summary.review_required,
        "nil_reason": summary.nil_reason,
        "nil_score": summary.nil_score,
        "reformulation": json.loads(reformulation_trace.to_json()) if reformulation_trace.attempted else None,
        "records_created": len(serialized),
        "winning_record": winning,
        "runner_up_record": runner_up,
        "records": serialized,
        "affiliation_resolution": affiliation_payload,
    }


@router.post("/authority/resolve/batch", status_code=201, tags=["authority"])
def resolve_authority_batch(
    payload: schemas.BatchResolveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Resolve all distinct values of a field against external authority sources.
    """
    org_id = resolve_request_org_id(db, current_user)
    record_org_id = persisted_org_id(org_id)
    field = payload.field_name
    entity_type = payload.entity_type.value

    if not _FIELD_RE.match(field):
        raise HTTPException(status_code=422, detail=f"Invalid field name: {field!r}")

    _entity_cols = {col["name"] for col in inspect(db.get_bind()).get_columns("raw_entities")}
    if field not in _entity_cols:
        raise HTTPException(status_code=422, detail=f"Field '{field}' not found in entity table")

    query_text = (
        f'SELECT DISTINCT "{field}" FROM raw_entities '
        f'WHERE "{field}" IS NOT NULL AND "{field}" != \'\''
    )
    params: dict[str, object] = {}
    where_clauses: list[str] = []
    add_org_sql_filter(where_clauses, params, org_id)
    if where_clauses:
        query_text += " AND " + " AND ".join(where_clauses)
    rows = db.execute(text(query_text), params).fetchall()
    all_values = [row[0] for row in rows if row[0]]

    already_existed = 0
    if payload.skip_existing and all_values:
        existing_values = {
            r.original_value
            for r in scope_query_to_org(
                db.query(models.AuthorityRecord.original_value), models.AuthorityRecord, org_id
            ).filter(
                models.AuthorityRecord.field_name == field,
                models.AuthorityRecord.status.in_(["pending", "confirmed"]),
            ).all()
        }
        filtered = [v for v in all_values if v not in existing_values]
        already_existed = len(all_values) - len(filtered)
        all_values = filtered

    to_resolve = all_values[: payload.limit]
    skipped = len(all_values) - len(to_resolve)

    ctx = _AuthorityContext()
    new_records: list[models.AuthorityRecord] = []

    for value in to_resolve:
        candidates = _authority_resolve_all(value, entity_type, ctx)
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

    db.commit()
    for rec in new_records:
        db.refresh(rec)

    return {
        "field_name":          field,
        "entity_type":         entity_type,
        "resolved_count":      len(to_resolve),
        "skipped_count":       skipped,
        "already_existed_count": already_existed,
        "records_created":     len(new_records),
        "records":             [_serialize_authority_record(r) for r in new_records],
    }


@router.get("/authority/queue/summary", tags=["authority"])
def authority_queue_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Aggregated queue stats by field."""
    org_id = resolve_request_org_id(db, current_user)
    rows = scope_query_to_org(
        db.query(
            models.AuthorityRecord.field_name,
            models.AuthorityRecord.status,
            func.count(models.AuthorityRecord.id),
            func.avg(models.AuthorityRecord.confidence),
        ),
        models.AuthorityRecord,
        org_id,
    ).group_by(
        models.AuthorityRecord.field_name,
        models.AuthorityRecord.status,
    ).all()

    field_map: dict[str, dict] = {}
    totals = {"pending": 0, "confirmed": 0, "rejected": 0}

    for field_name, status, count, avg_conf in rows:
        if field_name not in field_map:
            field_map[field_name] = {
                "field_name": field_name,
                "pending": 0, "confirmed": 0, "rejected": 0,
                "avg_confidence": 0.0,
            }
        if status in field_map[field_name]:
            field_map[field_name][status] = count
        if status in totals:
            totals[status] += count

    avg_rows = scope_query_to_org(
        db.query(
            models.AuthorityRecord.field_name,
            func.avg(models.AuthorityRecord.confidence),
        ),
        models.AuthorityRecord,
        org_id,
    ).group_by(models.AuthorityRecord.field_name).all()
    for field_name, avg_conf in avg_rows:
        if field_name in field_map:
            field_map[field_name]["avg_confidence"] = round(float(avg_conf or 0.0), 3)

    by_field = sorted(field_map.values(), key=lambda x: x["pending"], reverse=True)

    return {
        "total_pending":   totals["pending"],
        "total_confirmed": totals["confirmed"],
        "total_rejected":  totals["rejected"],
        "by_field":        by_field,
    }


@router.get("/authority/authors/review-queue", tags=["authority"])
def author_review_queue(
    status: Optional[str] = Query("pending", pattern="^(pending|confirmed|rejected)$"),
    review_required: Optional[bool] = Query(True),
    route: Optional[str] = Query(None, pattern="^(fast_path|hybrid_path|llm_path|manual_review)$"),
    nil_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Author-only operational queue.

    This is intentionally scoped to records created by the adaptive author
    pipeline (identified by a non-null `resolution_route`). It gives the
    frontend a stable review surface without disturbing the legacy authority
    endpoints used for generic entity reconciliation.
    """
    org_id = resolve_request_org_id(db, current_user)
    base_q = scope_query_to_org(db.query(models.AuthorityRecord), models.AuthorityRecord, org_id).filter(
        models.AuthorityRecord.resolution_route.is_not(None)
    )

    summary_by_route = {
        row[0]: row[1]
        for row in base_q.with_entities(
            models.AuthorityRecord.resolution_route,
            func.count(models.AuthorityRecord.id),
        ).group_by(
            models.AuthorityRecord.resolution_route
        ).all()
        if row[0]
    }
    summary_by_status = {
        row[0]: row[1]
        for row in base_q.with_entities(
            models.AuthorityRecord.status,
            func.count(models.AuthorityRecord.id),
        ).group_by(
            models.AuthorityRecord.status
        ).all()
        if row[0]
    }
    summary = {
        "total_records": base_q.count(),
        "pending_review": base_q.filter(
            models.AuthorityRecord.status == "pending",
            models.AuthorityRecord.review_required == True,  # noqa: E712
        ).count(),
        "nil_cases": base_q.filter(models.AuthorityRecord.nil_reason.is_not(None)).count(),
        "by_nil_reason": {
            row[0]: row[1]
            for row in base_q.with_entities(
                models.AuthorityRecord.nil_reason,
                func.count(models.AuthorityRecord.id),
            ).filter(
                models.AuthorityRecord.nil_reason.is_not(None)
            ).group_by(
                models.AuthorityRecord.nil_reason
            ).all()
            if row[0]
        },
        "by_route": summary_by_route,
        "by_status": summary_by_status,
    }

    q = base_q
    if status:
        q = q.filter(models.AuthorityRecord.status == status)
    if review_required is not None:
        q = q.filter(models.AuthorityRecord.review_required == review_required)
    if route:
        q = q.filter(models.AuthorityRecord.resolution_route == route)
    if nil_only:
        q = q.filter(models.AuthorityRecord.nil_reason.is_not(None))

    total = q.count()
    records = q.order_by(
        models.AuthorityRecord.review_required.desc(),
        models.AuthorityRecord.complexity_score.desc(),
        models.AuthorityRecord.confidence.desc(),
        models.AuthorityRecord.id.desc(),
    ).offset(skip).limit(limit).all()

    return {
        "total": total,
        "records": [_serialize_authority_record(r) for r in records],
        "summary": summary,
    }


@router.get("/authority/authors/metrics", tags=["authority"])
def author_resolution_metrics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Operational metrics for the adaptive author resolution engine only.

    This intentionally excludes legacy/generic authority rows by requiring
    `resolution_route` to be present.
    """
    org_id = resolve_request_org_id(db, current_user)
    base_q = scope_query_to_org(db.query(models.AuthorityRecord), models.AuthorityRecord, org_id).filter(
        models.AuthorityRecord.resolution_route.is_not(None)
    )

    total = base_q.count()
    pending_review = base_q.filter(
        models.AuthorityRecord.status == "pending",
        models.AuthorityRecord.review_required == True,  # noqa: E712
    ).count()
    nil_cases = base_q.filter(models.AuthorityRecord.nil_reason.is_not(None)).count()

    by_route = {
        row[0]: row[1]
        for row in base_q.with_entities(
            models.AuthorityRecord.resolution_route,
            func.count(models.AuthorityRecord.id),
        ).group_by(
            models.AuthorityRecord.resolution_route
        ).all()
        if row[0]
    }
    by_status = {
        row[0]: row[1]
        for row in base_q.with_entities(
            models.AuthorityRecord.status,
            func.count(models.AuthorityRecord.id),
        ).group_by(
            models.AuthorityRecord.status
        ).all()
        if row[0]
    }
    by_nil_reason = {
        row[0]: row[1]
        for row in base_q.with_entities(
            models.AuthorityRecord.nil_reason,
            func.count(models.AuthorityRecord.id),
        ).filter(
            models.AuthorityRecord.nil_reason.is_not(None)
        ).group_by(
            models.AuthorityRecord.nil_reason
        ).all()
        if row[0]
    }

    avg_confidence = base_q.with_entities(func.avg(models.AuthorityRecord.confidence)).scalar() or 0.0
    avg_complexity = base_q.with_entities(func.avg(models.AuthorityRecord.complexity_score)).scalar() or 0.0
    avg_nil_score = base_q.with_entities(func.avg(models.AuthorityRecord.nil_score)).scalar() or 0.0
    reformulation_attempts = base_q.filter(models.AuthorityRecord.reformulation_trace.is_not(None)).count()
    reformulation_applied = base_q.filter(models.AuthorityRecord.reformulation_applied == True).count()  # noqa: E712
    avg_reformulation_gain = (
        base_q.filter(models.AuthorityRecord.reformulation_trace.is_not(None))
        .with_entities(func.avg(models.AuthorityRecord.reformulation_gain))
        .scalar()
        or 0.0
    )
    total_reformulation_cost = (
        base_q.filter(models.AuthorityRecord.reformulation_trace.is_not(None))
        .with_entities(func.sum(models.AuthorityRecord.reformulation_cost_estimate))
        .scalar()
        or 0.0
    )
    confirmed = by_status.get("confirmed", 0)
    rejected = by_status.get("rejected", 0)

    return {
        "total_records": total,
        "pending_review": pending_review,
        "nil_cases": nil_cases,
        "avg_confidence": round(float(avg_confidence), 3),
        "avg_complexity": round(float(avg_complexity), 3),
        "avg_nil_score": round(float(avg_nil_score), 3),
        "reformulation_attempts": reformulation_attempts,
        "reformulation_applied": reformulation_applied,
        "avg_reformulation_gain": round(float(avg_reformulation_gain), 3),
        "reformulation_apply_rate": round(reformulation_applied / reformulation_attempts, 3) if reformulation_attempts > 0 else 0.0,
        "total_reformulation_cost": round(float(total_reformulation_cost), 6),
        "review_rate": round(pending_review / total, 3) if total > 0 else 0.0,
        "nil_rate": round(nil_cases / total, 3) if total > 0 else 0.0,
        "confirm_rate": round(confirmed / total, 3) if total > 0 else 0.0,
        "reject_rate": round(rejected / total, 3) if total > 0 else 0.0,
        "by_nil_reason": by_nil_reason,
        "by_route": by_route,
        "by_status": by_status,
    }


@router.get("/authority/authors/review-queue/{record_id}/compare", tags=["authority"])
def author_review_compare(
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Compare an author-engine record against sibling candidates from the same
    original query value. This supports lightweight reviewer workflows without
    introducing a heavier dedicated compare model.
    """
    org_id = resolve_request_org_id(db, current_user)
    subject = get_scoped_record(db, models.AuthorityRecord, record_id, org_id)
    if subject is None or subject.resolution_route is None:
        raise HTTPException(status_code=404, detail="Author review record not found")

    siblings = scope_query_to_org(
        db.query(models.AuthorityRecord),
        models.AuthorityRecord,
        org_id,
    ).filter(
        models.AuthorityRecord.resolution_route.is_not(None),
        models.AuthorityRecord.field_name == subject.field_name,
        models.AuthorityRecord.original_value == subject.original_value,
        models.AuthorityRecord.id != subject.id,
    ).order_by(
        models.AuthorityRecord.confidence.desc(),
        models.AuthorityRecord.id.desc(),
    ).limit(5).all()

    return {
        "subject": _serialize_authority_record(subject),
        "peers": [_serialize_authority_record(r) for r in siblings],
        "peer_count": len(siblings),
    }


@router.get("/authority/authors/review-queue/{record_id}/affiliations", tags=["authority"])
def author_review_affiliations(
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List institution authority links attached to an author authority record."""
    org_id = resolve_request_org_id(db, current_user)
    subject = get_scoped_record(db, models.AuthorityRecord, record_id, org_id)
    if subject is None or subject.resolution_route is None:
        raise HTTPException(status_code=404, detail="Author review record not found")

    links = (
        scope_query_to_org(db.query(models.AuthorityRecordLink), models.AuthorityRecordLink, org_id)
        .filter(
            models.AuthorityRecordLink.source_authority_record_id == subject.id,
            models.AuthorityRecordLink.link_type == _AFFILIATION_LINK_TYPE,
        )
        .order_by(models.AuthorityRecordLink.confidence.desc(), models.AuthorityRecordLink.id.desc())
        .all()
    )
    target_ids = [link.target_authority_record_id for link in links]
    targets = {
        record.id: record
        for record in scope_query_to_org(db.query(models.AuthorityRecord), models.AuthorityRecord, org_id)
        .filter(models.AuthorityRecord.id.in_(target_ids))
        .all()
    } if target_ids else {}

    return {
        "author_record": _serialize_authority_record(subject),
        "affiliations": [
            {
                "link": _serialize_authority_record_link(link),
                "institution_record": _serialize_authority_record(targets[link.target_authority_record_id])
                if link.target_authority_record_id in targets
                else None,
            }
            for link in links
        ],
    }


@router.post("/authority/links/{link_id}/confirm", tags=["authority"])
def confirm_authority_record_link(
    link_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Confirm an authority-to-authority relationship without mutating either record."""
    org_id = resolve_request_org_id(db, current_user)
    link = get_scoped_record(db, models.AuthorityRecordLink, link_id, org_id)
    if link is None:
        raise HTTPException(status_code=404, detail="AuthorityRecordLink not found")
    link.status = "confirmed"
    link.confirmed_at = datetime.now(timezone.utc)
    _audit(
        db,
        "authority.link.confirm",
        user_id=current_user.id,
        entity_type="authority_record_link",
        entity_id=link.id,
        details={"link_type": link.link_type},
    )
    db.commit()
    db.refresh(link)
    return _serialize_authority_record_link(link)


@router.post("/authority/links/{link_id}/reject", tags=["authority"])
def reject_authority_record_link(
    link_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Reject an authority-to-authority relationship without mutating either record."""
    org_id = resolve_request_org_id(db, current_user)
    link = get_scoped_record(db, models.AuthorityRecordLink, link_id, org_id)
    if link is None:
        raise HTTPException(status_code=404, detail="AuthorityRecordLink not found")
    link.status = "rejected"
    _audit(
        db,
        "authority.link.reject",
        user_id=current_user.id,
        entity_type="authority_record_link",
        entity_id=link.id,
        details={"link_type": link.link_type},
    )
    db.commit()
    db.refresh(link)
    return _serialize_authority_record_link(link)


@router.post("/authority/records/bulk-confirm", tags=["authority"])
def bulk_confirm_authority_records(
    payload: schemas.BulkActionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Confirm multiple authority records in one request."""
    org_id = resolve_request_org_id(db, current_user)
    confirmed = 0
    rules_created = 0
    now = datetime.now(timezone.utc)

    for record_id in payload.ids:
        rec = get_scoped_record(db, models.AuthorityRecord, record_id, org_id)
        if rec is None or rec.status == "confirmed":
            continue
        rec.status = "confirmed"
        rec.confirmed_at = now
        confirmed += 1

        if payload.also_create_rules:
            existing = scope_query_to_org(
                db.query(models.NormalizationRule), models.NormalizationRule, org_id
            ).filter(
                models.NormalizationRule.field_name == rec.field_name,
                models.NormalizationRule.original_value == rec.original_value,
            ).first()
            if not existing:
                db.add(models.NormalizationRule(
                    org_id=rec.org_id,
                    field_name=rec.field_name,
                    original_value=rec.original_value,
                    canonical_value=rec.canonical_label,
                    rule_type="exact",
                ))
                rules_created += 1

    db.commit()
    return {"confirmed": confirmed, "rules_created": rules_created}


@router.post("/authority/records/bulk-reject", tags=["authority"])
def bulk_reject_authority_records(
    payload: schemas.BulkActionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Reject multiple authority records in one request."""
    org_id = resolve_request_org_id(db, current_user)
    rejected = 0
    for record_id in payload.ids:
        rec = get_scoped_record(db, models.AuthorityRecord, record_id, org_id)
        if rec is None or rec.status == "rejected":
            continue
        rec.status = "rejected"
        rejected += 1

    db.commit()
    return {"rejected": rejected}


@router.get("/authority/records", tags=["authority"])
def list_authority_records(
    field_name: Optional[str] = Query(None, max_length=64),
    status: Optional[str] = Query(None, pattern="^(pending|confirmed|rejected)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List persisted authority candidates with optional filtering."""
    org_id = resolve_request_org_id(db, current_user)
    q = scope_query_to_org(db.query(models.AuthorityRecord), models.AuthorityRecord, org_id)
    if field_name:
        q = q.filter(models.AuthorityRecord.field_name == field_name)
    if status:
        q = q.filter(models.AuthorityRecord.status == status)
    q = q.order_by(models.AuthorityRecord.confidence.desc())
    total = q.count()
    records = q.offset(skip).limit(limit).all()
    return {
        "total":   total,
        "records": [_serialize_authority_record(r) for r in records],
    }


@router.post("/authority/records/{record_id}/confirm", tags=["authority"])
def confirm_authority_record(
    record_id: int = Path(ge=1),
    payload: schemas.AuthorityConfirmRequest = schemas.AuthorityConfirmRequest(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Confirm a candidate as the authoritative form."""
    org_id = resolve_request_org_id(db, current_user)
    rec = get_scoped_record(db, models.AuthorityRecord, record_id, org_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="AuthorityRecord not found")

    rec.status = "confirmed"
    rec.confirmed_at = datetime.now(timezone.utc)

    rule_created = False
    if payload.also_create_rule:
        existing = scope_query_to_org(
            db.query(models.NormalizationRule), models.NormalizationRule, org_id
        ).filter(
            models.NormalizationRule.field_name == rec.field_name,
            models.NormalizationRule.original_value == rec.original_value,
        ).first()
        if not existing:
            db.add(models.NormalizationRule(
                org_id=rec.org_id,
                field_name=rec.field_name,
                original_value=rec.original_value,
                canonical_value=rec.canonical_label,
                rule_type="exact",
            ))
            rule_created = True

    _audit(
        db, "authority.confirm",
        user_id=current_user.id,
        entity_type="authority_record",
        entity_id=record_id,
        details={"canonical_label": rec.canonical_label, "rule_created": rule_created},
    )
    db.commit()
    db.refresh(rec)
    return {**_serialize_authority_record(rec), "rule_created": rule_created}


@router.post("/authority/records/{record_id}/reject", tags=["authority"])
def reject_authority_record(
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Mark a candidate as rejected."""
    org_id = resolve_request_org_id(db, current_user)
    rec = get_scoped_record(db, models.AuthorityRecord, record_id, org_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="AuthorityRecord not found")
    rec.status = "rejected"
    _audit(
        db, "authority.reject",
        user_id=current_user.id,
        entity_type="authority_record",
        entity_id=record_id,
    )
    db.commit()
    db.refresh(rec)
    return _serialize_authority_record(rec)


@router.delete("/authority/records/{record_id}", tags=["authority"])
def delete_authority_record(
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Permanently delete an authority candidate record."""
    org_id = resolve_request_org_id(db, current_user)
    rec = get_scoped_record(db, models.AuthorityRecord, record_id, org_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="AuthorityRecord not found")
    db.delete(rec)
    db.commit()
    return {"message": "Deleted", "id": record_id}


@router.get("/authority/metrics", tags=["authority"])
def authority_metrics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Operational and quality KPIs for the Authority Resolution Layer."""
    org_id = resolve_request_org_id(db, current_user)
    total = (
        scope_query_to_org(db.query(func.count(models.AuthorityRecord.id)), models.AuthorityRecord, org_id)
        .scalar()
        or 0
    )

    by_status: dict = {}
    for row in (
        scope_query_to_org(
            db.query(models.AuthorityRecord.status, func.count(models.AuthorityRecord.id)),
            models.AuthorityRecord,
            org_id,
        )
        .group_by(models.AuthorityRecord.status)
        .all()
    ):
        by_status[row[0]] = row[1]

    by_resolution: dict = {}
    for row in (
        scope_query_to_org(
            db.query(models.AuthorityRecord.resolution_status, func.count(models.AuthorityRecord.id)),
            models.AuthorityRecord,
            org_id,
        )
        .group_by(models.AuthorityRecord.resolution_status)
        .all()
    ):
        if row[0]:
            by_resolution[row[0]] = row[1]

    by_source: dict = {}
    for row in (
        scope_query_to_org(
            db.query(models.AuthorityRecord.authority_source, func.count(models.AuthorityRecord.id)),
            models.AuthorityRecord,
            org_id,
        )
        .group_by(models.AuthorityRecord.authority_source)
        .all()
    ):
        by_source[row[0]] = row[1]

    avg_conf = (
        scope_query_to_org(db.query(func.avg(models.AuthorityRecord.confidence)), models.AuthorityRecord, org_id)
        .scalar()
        or 0.0
    )
    confirmed = by_status.get("confirmed", 0)
    rejected  = by_status.get("rejected", 0)

    return {
        "total_records":        total,
        "by_status":            by_status,
        "by_resolution_status": by_resolution,
        "by_source":            by_source,
        "avg_confidence":       round(float(avg_conf), 3),
        "confirm_rate":         round(confirmed / total, 3) if total > 0 else 0.0,
        "reject_rate":          round(rejected  / total, 3) if total > 0 else 0.0,
    }


# ── Authority field view (wildcard — must come LAST) ──────────────────────────

@router.get("/authority/{field}")
def get_authority_view(
    field: str,
    threshold: int = Query(default=80, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    try:
        groups = _build_disambig_groups(field, threshold, db, org_id=org_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    rules = scope_query_to_org(
        db.query(models.NormalizationRule), models.NormalizationRule, org_id
    ).filter(
        models.NormalizationRule.field_name == field
    ).all()
    rules_by_original = {r.original_value: r.normalized_value for r in rules}

    annotated = []
    for g in groups:
        resolved_to = None
        has_rules = False
        for var in g["variations"]:
            if var in rules_by_original:
                has_rules = True
                resolved_to = rules_by_original[var]
                break
        annotated.append({**g, "has_rules": has_rules, "resolved_to": resolved_to})

    total_rules = (
        scope_query_to_org(
            db.query(func.count(models.NormalizationRule.id)), models.NormalizationRule, org_id
        )
        .filter(models.NormalizationRule.field_name == field)
        .scalar() or 0
    )

    return {
        "groups":        annotated,
        "total_groups":  len(annotated),
        "total_rules":   total_rules,
        "pending_groups": sum(1 for g in annotated if not g["has_rules"]),
    }
