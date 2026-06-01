"""
Institution reconciliation endpoints extracted from authority.py.

  POST /authority/institutions/reconcile/preview
  POST /authority/institutions/reconcile/apply
  GET  /authority/institutions/review-queue
  POST /authority/institutions/review-queue/{record_id}/accept
  POST /authority/institutions/review-queue/{record_id}/reject
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.routers.deps import (
    _serialize_authority_record,
)
from backend.services.institution_reconciliation import (
    RORAdapter,
    RORRecord,
    extract_institution_candidates,
    normalize_ror_id,
    score_institution_match,
)
from backend.tenant_access import (
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

# Re-use shared constants from the core authority module.
from backend.routers.authority import _AFFILIATION_LINK_TYPE, _link_confidence

router = APIRouter(tags=["authority"])


# ── Pydantic models ──────────────────────────────────────────────────────────

class InstitutionReconcilePreviewRequest(BaseModel):
    entity_ids: list[int] | None = Field(default=None, max_length=100)
    domain_id: str | None = None
    limit: int = Field(default=25, ge=1, le=100)
    live_lookup: bool = False


class InstitutionReconcileApplyRequest(InstitutionReconcilePreviewRequest):
    auto_accept_threshold: float = Field(default=0.9, ge=0.0, le=1.0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _institution_candidate_rows(
    db: Session,
    *,
    org_id: int | None,
    payload: InstitutionReconcilePreviewRequest,
) -> list[models.RawEntity]:
    q = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
    if payload.entity_ids:
        q = q.filter(models.RawEntity.id.in_(payload.entity_ids))
    if payload.domain_id and payload.domain_id != "all":
        q = q.filter(models.RawEntity.domain == payload.domain_id)
    return q.order_by(models.RawEntity.id.asc()).limit(payload.limit).all()


def _preview_institution_reconciliation(
    db: Session,
    *,
    org_id: int | None,
    payload: InstitutionReconcilePreviewRequest,
) -> dict:
    adapter = RORAdapter()
    items: list[dict] = []
    for entity in _institution_candidate_rows(db, org_id=org_id, payload=payload):
        candidates = extract_institution_candidates(entity.attributes_json)
        for candidate in candidates:
            matches = []
            if candidate.ror:
                record = adapter.lookup(candidate.ror)
                if record is not None:
                    matches = [score_institution_match(candidate, record)]
            elif payload.live_lookup:
                matches = [
                    score_institution_match(candidate, record)
                    for record in adapter.search(candidate.name, candidate.country_code)
                ]
            matches.sort(key=lambda match: match.score, reverse=True)
            items.append({
                "entity_id": entity.id,
                "entity_label": entity.primary_label,
                "candidate": candidate.to_dict(),
                "matches": [match.to_dict() for match in matches],
                "best_match": matches[0].to_dict() if matches else None,
            })
    return {"count": len(items), "items": items}


def _find_existing_institution_record(
    db: Session,
    *,
    org_id: int | None,
    original_value: str,
    authority_source: str,
    authority_id: str,
) -> models.AuthorityRecord | None:
    return scope_query_to_org(db.query(models.AuthorityRecord), models.AuthorityRecord, org_id).filter(
        models.AuthorityRecord.field_name == "affiliation",
        models.AuthorityRecord.original_value == original_value,
        models.AuthorityRecord.authority_source == authority_source,
        models.AuthorityRecord.authority_id == authority_id,
    ).first()


def _persist_institution_match(
    db: Session,
    *,
    org_id: int | None,
    entity_id: int,
    match: dict,
    threshold: float,
) -> tuple[models.AuthorityRecord, bool]:
    candidate = match["candidate"]
    record = match["record"]
    existing = _find_existing_institution_record(
        db,
        org_id=org_id,
        original_value=candidate["name"],
        authority_source="ror",
        authority_id=record["ror_id"],
    )
    if existing is not None:
        return existing, False

    score = float(match["score"])
    auto_accept = bool(match.get("auto_accept")) and score >= threshold
    merged_sources = [f"ror:{record['ror_id']}"]
    if candidate.get("openalex_id"):
        merged_sources.append(f"openalex:{candidate['openalex_id']}")

    rec = models.AuthorityRecord(
        org_id=persisted_org_id(org_id),
        field_name="affiliation",
        original_value=candidate["name"],
        authority_source="ror",
        authority_id=record["ror_id"],
        canonical_label=record["name"],
        aliases=json.dumps([*record.get("aliases", []), *record.get("acronyms", [])]),
        description="; ".join(
            part
            for part in [
                "ROR organization",
                f"country={record.get('country_code')}" if record.get("country_code") else None,
                f"types={','.join(record.get('types') or [])}" if record.get("types") else None,
            ]
            if part
        ),
        confidence=score,
        uri=record.get("uri") or RORRecord(record["ror_id"], record["name"]).uri,
        status="confirmed" if auto_accept else "pending",
        confirmed_at=datetime.now(timezone.utc) if auto_accept else None,
        resolution_status=match.get("status") or "unresolved",
        score_breakdown=json.dumps(match.get("breakdown") or {}),
        evidence=json.dumps([*(match.get("evidence") or []), f"raw_entity:{entity_id}"]),
        merged_sources=json.dumps(merged_sources),
        review_required=not auto_accept,
    )
    db.add(rec)
    return rec, True


def _candidate_identity(candidate: dict) -> tuple[str, str]:
    if candidate.get("ror"):
        return ("ror", normalize_ror_id(candidate.get("ror")) or str(candidate["ror"]).strip().lower())
    if candidate.get("openalex_id"):
        return ("openalex", str(candidate["openalex_id"]).strip().lower())
    return (
        "name_country",
        f"{str(candidate.get('name') or '').strip().casefold()}|{str(candidate.get('country_code') or '').strip().upper()}",
    )


def _author_names_for_institution(entity: models.RawEntity, candidate: dict) -> list[str]:
    try:
        attrs = json.loads(entity.attributes_json or "{}")
    except (TypeError, ValueError):
        return []
    if not isinstance(attrs, dict):
        return []

    target = _candidate_identity(candidate)
    names: list[str] = []
    for author_affiliation in attrs.get("author_affiliations") or []:
        if not isinstance(author_affiliation, dict):
            continue
        author_name = str(author_affiliation.get("author_name") or "").strip()
        if not author_name:
            continue
        for institution in author_affiliation.get("institutions") or []:
            if not isinstance(institution, dict):
                continue
            current = _candidate_identity({
                "name": institution.get("name") or institution.get("display_name"),
                "ror": institution.get("ror"),
                "openalex_id": institution.get("openalex_id") or institution.get("id"),
                "country_code": institution.get("country_code"),
            })
            if current == target:
                names.append(author_name)
                break
    return sorted(set(names))


def _find_author_authority_record(
    db: Session,
    *,
    org_id: int | None,
    author_name: str,
) -> models.AuthorityRecord | None:
    return scope_query_to_org(db.query(models.AuthorityRecord), models.AuthorityRecord, org_id).filter(
        models.AuthorityRecord.field_name.in_(("author_name", "author")),
        models.AuthorityRecord.status != "rejected",
        (
            (models.AuthorityRecord.original_value == author_name)
            | (models.AuthorityRecord.canonical_label == author_name)
        ),
    ).order_by(
        models.AuthorityRecord.status.asc(),
        models.AuthorityRecord.confidence.desc(),
        models.AuthorityRecord.id.desc(),
    ).first()


def _ensure_author_institution_links(
    db: Session,
    *,
    org_id: int | None,
    entity: models.RawEntity,
    institution_record: models.AuthorityRecord,
    candidate: dict,
) -> int:
    created = 0
    for author_name in _author_names_for_institution(entity, candidate):
        author_record = _find_author_authority_record(db, org_id=org_id, author_name=author_name)
        if author_record is None:
            continue
        existing = scope_query_to_org(db.query(models.AuthorityRecordLink), models.AuthorityRecordLink, org_id).filter(
            models.AuthorityRecordLink.source_authority_record_id == author_record.id,
            models.AuthorityRecordLink.target_authority_record_id == institution_record.id,
            models.AuthorityRecordLink.link_type == _AFFILIATION_LINK_TYPE,
        ).first()
        if existing is not None:
            continue
        confidence = _link_confidence(author_record, institution_record)
        db.add(models.AuthorityRecordLink(
            org_id=persisted_org_id(org_id),
            source_authority_record_id=author_record.id,
            target_authority_record_id=institution_record.id,
            link_type=_AFFILIATION_LINK_TYPE,
            confidence=confidence,
            status="confirmed" if confidence >= 0.88 and institution_record.status == "confirmed" else "pending",
            confirmed_at=datetime.now(timezone.utc)
            if confidence >= 0.88 and institution_record.status == "confirmed"
            else None,
            evidence=json.dumps([
                f"raw_entity:{entity.id}",
                f"author_name:{author_name}",
                f"institution_record:ror:{institution_record.authority_id}",
                f"institution_confidence:{float(institution_record.confidence or 0.0):.3f}",
            ]),
        ))
        created += 1
    return created


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/authority/institutions/reconcile/preview", tags=["authority"])
def institution_reconcile_preview(
    payload: InstitutionReconcilePreviewRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    return _preview_institution_reconciliation(db, org_id=org_id, payload=payload)


@router.post("/authority/institutions/reconcile/apply", tags=["authority"])
def institution_reconcile_apply(
    payload: InstitutionReconcileApplyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    preview = _preview_institution_reconciliation(db, org_id=org_id, payload=payload)
    created = 0
    reused = 0
    links_created = 0
    records: list[models.AuthorityRecord] = []
    for item in preview["items"]:
        best = item.get("best_match")
        if not best:
            continue
        rec, was_created = _persist_institution_match(
            db,
            org_id=org_id,
            entity_id=item["entity_id"],
            match=best,
            threshold=payload.auto_accept_threshold,
        )
        records.append(rec)
        created += 1 if was_created else 0
        reused += 0 if was_created else 1
        if rec.id is None:
            db.flush()
        entity = get_scoped_record(db, models.RawEntity, item["entity_id"], org_id)
        if entity is not None:
            links_created += _ensure_author_institution_links(
                db,
                org_id=org_id,
                entity=entity,
                institution_record=rec,
                candidate=best["candidate"],
            )
    db.commit()
    for rec in records:
        db.refresh(rec)
    return {
        "preview_count": preview["count"],
        "created": created,
        "reused": reused,
        "links_created": links_created,
        "records": [_serialize_authority_record(r) for r in records],
    }


@router.get("/authority/institutions/review-queue", tags=["authority"])
def institution_review_queue(
    status: Optional[str] = Query("pending", pattern="^(pending|confirmed|rejected)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    q = scope_query_to_org(db.query(models.AuthorityRecord), models.AuthorityRecord, org_id).filter(
        models.AuthorityRecord.field_name == "affiliation",
        models.AuthorityRecord.authority_source == "ror",
        models.AuthorityRecord.review_required == True,  # noqa: E712
    )
    if status:
        q = q.filter(models.AuthorityRecord.status == status)
    total = q.count()
    records = q.order_by(
        models.AuthorityRecord.confidence.desc(),
        models.AuthorityRecord.id.desc(),
    ).offset(skip).limit(limit).all()
    return {"total": total, "records": [_serialize_authority_record(r) for r in records]}


@router.post("/authority/institutions/review-queue/{record_id}/accept", tags=["authority"])
def institution_review_accept(
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    rec = get_scoped_record(db, models.AuthorityRecord, record_id, org_id)
    if rec is None or rec.field_name != "affiliation" or rec.authority_source != "ror":
        raise HTTPException(status_code=404, detail="Institution authority record not found")
    rec.status = "confirmed"
    rec.review_required = False
    rec.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rec)
    return _serialize_authority_record(rec)


@router.post("/authority/institutions/review-queue/{record_id}/reject", tags=["authority"])
def institution_review_reject(
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    rec = get_scoped_record(db, models.AuthorityRecord, record_id, org_id)
    if rec is None or rec.field_name != "affiliation" or rec.authority_source != "ror":
        raise HTTPException(status_code=404, detail="Institution authority record not found")
    rec.status = "rejected"
    rec.review_required = False
    db.commit()
    db.refresh(rec)
    return _serialize_authority_record(rec)
