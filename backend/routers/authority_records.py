"""
Authority record management, thresholds, and metrics endpoints extracted from authority.py.

  POST /authority/links/{link_id}/confirm
  POST /authority/links/{link_id}/reject
  POST /authority/records/bulk-confirm
  POST /authority/records/bulk-reject
  GET  /authority/records
  POST /authority/records/{record_id}/confirm
  POST /authority/records/{record_id}/reject
  DELETE /authority/records/{record_id}
  POST /authority/thresholds
  GET  /authority/thresholds
  DELETE /authority/thresholds/{threshold_id}
  GET  /authority/metrics
  GET  /authority/{field}          ← catch-all, MUST be last
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import get_current_user, require_role
from backend.authority import entity_writeback as _authority_writeback
from backend.authority import feedback as _authority_feedback
from backend.authority import thresholds as _authority_thresholds
from backend.database import get_db
from backend.routers.deps import (
    _audit,
    _build_disambig_groups,
    _serialize_authority_record,
    _serialize_authority_record_link,
)
from backend.tenant_access import (
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

router = APIRouter(tags=["authority"])


# ── Link confirm/reject ──────────────────────────────────────────────────────

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


# ── Bulk confirm/reject ──────────────────────────────────────────────────────

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
    entities_updated = 0
    now = datetime.now(timezone.utc)

    for record_id in payload.ids:
        rec = get_scoped_record(db, models.AuthorityRecord, record_id, org_id)
        if rec is None or rec.status == "confirmed":
            continue
        rec.status = "confirmed"
        rec.confirmed_at = now
        confirmed += 1

        # Close the loop: promote matching derived entities' weak canonical_id
        # to the confirmed external identity (best-effort, never raises).
        entities_updated += _authority_writeback.promote_confirmed_identity(
            db, rec, org_id=rec.org_id
        )

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
    return {
        "confirmed": confirmed,
        "rules_created": rules_created,
        "entities_updated": entities_updated,
    }


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


@router.post("/authority/records/purge", tags=["authority"])
def purge_authority_records(
    field_name: Optional[str] = Query(None, max_length=64),
    status: str = Query("pending", pattern="^(pending|rejected)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Bulk-delete unreviewed records so they can be re-resolved (e.g. after
    enabling orcid_hint). Only ``pending``/``rejected`` are ever deletable —
    ``confirmed`` records are never touched. Optionally scoped to ``field_name``.
    """
    org_id = resolve_request_org_id(db, current_user)
    q = scope_query_to_org(
        db.query(models.AuthorityRecord), models.AuthorityRecord, org_id
    ).filter(models.AuthorityRecord.status == status)
    if field_name:
        q = q.filter(models.AuthorityRecord.field_name == field_name)
    deleted = q.delete(synchronize_session=False)
    _audit(
        db, "authority.purge",
        user_id=current_user.id,
        entity_type="authority_record",
        entity_id=0,
        details={"field_name": field_name, "status": status, "deleted": deleted},
    )
    db.commit()
    return {"deleted": deleted, "field_name": field_name, "status": status}


@router.post("/authority/resolver-cache/purge", tags=["authority"])
def purge_resolver_cache(
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Flush the external-authority resolver cache (Redis, 1-week TTL,
    deploy-surviving). Run after a resolver behavior change so the next
    resolution re-hits the sources instead of serving stale cached candidates.
    """
    from backend.authority.cache import get_resolver_cache

    removed = get_resolver_cache().clear()
    return {"cache_keys_removed": removed}


# ── Record CRUD ──────────────────────────────────────────────────────────────

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

    # Record positive feedback for this (field, source) so the scoring engine
    # can learn a bounded prior (Task 10).
    if rec.field_name and rec.authority_source:
        _authority_feedback.record_outcome(
            db, rec.field_name, rec.authority_source,
            confirmed=True, org_id=rec.org_id,
        )

    # Close the loop: promote matching derived entities' weak canonical_id to
    # the confirmed external identity (best-effort, never raises).
    entities_updated = _authority_writeback.promote_confirmed_identity(
        db, rec, org_id=rec.org_id
    )

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
        details={
            "canonical_label": rec.canonical_label,
            "rule_created": rule_created,
            "entities_updated": entities_updated,
        },
    )
    db.commit()
    db.refresh(rec)
    return {
        **_serialize_authority_record(rec),
        "rule_created": rule_created,
        "entities_updated": entities_updated,
    }


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
    if rec.field_name and rec.authority_source:
        _authority_feedback.record_outcome(
            db, rec.field_name, rec.authority_source,
            rejected=True, org_id=rec.org_id,
        )
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


# ── Adaptive resolution thresholds (Phase 3, Task 11) ─────────────────────────

@router.post("/authority/thresholds", tags=["authority"], status_code=201)
def upsert_resolution_threshold(
    payload: schemas.ResolutionThresholdCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Create or update a per-(org, domain, field) resolution-threshold override."""
    org_id = persisted_org_id(resolve_request_org_id(db, current_user))
    row = (
        scope_query_to_org(
            db.query(models.ResolutionThreshold), models.ResolutionThreshold, org_id
        )
        .filter(
            models.ResolutionThreshold.domain_id == payload.domain_id,
            models.ResolutionThreshold.field_name == payload.field_name,
        )
        .first()
    )
    if row is None:
        row = models.ResolutionThreshold(
            org_id=org_id, domain_id=payload.domain_id, field_name=payload.field_name,
        )
        db.add(row)
    row.exact = payload.exact
    row.probable = payload.probable
    row.ambiguous = payload.ambiguous
    db.commit()
    db.refresh(row)
    _authority_thresholds.clear_cache()
    return schemas.ResolutionThresholdResponse.model_validate(row)


@router.get("/authority/thresholds", tags=["authority"])
def list_resolution_thresholds(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List resolution-threshold overrides for the caller's organization."""
    org_id = persisted_org_id(resolve_request_org_id(db, current_user))
    rows = scope_query_to_org(
        db.query(models.ResolutionThreshold), models.ResolutionThreshold, org_id
    ).all()
    return [schemas.ResolutionThresholdResponse.model_validate(r) for r in rows]


@router.delete("/authority/thresholds/{threshold_id}", tags=["authority"])
def delete_resolution_threshold(
    threshold_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Delete a resolution-threshold override (falls back to defaults)."""
    org_id = persisted_org_id(resolve_request_org_id(db, current_user))
    row = get_scoped_record(db, models.ResolutionThreshold, threshold_id, org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ResolutionThreshold not found")
    db.delete(row)
    db.commit()
    _authority_thresholds.clear_cache()
    return {"message": "Deleted", "id": threshold_id}


# ── Metrics ──────────────────────────────────────────────────────────────────

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


# ── Authority field view (wildcard — MUST come LAST) ─────────────────────────

@router.get("/authority/{field}")
def get_authority_view(
    field: str,
    response: Response,
    threshold: int = Query(default=80, ge=0, le=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    try:
        groups, total_groups = _build_disambig_groups(
            field, threshold, db, org_id=org_id, skip=skip, limit=limit, with_total=True,
        )
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

    response.headers["X-Total-Count"] = str(total_groups)
    return {
        "groups":        annotated,
        "total_groups":  total_groups,
        "total_rules":   total_rules,
        "pending_groups": sum(1 for g in annotated if not g["has_rules"]),
    }
