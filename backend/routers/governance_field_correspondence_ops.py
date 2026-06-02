"""
Governance API — Field Correspondence Operations.
  GET    /field-correspondence-rules/governance-metrics
  POST   /field-correspondence-rules/preventive-seed
  GET    /field-correspondence-rules/jobs
  GET    /field-correspondence-rules/review-export.csv
  POST   /field-correspondence-rules/jobs/{job_id}/rollback
  POST   /field-correspondence-rules/impact
  POST   /field-correspondence-rules/{rule_id}/apply
  POST   /field-correspondence-rules/{rule_id}/review-status
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend import models

from backend.routers.governance_field_correspondence import (
    FieldCorrespondenceRuleResponse,
    FieldCorrespondenceRulePayload,
    _json_list,
    _json_object,
    _serialize_rule,
    _dump_rule,
    _audit_rule_change,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["governance"])


# ── Pydantic models ──────────────────────────────────────────────────────────

class PreventiveRuleSeedResponse(BaseModel):
    created: int
    updated: int
    total_candidates: int
    rules: list[FieldCorrespondenceRuleResponse] = Field(default_factory=list)


class FieldCorrespondenceImpactExample(BaseModel):
    entity_id: int
    primary_label: str | None = None
    import_batch_id: int | None = None
    source_field: str
    current_value: str | None = None
    location: str


class FieldCorrespondenceImpactResponse(BaseModel):
    source_schema: str | None = None
    source_field: str
    canonical_target: str | None = None
    affected_records: int
    affected_import_batches: int
    matching_suggestions: int
    examples: list[FieldCorrespondenceImpactExample] = Field(default_factory=list)


class AmbiguousSourceMetric(BaseModel):
    source_schema: str
    pending_suggestions: int


class GovernanceMetricsResponse(BaseModel):
    active_rules: int
    inactive_rules: int
    approved_rules: int = 0
    pending_rules: int = 0
    rejected_rules: int = 0
    needs_adjustment_rules: int = 0
    pending_suggestions: int
    rejected_false_positives: int
    ambiguous_sources: list[AmbiguousSourceMetric] = Field(default_factory=list)


class FieldCorrespondenceApplyPayload(BaseModel):
    dry_run: bool = True
    overwrite_existing: bool = False
    limit: int = Field(default=5000, ge=1, le=50000)


class FieldCorrespondenceReviewPayload(BaseModel):
    review_status: str = Field(..., pattern=r"^(pending|approved|rejected|needs_adjustment)$")


class FieldCorrespondenceApplyResponse(FieldCorrespondenceImpactResponse):
    dry_run: bool
    overwrite_existing: bool
    job_id: int | None = None
    updated_records: int = 0
    skipped_existing: int = 0
    skipped_missing_value: int = 0


class FieldCorrespondenceJobResponse(BaseModel):
    id: int
    rule_id: int | None = None
    rule_label: str | None = None
    username: str | None = None
    records_updated: int
    affected_records: int = 0
    skipped_existing: int = 0
    skipped_missing_value: int = 0
    fields_modified: list[str] = Field(default_factory=list)
    executed_at: str | None = None
    reverted: bool = False


class FieldCorrespondenceRollbackResponse(BaseModel):
    job_id: int
    records_restored: int
    reverted: bool


# ── Helpers ───────────────────────────────────────────────────────────────────

def _preventive_rule_candidates() -> list[dict]:
    source_schemas = [None, "csv", "wos", "ris", "bibtex", "openalex", "crossref", "orcid", "ror"]
    identifier_aliases = {
        "doi": ["DOI", "doi", "DI", "DO", "doi_url", "external_doi"],
        "orcid": ["ORCID", "orcid", "author_orcid", "researcher_id", "researcher_orcid"],
        "ror": ["ROR", "ror", "affiliation_ror", "institution_ror", "organization_ror"],
        "local": ["ID", "id", "source_id", "record_id", "UT", "UID", "EID", "Accession Number"],
    }
    entity_type_aliases = ["type", "Type", "entity_type", "document_type", "publication_type", "resource_type", "item_type", "TY"]
    candidates: list[dict] = []
    for source_schema in source_schemas:
        for identifier_scheme, fields in identifier_aliases.items():
            for source_field in fields:
                candidates.append({
                    "source_schema": source_schema,
                    "source_field": source_field,
                    "canonical_target": "canonical_id",
                    "semantic_concept": "persistent_identifier",
                    "identifier_scheme": identifier_scheme,
                })
        for source_field in entity_type_aliases:
            candidates.append({
                "source_schema": source_schema,
                "source_field": source_field,
                "canonical_target": "entity_type",
                "semantic_concept": "entity_type",
                "identifier_scheme": None,
            })
    return candidates


def _field_correspondence_matches(
    attrs: dict,
    *,
    source_field: str,
    source_schema: str | None,
) -> bool:
    correspondence = attrs.get("_field_correspondence")
    if not isinstance(correspondence, dict) or source_field not in correspondence:
        return False
    if not source_schema:
        return True
    metadata = correspondence.get(source_field)
    if not isinstance(metadata, dict):
        return False
    evidence = metadata.get("evidence") or []
    return any(str(item).startswith(f"{source_schema}_") for item in evidence)


def _rule_candidate_query(
    db: Session,
    *,
    org_id: int | None,
    source_field: str,
):
    candidates = db.query(models.RawEntity).filter(
        (
            models.RawEntity.normalized_json.like(f'%"{source_field}"%')
            | models.RawEntity.attributes_json.like(f'%"{source_field}"%')
        )
    )
    if org_id is None:
        return candidates.filter(models.RawEntity.org_id.is_(None))
    return candidates.filter(models.RawEntity.org_id == org_id)


def _extract_rule_value(
    entity: models.RawEntity,
    *,
    source_field: str,
    source_schema: str | None,
    canonical_target: str | None,
) -> tuple[str | None, object | None]:
    normalized = _json_object(entity.normalized_json)
    attrs = _json_object(entity.attributes_json)
    if source_field in normalized:
        return "normalized_json", normalized.get(source_field)
    if _field_correspondence_matches(attrs, source_field=source_field, source_schema=source_schema):
        if canonical_target and hasattr(entity, canonical_target):
            return "attributes_json._field_correspondence", getattr(entity, canonical_target)
        return "attributes_json._field_correspondence", None
    return None, None


def _serialize_field_correspondence_job(log: models.HarmonizationLog) -> FieldCorrespondenceJobResponse:
    details = _json_object(log.details)
    fields_modified = _json_list(log.fields_modified)
    return FieldCorrespondenceJobResponse(
        id=log.id,
        rule_id=details.get("rule_id") if isinstance(details.get("rule_id"), int) else None,
        rule_label=details.get("rule_label") if isinstance(details.get("rule_label"), str) else None,
        username=details.get("username") if isinstance(details.get("username"), str) else None,
        records_updated=log.records_updated or 0,
        affected_records=int(details.get("affected_records") or 0),
        skipped_existing=int(details.get("skipped_existing") or 0),
        skipped_missing_value=int(details.get("skipped_missing_value") or 0),
        fields_modified=fields_modified,
        executed_at=log.executed_at.isoformat() if log.executed_at else None,
        reverted=bool(log.reverted),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/field-correspondence-rules/governance-metrics",
    response_model=GovernanceMetricsResponse,
    dependencies=[Depends(get_current_user)],
)
def get_field_correspondence_governance_metrics(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Summarize field correspondence governance health for the current tenant."""
    from backend.tenant_access import resolve_request_org_id

    org_id = resolve_request_org_id(db, current_user)
    rule_query = db.query(models.FieldCorrespondenceRule)
    suggestion_query = db.query(models.MappingSuggestionRecord)
    if org_id is None:
        rule_query = rule_query.filter(models.FieldCorrespondenceRule.org_id.is_(None))
        suggestion_query = suggestion_query.filter(models.MappingSuggestionRecord.org_id.is_(None))
    else:
        rule_query = rule_query.filter(models.FieldCorrespondenceRule.org_id == org_id)
        suggestion_query = suggestion_query.filter(models.MappingSuggestionRecord.org_id == org_id)

    active_rules = rule_query.filter(models.FieldCorrespondenceRule.is_active.is_(True)).count()
    inactive_rules = rule_query.filter(models.FieldCorrespondenceRule.is_active.is_(False)).count()
    all_rules = rule_query.all()
    serialized_rules = [_serialize_rule(rule) for rule in all_rules]
    approved_rules = sum(1 for rule in serialized_rules if rule.review_status == "approved")
    pending_rules = sum(1 for rule in serialized_rules if rule.review_status == "pending")
    rejected_rules = sum(1 for rule in serialized_rules if rule.review_status == "rejected")
    needs_adjustment_rules = sum(1 for rule in serialized_rules if rule.review_status == "needs_adjustment")
    pending_records = suggestion_query.filter(
        models.MappingSuggestionRecord.status.in_(["auto_acceptable", "review_required"]),
    ).all()
    rejected_false_positives = suggestion_query.filter(
        models.MappingSuggestionRecord.status == "rejected",
    ).count()

    ambiguity: dict[str, int] = {}
    for suggestion in pending_records:
        source_schema = suggestion.source_schema or "unknown"
        ambiguity[source_schema] = ambiguity.get(source_schema, 0) + 1

    ambiguous_sources = [
        AmbiguousSourceMetric(source_schema=source_schema, pending_suggestions=count)
        for source_schema, count in sorted(ambiguity.items(), key=lambda item: item[1], reverse=True)[:5]
    ]

    return GovernanceMetricsResponse(
        active_rules=active_rules,
        inactive_rules=inactive_rules,
        approved_rules=approved_rules,
        pending_rules=pending_rules,
        rejected_rules=rejected_rules,
        needs_adjustment_rules=needs_adjustment_rules,
        pending_suggestions=len(pending_records),
        rejected_false_positives=rejected_false_positives,
        ambiguous_sources=ambiguous_sources,
    )


