"""
Governance API endpoints — Priority 1.
  POST /sources/profile
  GET  /sources/{source_id}/profile
  GET  /sources/{source_id}/candidates
  GET  /mapping-suggestions
  POST /mapping-suggestions/{suggestion_id}/accept
  POST /mapping-suggestions/{suggestion_id}/reject
  GET  /authority/readiness/{dataset_id}
  GET  /exports/{entity_id}/jsonld
"""
import logging
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend import models

logger = logging.getLogger(__name__)

router = APIRouter(tags=["governance"])


# ── Source Profiling ──────────────────────────────────────────────────────────

class ProfileRequest(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=200)
    field_names: list[str] = Field(default_factory=list)
    sample_values: dict[str, list] = Field(default_factory=dict)
    payload_type: str = Field(default="csv", pattern=r"^(csv|rest|openalex|crossref)$")


@router.post(
    "/sources/profile",
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "admin", "editor"))],
)
def create_source_profile(payload: ProfileRequest):
    """Profile a data source to infer field types and semantic roles."""
    from backend.services.source_profiler import SourceProfiler

    profiler = SourceProfiler()
    profile = profiler.analyze(
        source_id=payload.source_id,
        field_names=payload.field_names,
        sample_values=payload.sample_values,
        payload_type=payload.payload_type,
    )
    return profile.to_dict()


