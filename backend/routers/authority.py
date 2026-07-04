"""
Authority resolution layer — core resolution endpoints.

  POST /authority/resolve
  POST /authority/authors/resolve
  POST /authority/resolve/batch
  GET  /authority/jobs/{job_id}
  GET  /authority/queue/summary
  GET  /authority/authors/review-queue
  GET  /authority/authors/metrics
  GET  /authority/authors/review-queue/{record_id}/compare
  GET  /authority/authors/review-queue/{record_id}/affiliations
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import get_current_user, require_role
from backend.authority.author_resolution import summarize_author_resolution
from backend.authority import coauthorship_signal as _coauthorship_signal
from backend.authority import feedback as _authority_feedback
from backend.authority import thresholds as _authority_thresholds
from backend.authority.base import ResolveContext as _AuthorityContext
from backend.authority.batch_resolution import (
    InvalidFieldError,
    execute_batch_resolution,
    validate_field,
)
from backend.authority.hierarchical_fallback import apply_hierarchical_fallback
from backend.authority.query_reformulation import run_author_query_reformulation
from backend.authority.resolver import resolve_all as _authority_resolve_all
from backend.authority.resolver import resolve_all_via_engine as _authority_resolve_engine
from backend.database import get_db
from backend.routers.deps import (
    _serialize_authority_record,
    _serialize_authority_record_link,
)
from backend.services.engine_delegation import run_coro_sync
from backend.routers.limiter import limiter
from backend.tenant_access import (
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["authority"])

_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_AFFILIATION_LINK_TYPE = "affiliated-with"


# ── Shared helpers (used by authority_institutions.py) ────────────────────────

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

# ── Endpoints ─────────────────────────────────────────────────────────────────

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
        source_priors=_authority_feedback.get_source_priors(
            db, payload.field_name, org_id=record_org_id
        ),
        thresholds=_authority_thresholds.get_thresholds(
            db, payload.field_name,
            domain_id=getattr(payload, "domain_id", None),
            org_id=record_org_id,
        ),
    )

    # Coauthorship signal (Task 7 wiring): for person resolution, source the
    # query author's collaborators from the local graph and bind a provider so
    # the resolver can look up each candidate's collaborators by canonical label.
    if payload.entity_type == schemas.AuthorityEntityType.person:
        graph_org_id = record_org_id if record_org_id is not None else 0
        graph_domain_id = getattr(payload, "domain_id", None)
        query_coauthors = _coauthorship_signal.local_coauthor_names(
            db, payload.value, org_id=graph_org_id, domain_id=graph_domain_id
        )
        if query_coauthors:
            ctx.coauthors = query_coauthors
            ctx.candidate_coauthor_provider = _coauthorship_signal.make_local_coauthor_provider(
                db, org_id=graph_org_id, domain_id=graph_domain_id
            )

    # Try engine delegation first, fall back to Python resolvers. This endpoint
    # is sync (the Python resolver blocks on external HTTP in a threadpool), so
    # we bridge to the async engine call via a safe run-to-completion helper.
    engine_client = getattr(request.app.state, "engine_client", None)
    engine_candidates = None
    if engine_client:
        engine_candidates = run_coro_sync(
            _authority_resolve_engine(
                payload.value, payload.entity_type.value, ctx, engine_client
            )
        )

    if engine_candidates is not None:
        candidates = engine_candidates
    else:
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
    sync: bool = Query(False, description="Run inline (legacy) instead of enqueuing an async job"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Resolve all distinct values of a field against external authority sources.

    Default mode enqueues an async ``AuthorityResolveJob`` and returns a job id;
    poll ``GET /authority/jobs/{job_id}`` for progress. Pass ``?sync=true`` to
    run inline and receive the resolved records in the response (legacy shape).
    """
    org_id = resolve_request_org_id(db, current_user)
    record_org_id = persisted_org_id(org_id)
    field = payload.field_name
    entity_type = payload.entity_type.value

    try:
        validate_field(db, field)
    except InvalidFieldError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if not sync:
        job = models.AuthorityResolveJob(
            org_id=record_org_id,
            field_name=field,
            entity_type=entity_type,
            params_json=json.dumps({"limit": payload.limit, "skip_existing": payload.skip_existing}),
            status="pending",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return {
            "job_id": job.id,
            "status": job.status,
            "field_name": field,
            "entity_type": entity_type,
        }

    summary, new_records = execute_batch_resolution(
        db,
        org_id=org_id,
        record_org_id=record_org_id,
        field=field,
        entity_type=entity_type,
        limit=payload.limit,
        skip_existing=payload.skip_existing,
        resolve_fn=_authority_resolve_all,
    )
    db.commit()
    for rec in new_records:
        db.refresh(rec)

    summary["records"] = [_serialize_authority_record(r) for r in new_records]
    return summary


@router.get("/authority/jobs/{job_id}", tags=["authority"])
def get_authority_job(
    job_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return status + progress counters for an async batch resolution job."""
    org_id = resolve_request_org_id(db, current_user)
    job = get_scoped_record(db, models.AuthorityResolveJob, job_id, org_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "field_name": job.field_name,
        "entity_type": job.entity_type,
        "total": job.total or 0,
        "processed": job.processed or 0,
        "records_created": job.records_created or 0,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
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
