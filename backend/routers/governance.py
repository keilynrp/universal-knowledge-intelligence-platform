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


class FieldCorrespondenceRulePayload(BaseModel):
    source_schema: str | None = Field(default=None, max_length=100)
    source_field: str = Field(..., min_length=1, max_length=255)
    canonical_target: str | None = Field(default=None, max_length=100)
    semantic_concept: str | None = Field(default=None, max_length=100)
    identifier_scheme: str | None = Field(default=None, max_length=100)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, max_length=20)


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


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
    else:
        from datetime import datetime, timezone

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

    rule.source_schema = payload.source_schema.strip() if payload.source_schema else None
    rule.source_field = payload.source_field.strip()
    rule.canonical_target = payload.canonical_target.strip() if payload.canonical_target else None
    rule.semantic_concept = payload.semantic_concept.strip() if payload.semantic_concept else None
    rule.identifier_scheme = payload.identifier_scheme.strip() if payload.identifier_scheme else None
    rule.confidence = payload.confidence
    rule.evidence = json.dumps(payload.evidence or ["manual_admin_rule"], ensure_ascii=False)
    rule.updated_at = datetime.now(timezone.utc)
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
    rule.is_active = False
    rule.updated_at = datetime.now(timezone.utc)
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
    rule.is_active = True
    rule.updated_at = datetime.now(timezone.utc)
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
