"""
Governance API — Field Correspondence Rules CRUD.
  GET    /field-correspondence-rules
  POST   /field-correspondence-rules
  PATCH  /field-correspondence-rules/{rule_id}
  POST   /field-correspondence-rules/{rule_id}/deactivate
  POST   /field-correspondence-rules/{rule_id}/reactivate
  GET    /field-correspondence-rules/evidence-scores
  GET    /field-correspondence-rules/{rule_id}/audit
"""
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend import models

logger = logging.getLogger(__name__)

router = APIRouter(tags=["governance"])


# ── Pydantic models ──────────────────────────────────────────────────────────

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
    review_status: str = "pending"
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


class FieldCorrespondenceEvidenceScore(BaseModel):
    rule_id: int
    score: str
    validation_status: str
    collision_count: int = 0
    affected_records: int
    matching_suggestions: int
    sample_values: list[str] = Field(default_factory=list)


class FieldCorrespondenceAuditEntry(BaseModel):
    id: int
    action: str
    username: str | None = None
    created_at: str | None = None
    before: dict | None = None
    after: dict | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    evidence = _json_list(rule.evidence)
    review_status = "approved" if rule.is_active else "pending"
    if "rejected_admin_review" in evidence:
        review_status = "rejected"
    elif "needs_adjustment" in evidence:
        review_status = "needs_adjustment"
    return FieldCorrespondenceRuleResponse(
        id=rule.id,
        source_schema=rule.source_schema,
        source_field=rule.source_field,
        canonical_target=rule.canonical_target,
        semantic_concept=rule.semantic_concept,
        identifier_scheme=rule.identifier_scheme,
        confidence=rule.confidence or 0.0,
        evidence=evidence,
        is_active=bool(rule.is_active),
        review_status=review_status,
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


def _evidence_level(affected_records: int, matching_suggestions: int) -> str:
    if affected_records >= 10 or matching_suggestions >= 3:
        return "high"
    if affected_records >= 3 or matching_suggestions >= 1:
        return "medium"
    if affected_records >= 1:
        return "low"
    return "none"


def _validate_identifier_value(identifier_scheme: str | None, value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not identifier_scheme:
        return bool(text)
    if identifier_scheme == "doi":
        return bool(re.match(r"^10\.\d{4,9}/\S+$", text, flags=re.IGNORECASE))
    if identifier_scheme == "orcid":
        return bool(re.match(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", text, flags=re.IGNORECASE))
    if identifier_scheme == "ror":
        return bool(re.match(r"^(https://ror\.org/)?0[a-z0-9]{6}\d{2}$", text, flags=re.IGNORECASE))
    return bool(text)


def _collision_count_for_rule(
    db: Session,
    *,
    org_id: int | None,
    rule: models.FieldCorrespondenceRule,
) -> int:
    from backend.routers.governance_field_correspondence_ops import (
        _extract_rule_value,
        _rule_candidate_query,
    )

    if not rule.canonical_target or not hasattr(models.RawEntity, rule.canonical_target):
        return 0
    collisions = 0
    candidates = _rule_candidate_query(db, org_id=org_id, source_field=rule.source_field)
    for entity in candidates.limit(500).all():
        location, current_value = _extract_rule_value(
            entity,
            source_field=rule.source_field,
            source_schema=rule.source_schema,
            canonical_target=rule.canonical_target,
        )
        if not location or current_value is None:
            continue
        existing_value = getattr(entity, rule.canonical_target)
        if existing_value not in (None, "") and str(existing_value) != str(current_value):
            collisions += 1
    return collisions


# ── Endpoints ─────────────────────────────────────────────────────────────────

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


@router.get(
    "/field-correspondence-rules/evidence-scores",
    response_model=list[FieldCorrespondenceEvidenceScore],
    dependencies=[Depends(get_current_user)],
)
def score_field_correspondence_rule_evidence(
    active: bool | None = Query(default=None),
    source_schema: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Score visible rules against real records/suggestions so admins can prioritize review."""
    from backend.tenant_access import resolve_request_org_id
    from backend.routers.governance_field_correspondence_ops import (
        _extract_rule_value,
        _rule_candidate_query,
    )

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
    scores: list[FieldCorrespondenceEvidenceScore] = []
    for rule in rules:
        suggestion_query = db.query(models.MappingSuggestionRecord).filter(
            models.MappingSuggestionRecord.source_field == rule.source_field,
        )
        if org_id is None:
            suggestion_query = suggestion_query.filter(models.MappingSuggestionRecord.org_id.is_(None))
        else:
            suggestion_query = suggestion_query.filter(models.MappingSuggestionRecord.org_id == org_id)
        if rule.source_schema:
            suggestion_query = suggestion_query.filter(models.MappingSuggestionRecord.source_schema == rule.source_schema)
        matching_suggestions = suggestion_query.count()

        affected_records = 0
        sample_values: list[str] = []
        valid_samples = 0
        candidates = _rule_candidate_query(db, org_id=org_id, source_field=rule.source_field)
        for entity in candidates.limit(500).all():
            location, current_value = _extract_rule_value(
                entity,
                source_field=rule.source_field,
                source_schema=rule.source_schema,
                canonical_target=rule.canonical_target,
            )
            if not location:
                continue
            affected_records += 1
            if current_value is not None and len(sample_values) < 3:
                value = str(current_value)
                if value not in sample_values:
                    sample_values.append(value)
            if _validate_identifier_value(rule.identifier_scheme, current_value):
                valid_samples += 1

        validation_status = "not_applicable"
        if rule.canonical_target == "canonical_id":
            if affected_records == 0:
                validation_status = "unknown"
            elif valid_samples == affected_records:
                validation_status = "valid"
            elif valid_samples > 0:
                validation_status = "mixed"
            else:
                validation_status = "invalid"
        collision_count = _collision_count_for_rule(db, org_id=org_id, rule=rule)

        scores.append(FieldCorrespondenceEvidenceScore(
            rule_id=rule.id,
            score=_evidence_level(affected_records, matching_suggestions),
            validation_status=validation_status,
            collision_count=collision_count,
            affected_records=affected_records,
            matching_suggestions=matching_suggestions,
            sample_values=sample_values,
        ))
    return scores


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