@router.post(
    "/field-correspondence-rules/preventive-seed",
    response_model=PreventiveRuleSeedResponse,
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def seed_preventive_field_correspondence_rules(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Load inactive preventive correspondence candidates for admin validation."""
    from backend.tenant_access import resolve_request_org_id
    from datetime import datetime, timezone

    org_id = resolve_request_org_id(db, current_user)
    candidates = _preventive_rule_candidates()
    created = 0
    updated = 0
    touched: list[models.FieldCorrespondenceRule] = []
    now = datetime.now(timezone.utc)
    for candidate in candidates:
        rule = db.query(models.FieldCorrespondenceRule).filter(
            models.FieldCorrespondenceRule.org_id == org_id,
            models.FieldCorrespondenceRule.source_schema == candidate["source_schema"],
            models.FieldCorrespondenceRule.source_field == candidate["source_field"],
        ).first()
        if rule:
            updated += 1
            before = _dump_rule(rule)
        else:
            created += 1
            before = None
            rule = models.FieldCorrespondenceRule(
                org_id=org_id,
                source_schema=candidate["source_schema"],
                source_field=candidate["source_field"],
                created_by_id=getattr(current_user, "id", None),
                created_at=now,
            )
            db.add(rule)

        rule.canonical_target = candidate["canonical_target"]
        rule.semantic_concept = candidate["semantic_concept"]
        rule.identifier_scheme = candidate["identifier_scheme"]
        rule.confidence = 0.55
        rule.evidence = json.dumps(["preventive_candidate_rule"], ensure_ascii=False)
        if before is None:
            rule.is_active = False
        rule.updated_at = now
        db.flush()
        _audit_rule_change(
            db,
            action="PREVENTIVE_SEED_UPDATE" if before else "PREVENTIVE_SEED_CREATE",
            rule=rule,
            current_user=current_user,
            before=before,
        )
        touched.append(rule)

    db.commit()
    for rule in touched:
        db.refresh(rule)

    return PreventiveRuleSeedResponse(
        created=created,
        updated=updated,
        total_candidates=len(candidates),
        rules=[_serialize_rule(rule) for rule in touched[:25]],
    )


@router.get(
    "/field-correspondence-rules/jobs",
    response_model=list[FieldCorrespondenceJobResponse],
    dependencies=[Depends(get_current_user)],
)
def list_field_correspondence_jobs(
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List production executions of field correspondence rules."""
    from backend.tenant_access import resolve_request_org_id

    org_id = resolve_request_org_id(db, current_user)
    query = db.query(models.HarmonizationLog).filter(
        models.HarmonizationLog.step_id.like("field_correspondence_rule:%"),
    )
    if org_id is None:
        query = query.filter(models.HarmonizationLog.org_id.is_(None))
    else:
        query = query.filter(models.HarmonizationLog.org_id == org_id)
    logs = query.order_by(models.HarmonizationLog.id.desc()).limit(limit).all()
    return [_serialize_field_correspondence_job(log) for log in logs]


@router.get(
    "/field-correspondence-rules/review-export.csv",
    dependencies=[Depends(get_current_user)],
)
def export_field_correspondence_review_csv(
    active: bool | None = Query(default=None),
    source_schema: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Export rule review data as CSV for offline governance review."""
    from backend.tenant_access import resolve_request_org_id

    org_id = resolve_request_org_id(db, current_user)
    query = db.query(models.FieldCorrespondenceRule)
    if org_id is None:
        query = query.filter(models.FieldCorrespondenceRule.org_id.is_(None))
    else:
        query = query.filter(models.FieldCorrespondenceRule.org_id == org_id)
    if active is not None:
        query = query.filter(models.FieldCorrespondenceRule.is_active.is_(active))
    if source_schema:
        query = query.filter(models.FieldCorrespondenceRule.source_schema == source_schema)
    rules = query.order_by(models.FieldCorrespondenceRule.id.desc()).limit(limit).all()

    rows = ["rule_id,source_schema,source_field,canonical_target,identifier_scheme,is_active,review_status"]
    for rule in rules:
        serialized = _serialize_rule(rule)
        rows.append(",".join([
            str(rule.id),
            (rule.source_schema or "").replace(",", " "),
            rule.source_field.replace(",", " "),
            (rule.canonical_target or "").replace(",", " "),
            (rule.identifier_scheme or "").replace(",", " "),
            str(bool(rule.is_active)).lower(),
            serialized.review_status,
        ]))
    return Response(
        content="\n".join(rows) + "\n",
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=field-correspondence-review.csv"},
    )


@router.post(
    "/field-correspondence-rules/jobs/{job_id}/rollback",
    response_model=FieldCorrespondenceRollbackResponse,
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def rollback_field_correspondence_job(
    job_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Rollback a production field correspondence execution."""
    from backend.tenant_access import resolve_request_org_id
    from datetime import datetime, timezone

    org_id = resolve_request_org_id(db, current_user)
    log = db.get(models.HarmonizationLog, job_id)
    if not log or not (log.step_id or "").startswith("field_correspondence_rule:"):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if log.org_id != org_id:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if log.reverted:
        raise HTTPException(status_code=400, detail="This job has already been rolled back")

    changes = db.query(models.HarmonizationChangeRecord).filter(
        models.HarmonizationChangeRecord.log_id == job_id,
    ).all()
    if not changes and (log.records_updated or 0) > 0:
        raise HTTPException(status_code=400, detail="No change records found for rollback")

    restored = 0
    for change in changes:
        entity = db.get(models.RawEntity, change.record_id)
        if not entity or entity.org_id != org_id:
            continue
        setattr(entity, change.field, change.old_value)
        entity.updated_at = datetime.now(timezone.utc)
        restored += 1

    log.reverted = True
    db.add(models.AuditLog(
        action="ROLLBACK",
        entity_type="field_correspondence_job",
        entity_id=log.id,
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", None),
        details=json.dumps({
            "job_id": log.id,
            "step_id": log.step_id,
            "records_restored": restored,
        }, ensure_ascii=False, default=str),
    ))
    db.commit()

    return FieldCorrespondenceRollbackResponse(job_id=job_id, records_restored=restored, reverted=True)


@router.post(
    "/field-correspondence-rules/impact",
    response_model=FieldCorrespondenceImpactResponse,
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def preview_field_correspondence_rule_impact(
    payload: FieldCorrespondenceRulePayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Preview existing records and suggestions affected by a proposed rule."""
    from backend.tenant_access import resolve_request_org_id

    org_id = resolve_request_org_id(db, current_user)
    source_field = payload.source_field.strip()
    source_schema = payload.source_schema.strip() if payload.source_schema else None
    canonical_target = payload.canonical_target.strip() if payload.canonical_target else None

    suggestion_query = db.query(models.MappingSuggestionRecord).filter(
        models.MappingSuggestionRecord.source_field == source_field,
    )
    if org_id is None:
        suggestion_query = suggestion_query.filter(models.MappingSuggestionRecord.org_id.is_(None))
    else:
        suggestion_query = suggestion_query.filter(models.MappingSuggestionRecord.org_id == org_id)
    if source_schema:
        suggestion_query = suggestion_query.filter(models.MappingSuggestionRecord.source_schema == source_schema)
    matching_suggestions = suggestion_query.count()

    candidates = _rule_candidate_query(db, org_id=org_id, source_field=source_field)

    affected_records = 0
    affected_import_batches: set[int] = set()
    examples: list[FieldCorrespondenceImpactExample] = []
    for entity in candidates.limit(5000).all():
        location, current_value = _extract_rule_value(
            entity,
            source_field=source_field,
            source_schema=source_schema,
            canonical_target=canonical_target,
        )
        if not location:
            continue

        affected_records += 1
        if entity.import_batch_id is not None:
            affected_import_batches.add(entity.import_batch_id)
        if len(examples) < 5:
            examples.append(FieldCorrespondenceImpactExample(
                entity_id=entity.id,
                primary_label=entity.primary_label,
                import_batch_id=entity.import_batch_id,
                source_field=source_field,
                current_value=str(current_value) if current_value is not None else None,
                location=location,
            ))

    return FieldCorrespondenceImpactResponse(
        source_schema=source_schema,
        source_field=source_field,
        canonical_target=canonical_target,
        affected_records=affected_records,
        affected_import_batches=len(affected_import_batches),
        matching_suggestions=matching_suggestions,
        examples=examples,
    )


@router.post(
    "/field-correspondence-rules/{rule_id}/apply",
    response_model=FieldCorrespondenceApplyResponse,
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def apply_field_correspondence_rule(
    payload: FieldCorrespondenceApplyPayload,
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Dry-run or apply an approved rule to existing imported records."""
    from backend.tenant_access import resolve_request_org_id
    from datetime import datetime, timezone

    org_id = resolve_request_org_id(db, current_user)
    rule = db.get(models.FieldCorrespondenceRule, rule_id)
    if not rule or rule.org_id != org_id:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    if not rule.is_active:
        raise HTTPException(status_code=409, detail="Only active rules can be applied")
    if not rule.canonical_target or not hasattr(models.RawEntity, rule.canonical_target):
        raise HTTPException(status_code=422, detail="Rule target is not an entity field")

    candidates = _rule_candidate_query(db, org_id=org_id, source_field=rule.source_field)
    affected_records = 0
    affected_import_batches: set[int] = set()
    examples: list[FieldCorrespondenceImpactExample] = []
    updated_records = 0
    skipped_existing = 0
    skipped_missing_value = 0
    changes: list[dict] = []

    for entity in candidates.limit(payload.limit).all():
        location, current_value = _extract_rule_value(
            entity,
            source_field=rule.source_field,
            source_schema=rule.source_schema,
            canonical_target=rule.canonical_target,
        )
        if not location:
            continue
        affected_records += 1
        if entity.import_batch_id is not None:
            affected_import_batches.add(entity.import_batch_id)

        existing_value = getattr(entity, rule.canonical_target)
        if current_value is None or str(current_value).strip() == "":
            skipped_missing_value += 1
        elif existing_value not in (None, "") and not payload.overwrite_existing:
            skipped_existing += 1
        else:
            if not payload.dry_run:
                changes.append({
                    "record_id": entity.id,
                    "field": rule.canonical_target,
                    "old_value": existing_value,
                    "new_value": str(current_value),
                })
                setattr(entity, rule.canonical_target, str(current_value))
                entity.updated_at = datetime.now(timezone.utc)
            updated_records += 1

        if len(examples) < 5:
            examples.append(FieldCorrespondenceImpactExample(
                entity_id=entity.id,
                primary_label=entity.primary_label,
                import_batch_id=entity.import_batch_id,
                source_field=rule.source_field,
                current_value=str(current_value) if current_value is not None else None,
                location=location,
            ))

    job_id: int | None = None
    if not payload.dry_run:
        rule_label = f"{rule.source_schema or '*'}:{rule.source_field}->{rule.canonical_target}"
        log = models.HarmonizationLog(
            org_id=org_id,
            step_id=f"field_correspondence_rule:{rule.id}",
            step_name="Field correspondence apply",
            records_updated=len(changes),
            fields_modified=json.dumps([rule.canonical_target], ensure_ascii=False),
            executed_at=datetime.now(timezone.utc),
            details=json.dumps({
                "rule_id": rule.id,
                "rule_label": rule_label,
                "username": getattr(current_user, "username", None),
                "affected_records": affected_records,
                "updated_records": updated_records,
                "skipped_existing": skipped_existing,
                "skipped_missing_value": skipped_missing_value,
                "overwrite_existing": payload.overwrite_existing,
            }, ensure_ascii=False, default=str),
            reverted=False,
        )
        db.add(log)
        db.flush()
        job_id = log.id
        for change in changes:
            db.add(models.HarmonizationChangeRecord(
                log_id=log.id,
                record_id=change["record_id"],
                field=change["field"],
                old_value=change["old_value"],
                new_value=change["new_value"],
            ))
        db.add(models.AuditLog(
            action="APPLY",
            entity_type="field_correspondence_rule",
            entity_id=rule.id,
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "username", None),
            details=json.dumps({
                "rule": _dump_rule(rule),
                "dry_run": False,
                "overwrite_existing": payload.overwrite_existing,
                "affected_records": affected_records,
                "updated_records": updated_records,
                "skipped_existing": skipped_existing,
                "skipped_missing_value": skipped_missing_value,
                "job_id": job_id,
            }, ensure_ascii=False, default=str),
        ))
        db.commit()

    return FieldCorrespondenceApplyResponse(
        source_schema=rule.source_schema,
        source_field=rule.source_field,
        canonical_target=rule.canonical_target,
        affected_records=affected_records,
        affected_import_batches=len(affected_import_batches),
        matching_suggestions=db.query(models.MappingSuggestionRecord).filter(
            models.MappingSuggestionRecord.org_id.is_(None) if org_id is None else models.MappingSuggestionRecord.org_id == org_id,
            models.MappingSuggestionRecord.source_field == rule.source_field,
            models.MappingSuggestionRecord.source_schema == rule.source_schema,
        ).count(),
        examples=examples,
        dry_run=payload.dry_run,
        overwrite_existing=payload.overwrite_existing,
        job_id=job_id,
        updated_records=updated_records,
        skipped_existing=skipped_existing,
        skipped_missing_value=skipped_missing_value,
    )


@router.post(
    "/field-correspondence-rules/{rule_id}/review-status",
    response_model=FieldCorrespondenceRuleResponse,
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def set_field_correspondence_review_status(
    payload: FieldCorrespondenceReviewPayload,
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Mark an admin review decision without losing rule history."""
    from backend.tenant_access import resolve_request_org_id
    from datetime import datetime, timezone

    org_id = resolve_request_org_id(db, current_user)
    rule = db.get(models.FieldCorrespondenceRule, rule_id)
    if not rule or rule.org_id != org_id:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

    before = _dump_rule(rule)
    evidence = [item for item in _json_list(rule.evidence) if item not in {"rejected_admin_review", "needs_adjustment"}]
    if payload.review_status == "approved":
        rule.is_active = True
    elif payload.review_status == "pending":
        rule.is_active = False
    elif payload.review_status == "rejected":
        rule.is_active = False
        evidence.append("rejected_admin_review")
    elif payload.review_status == "needs_adjustment":
        rule.is_active = False
        evidence.append("needs_adjustment")
    rule.evidence = json.dumps(evidence or ["manual_admin_rule"], ensure_ascii=False)
    rule.updated_at = datetime.now(timezone.utc)
    db.flush()
    _audit_rule_change(db, action="REVIEW_STATUS", rule=rule, current_user=current_user, before=before)
    db.commit()
    db.refresh(rule)
    return _serialize_rule(rule)
