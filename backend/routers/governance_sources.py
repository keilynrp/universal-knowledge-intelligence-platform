"""
Governance API — Source Profiling, Mapping Suggestions, Readiness & Export.
  POST /sources/profile
  GET  /sources/{source_id}/profile
  GET  /sources/{source_id}/candidates
  GET  /mapping-suggestions
  POST /mapping-suggestions/bulk/{action}
  POST /mapping-suggestions/{suggestion_id}/accept
  POST /mapping-suggestions/{suggestion_id}/reject
  GET  /governance/authority-readiness/{dataset_id}
  GET  /exports/{entity_id}/jsonld
"""
import logging
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