@router.get(
    "/sources/{source_id}/profile",
    dependencies=[Depends(get_current_user)],
)
def get_source_profile(source_id: str = Path(..., min_length=1)):
    """Get a previously computed source profile."""
    from backend.services.source_profiler import SourceProfiler

    profiler = SourceProfiler()
    profile = profiler.get_profile(source_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No profile found for source '{source_id}'")
    return profile.to_dict()


@router.get(
    "/sources/{source_id}/candidates",
    dependencies=[Depends(get_current_user)],
)
def get_source_candidates(source_id: str = Path(..., min_length=1)):
    """Get semantic candidates extracted from a source profile."""
    from backend.services.source_profiler import SourceProfiler

    profiler = SourceProfiler()
    profile = profiler.get_profile(source_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No profile found for source '{source_id}'")
    return {
        "source_id": source_id,
        "semantic_candidates": profile.semantic_candidates,
        "candidate_identifiers": profile.candidate_identifiers,
    }


# ── Mapping Suggestions ──────────────────────────────────────────────────────

class MappingSuggestionResponse(BaseModel):
    id: int
    source_field: str
    canonical_target: str
    confidence: float
    status: str
    evidence_samples: list[str]
    rationale: str
    semantic_concept: str | None = None
    identifier_scheme: str | None = None
    evidence: list[str] = Field(default_factory=list)
    requires_review: bool = False


class RejectPayload(BaseModel):
    rationale: str = Field(..., min_length=1, max_length=2000)


class BulkSuggestionReviewPayload(BaseModel):
    suggestion_ids: list[int] = Field(..., min_length=1, max_length=100)
    rationale: str | None = Field(default=None, max_length=2000)


class BulkSuggestionReviewResponse(BaseModel):
    action: str
    reviewed: int
    not_found: list[int] = Field(default_factory=list)


class FieldCorrespondenceRuleResponse(BaseModel):
    id: int
    source_schema: str | None = None
    source_field: str
    canonical_target: str | None = None
    semantic_concept: str | None = None
    identifier_scheme: str | None = None
    confidence: float
    evidence: list[str] = Field(default_factory=list)
    is_active: bool
    created_from_suggestion_id: int | None = None
    created_by_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PreventiveRuleSeedResponse(BaseModel):
    created: int
    updated: int
    total_candidates: int
    rules: list[FieldCorrespondenceRuleResponse] = Field(default_factory=list)


class FieldCorrespondenceRulePayload(BaseModel):
    source_schema: str | None = Field(default=None, max_length=100)
    source_field: str = Field(..., min_length=1, max_length=255)
    canonical_target: str | None = Field(default=None, max_length=100)
    semantic_concept: str | None = Field(default=None, max_length=100)
    identifier_scheme: str | None = Field(default=None, max_length=100)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, max_length=20)


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
    pending_suggestions: int
    rejected_false_positives: int
    ambiguous_sources: list[AmbiguousSourceMetric] = Field(default_factory=list)


class FieldCorrespondenceAuditEntry(BaseModel):
    id: int
    action: str
    username: str | None = None
    created_at: str | None = None
    before: dict | None = None
    after: dict | None = None


class FieldCorrespondenceApplyPayload(BaseModel):
    dry_run: bool = True
    overwrite_existing: bool = False
    limit: int = Field(default=5000, ge=1, le=50000)


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


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


def _json_object(value: str | None) -> dict:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _serialize_rule(rule: models.FieldCorrespondenceRule) -> FieldCorrespondenceRuleResponse:
    return FieldCorrespondenceRuleResponse(
        id=rule.id,
        source_schema=rule.source_schema,
        source_field=rule.source_field,
        canonical_target=rule.canonical_target,
        semantic_concept=rule.semantic_concept,
        identifier_scheme=rule.identifier_scheme,
        confidence=rule.confidence or 0.0,
        evidence=_json_list(rule.evidence),
        is_active=bool(rule.is_active),
        created_from_suggestion_id=rule.created_from_suggestion_id,
        created_by_id=rule.created_by_id,
        created_at=rule.created_at.isoformat() if rule.created_at else None,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
    )


def _dump_rule(rule: models.FieldCorrespondenceRule | None) -> dict | None:
    if rule is None:
        return None
    serialized = _serialize_rule(rule)
    if hasattr(serialized, "model_dump"):
        return serialized.model_dump()
    return serialized.dict()


def _audit_rule_change(
    db: Session,
    *,
    action: str,
    rule: models.FieldCorrespondenceRule,
    current_user,
    before: dict | None,
) -> None:
    after = _dump_rule(rule)
    db.add(models.AuditLog(
        action=action,
        entity_type="field_correspondence_rule",
        entity_id=rule.id,
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", None),
        details=json.dumps({"before": before, "after": after}, ensure_ascii=False, default=str),
    ))


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


# Module-level singleton for legacy tests that use the service without DB.
_mapping_service = None


def _get_mapping_service(db: Session | None = None, org_id: int | None = None):
    if db is not None:
        from backend.services.mapping_suggestions import MappingSuggestionService
        return MappingSuggestionService(db=db, org_id=org_id)
    global _mapping_service
    if _mapping_service is None:
        from backend.services.mapping_suggestions import MappingSuggestionService
        _mapping_service = MappingSuggestionService()
    return _mapping_service


@router.get(
    "/mapping-suggestions",
    response_model=list[MappingSuggestionResponse],
)
def list_mapping_suggestions(
    status: Optional[str] = Query(default=None, pattern=r"^(auto_acceptable|review_required|accepted|rejected|superseded)$"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List mapping suggestions, optionally filtered by status."""
    from backend.services.mapping_suggestions import SuggestionStatus
    from backend.tenant_access import resolve_request_org_id

    service = _get_mapping_service(db, org_id=resolve_request_org_id(db, current_user))
    status_enum = SuggestionStatus(status) if status else None
    suggestions = service.list_suggestions(status=status_enum)[:limit]
    return [
        MappingSuggestionResponse(
            id=s.id,
            source_field=s.source_field,
            canonical_target=s.canonical_target,
            confidence=s.confidence,
            status=s.status.value if hasattr(s.status, 'value') else s.status,
            evidence_samples=s.evidence_samples,
            rationale=s.rationale or "",
            semantic_concept=s.semantic_concept,
            identifier_scheme=s.identifier_scheme,
            evidence=s.evidence,
            requires_review=s.requires_review,
        )
        for s in suggestions
    ]


@router.post(
    "/mapping-suggestions/bulk/{action}",
    response_model=BulkSuggestionReviewResponse,
    dependencies=[Depends(require_role("super_admin", "admin", "editor"))],
)
def bulk_review_mapping_suggestions(
    payload: BulkSuggestionReviewPayload,
    action: str = Path(..., pattern=r"^(accept|reject)$"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Accept or reject multiple mapping suggestions in one review action."""
    from backend.tenant_access import resolve_request_org_id

    if action == "reject" and not (payload.rationale or "").strip():
        raise HTTPException(status_code=422, detail="Rationale is required for bulk rejection")

    service = _get_mapping_service(db, org_id=resolve_request_org_id(db, user))
    reviewer_id = user.id if hasattr(user, 'id') else 0
    reviewed = 0
    not_found: list[int] = []
    seen: set[int] = set()
    for suggestion_id in payload.suggestion_ids:
        if suggestion_id in seen:
            continue
        seen.add(suggestion_id)
        if action == "accept":
            suggestion = service.accept_suggestion(suggestion_id, reviewer_id=reviewer_id)
        else:
            suggestion = service.reject_suggestion(
                suggestion_id,
                rationale=(payload.rationale or "").strip(),
                reviewer_id=reviewer_id,
            )
        if suggestion is None:
            not_found.append(suggestion_id)
        else:
            reviewed += 1

    return BulkSuggestionReviewResponse(action=action, reviewed=reviewed, not_found=not_found)


@router.post(
    "/mapping-suggestions/{suggestion_id}/accept",
    dependencies=[Depends(require_role("super_admin", "admin", "editor"))],
)
def accept_mapping_suggestion(
    suggestion_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Accept a mapping suggestion (editor+)."""
    from backend.tenant_access import resolve_request_org_id

    service = _get_mapping_service(db, org_id=resolve_request_org_id(db, user))
    reviewer_id = user.id if hasattr(user, 'id') else 0
    suggestion = service.accept_suggestion(suggestion_id, reviewer_id=reviewer_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail=f"Suggestion '{suggestion_id}' not found")
    return {"status": "accepted", "id": suggestion_id}


@router.post(
    "/mapping-suggestions/{suggestion_id}/reject",
    dependencies=[Depends(require_role("super_admin", "admin", "editor"))],
)
def reject_mapping_suggestion(
    payload: RejectPayload,
    suggestion_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Reject a mapping suggestion with rationale (editor+)."""
    from backend.tenant_access import resolve_request_org_id

    service = _get_mapping_service(db, org_id=resolve_request_org_id(db, user))
    reviewer_id = user.id if hasattr(user, 'id') else 0
    suggestion = service.reject_suggestion(
        suggestion_id,
        rationale=payload.rationale,
        reviewer_id=reviewer_id,
    )
    if suggestion is None:
        raise HTTPException(status_code=404, detail=f"Suggestion '{suggestion_id}' not found")
    return {"status": "rejected", "id": suggestion_id}


# ── Field Correspondence Rules ───────────────────────────────────────────────

@router.get(
    "/field-correspondence-rules",
    response_model=list[FieldCorrespondenceRuleResponse],
    dependencies=[Depends(get_current_user)],
)
def list_field_correspondence_rules(
    source_schema: str | None = Query(default=None, max_length=100),
    active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List governed field correspondence rules for the current tenant."""
    from backend.tenant_access import resolve_request_org_id

    org_id = resolve_request_org_id(db, current_user)
    query = db.query(models.FieldCorrespondenceRule)
    if org_id is None:
        query = query.filter(models.FieldCorrespondenceRule.org_id.is_(None))
    else:
        query = query.filter(models.FieldCorrespondenceRule.org_id == org_id)
    if source_schema:
        query = query.filter(models.FieldCorrespondenceRule.source_schema == source_schema)
    if active is not None:
        query = query.filter(models.FieldCorrespondenceRule.is_active.is_(active))
    rules = query.order_by(models.FieldCorrespondenceRule.id.desc()).limit(limit).all()
    return [_serialize_rule(rule) for rule in rules]


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


@router.get(
    "/field-correspondence-rules/{rule_id}/audit",
    response_model=list[FieldCorrespondenceAuditEntry],
    dependencies=[Depends(get_current_user)],
)
def list_field_correspondence_rule_audit(
    rule_id: int = Path(..., ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return audit history for a governed correspondence rule."""
    from backend.tenant_access import resolve_request_org_id

    org_id = resolve_request_org_id(db, current_user)
    rule = db.get(models.FieldCorrespondenceRule, rule_id)
    if not rule or rule.org_id != org_id:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

    entries = db.query(models.AuditLog).filter(
        models.AuditLog.entity_type == "field_correspondence_rule",
        models.AuditLog.entity_id == rule_id,
    ).order_by(models.AuditLog.id.desc()).limit(limit).all()

    response: list[FieldCorrespondenceAuditEntry] = []
    for entry in entries:
        details = _json_object(entry.details)
        response.append(FieldCorrespondenceAuditEntry(
            id=entry.id,
            action=entry.action or "",
            username=entry.username,
            created_at=entry.created_at.isoformat() if entry.created_at else None,
            before=details.get("before") if isinstance(details.get("before"), dict) else None,
            after=details.get("after") if isinstance(details.get("after"), dict) else None,
        ))
    return response


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
    "/field-correspondence-rules",
    response_model=FieldCorrespondenceRuleResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def create_field_correspondence_rule(
    payload: FieldCorrespondenceRulePayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create or reactivate a governed source-field mapping override."""
    from backend.tenant_access import resolve_request_org_id

    org_id = resolve_request_org_id(db, current_user)
    source_field = payload.source_field.strip()
    source_schema = payload.source_schema.strip() if payload.source_schema else None
    existing = db.query(models.FieldCorrespondenceRule).filter(
        models.FieldCorrespondenceRule.org_id == org_id,
        models.FieldCorrespondenceRule.source_schema == source_schema,
        models.FieldCorrespondenceRule.source_field == source_field,
    ).first()
    if existing:
        rule = existing
        before = _dump_rule(rule)
    else:
        from datetime import datetime, timezone

        before = None
        rule = models.FieldCorrespondenceRule(
            org_id=org_id,
            source_schema=source_schema,
            source_field=source_field,
            created_by_id=getattr(current_user, "id", None),
            created_at=datetime.now(timezone.utc),
        )
        db.add(rule)

    from datetime import datetime, timezone

    rule.canonical_target = payload.canonical_target.strip() if payload.canonical_target else None
    rule.semantic_concept = payload.semantic_concept.strip() if payload.semantic_concept else None
    rule.identifier_scheme = payload.identifier_scheme.strip() if payload.identifier_scheme else None
    rule.confidence = payload.confidence
    rule.evidence = json.dumps(payload.evidence or ["manual_admin_rule"], ensure_ascii=False)
    rule.is_active = True
    rule.updated_at = datetime.now(timezone.utc)
    db.flush()
    _audit_rule_change(
        db,
        action="UPDATE" if before else "CREATE",
        rule=rule,
        current_user=current_user,
        before=before,
    )
    db.commit()
    db.refresh(rule)
    return _serialize_rule(rule)


@router.patch(
    "/field-correspondence-rules/{rule_id}",
    response_model=FieldCorrespondenceRuleResponse,
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def update_field_correspondence_rule(
    payload: FieldCorrespondenceRulePayload,
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a governed correspondence rule."""
    from backend.tenant_access import resolve_request_org_id
    from datetime import datetime, timezone

    org_id = resolve_request_org_id(db, current_user)
    rule = db.get(models.FieldCorrespondenceRule, rule_id)
    if not rule or rule.org_id != org_id:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

    before = _dump_rule(rule)
    rule.source_schema = payload.source_schema.strip() if payload.source_schema else None
    rule.source_field = payload.source_field.strip()
    rule.canonical_target = payload.canonical_target.strip() if payload.canonical_target else None
    rule.semantic_concept = payload.semantic_concept.strip() if payload.semantic_concept else None
    rule.identifier_scheme = payload.identifier_scheme.strip() if payload.identifier_scheme else None
    rule.confidence = payload.confidence
    rule.evidence = json.dumps(payload.evidence or ["manual_admin_rule"], ensure_ascii=False)
    rule.updated_at = datetime.now(timezone.utc)
    db.flush()
    _audit_rule_change(db, action="UPDATE", rule=rule, current_user=current_user, before=before)
    db.commit()
    db.refresh(rule)
    return _serialize_rule(rule)


@router.post(
    "/field-correspondence-rules/{rule_id}/deactivate",
    response_model=FieldCorrespondenceRuleResponse,
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def deactivate_field_correspondence_rule(
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Deactivate a governed correspondence rule without deleting history."""
    from backend.tenant_access import resolve_request_org_id
    from datetime import datetime, timezone

    org_id = resolve_request_org_id(db, current_user)
    rule = db.get(models.FieldCorrespondenceRule, rule_id)
    if not rule or rule.org_id != org_id:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    before = _dump_rule(rule)
    rule.is_active = False
    rule.updated_at = datetime.now(timezone.utc)
    db.flush()
    _audit_rule_change(db, action="DEACTIVATE", rule=rule, current_user=current_user, before=before)
    db.commit()
    db.refresh(rule)
    return _serialize_rule(rule)


@router.post(
    "/field-correspondence-rules/{rule_id}/reactivate",
    response_model=FieldCorrespondenceRuleResponse,
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def reactivate_field_correspondence_rule(
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Reactivate a previously deactivated correspondence rule."""
    from backend.tenant_access import resolve_request_org_id
    from datetime import datetime, timezone

    org_id = resolve_request_org_id(db, current_user)
    rule = db.get(models.FieldCorrespondenceRule, rule_id)
    if not rule or rule.org_id != org_id:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    before = _dump_rule(rule)
    rule.is_active = True
    rule.updated_at = datetime.now(timezone.utc)
    db.flush()
    _audit_rule_change(db, action="REACTIVATE", rule=rule, current_user=current_user, before=before)
    db.commit()
    db.refresh(rule)
    return _serialize_rule(rule)


# ── Authority Readiness ───────────────────────────────────────────────────────

class FamilyCountsResponse(BaseModel):
    extracted: int = 0
    resolved: int = 0
    review_required: int = 0
    rejected: int = 0
    failed: int = 0
    stale: int = 0


class ReadinessResponse(BaseModel):
    dataset_id: str
    state: str
    families: dict[str, FamilyCountsResponse]


@router.get(
    "/governance/authority-readiness/{dataset_id}",
    response_model=ReadinessResponse,
    dependencies=[Depends(get_current_user)],
)
def get_authority_readiness(dataset_id: str = Path(..., min_length=1)):
    """Get authority readiness status for a dataset."""
    from backend.services.authority_readiness import AuthorityReadinessTracker

    tracker = AuthorityReadinessTracker()
    readiness = tracker.get_or_create(dataset_id)
    families = {}
    for family_name, counts in readiness.families.items():
        families[family_name] = FamilyCountsResponse(
            extracted=counts.extracted,
            resolved=counts.resolved,
            review_required=counts.review_required,
            rejected=counts.rejected,
            failed=counts.failed,
            stale=counts.stale,
        )
    return ReadinessResponse(
        dataset_id=dataset_id,
        state=readiness.state,
        families=families,
    )


# ── JSON-LD Export ────────────────────────────────────────────────────────────

@router.get(
    "/exports/{entity_id}/jsonld",
    dependencies=[Depends(get_current_user)],
)
def export_entity_jsonld(
    entity_id: int = Path(..., ge=1),
    vocabulary: str = Query(default="schema_org", pattern=r"^(schema_org|bibframe|edm|dcat)$"),
    db: Session = Depends(get_db),
):
    """Export an entity as JSON-LD aligned to a standard vocabulary."""
    from backend.exporters.jsonld_exporter import JSONLDExporter
    from backend import models

    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    # Build entity dict from DB record
    import json as _json
    attrs = {}
    if entity.attributes_json:
        try:
            attrs = _json.loads(entity.attributes_json) if isinstance(entity.attributes_json, str) else entity.attributes_json
        except (ValueError, TypeError):
            attrs = {}

    entity_data = {
        "id": entity.id,
        "name": entity.name or "",
        "entity_type": attrs.get("entity_type", "Thing"),
        "identifiers": {},
        "attributes": attrs,
    }

    # Extract known identifiers
    for id_field in ("doi", "orcid", "ror_id", "issn", "wikidata_id"):
        val = attrs.get(id_field)
        if val:
            entity_data["identifiers"][id_field] = val

    # Extract authority records if present
    if attrs.get("authority_uri"):
        entity_data["authority_uris"] = [attrs["authority_uri"]]
    if attrs.get("canonical_affiliations"):
        entity_data["affiliations"] = attrs["canonical_affiliations"]

    exporter = JSONLDExporter()
    jsonld = exporter.export_entity(entity_data, vocabulary=vocabulary)
    return jsonld
