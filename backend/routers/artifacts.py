"""
Artifact Studio router — Phase 10
Endpoints:
  GET  /artifacts/gaps/{domain_id}   — Knowledge Gap Detector
  GET  /artifacts/templates          — List saved report templates
  POST /artifacts/templates          — Create custom template (editor+)
  DELETE /artifacts/templates/{id}   — Delete template (editor+, non-builtin only)
"""
import json
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.analyzers.gap_detector import GapAnalyzer
from backend.schema_registry import SchemaRegistry
from backend.tenant_access import (
    get_scoped_record,
    org_scope_filter,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)
from backend.schemas import (
    GapItemResponse,
    GapReportResponse,
    ArtifactTemplateCreate,
    ArtifactTemplateResponse,
    VALID_SECTIONS,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/artifacts", tags=["artifacts"])
_registry = SchemaRegistry()
_analyzer = GapAnalyzer()


# ── Knowledge Gap Detector ────────────────────────────────────────────────────

@router.get("/gaps/{domain_id}", response_model=GapReportResponse)
def detect_gaps(
    domain_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    domain = _registry.get_domain(domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")

    gaps = _analyzer.analyze(domain_id, db)

    org_id = resolve_request_org_id(db, current_user)
    total_entities = scope_query_to_org(
        db.query(models.RawEntity), models.RawEntity, org_id
    ).count()
    summary = {
        "critical": sum(1 for g in gaps if g.severity == "critical"),
        "warning":  sum(1 for g in gaps if g.severity == "warning"),
        "ok":       sum(1 for g in gaps if g.severity == "ok"),
        "total_entities": total_entities,
    }

    return GapReportResponse(
        domain_id=domain_id,
        generated_at=datetime.now(timezone.utc),
        summary=summary,
        gaps=[GapItemResponse(**g.__dict__) for g in gaps],
    )


# ── Template helpers ──────────────────────────────────────────────────────────

def _deserialize(tmpl: models.ArtifactTemplate) -> ArtifactTemplateResponse:
    try:
        sections = json.loads(tmpl.sections)
    except (TypeError, ValueError):
        sections = []
    return ArtifactTemplateResponse(
        id=tmpl.id,
        name=tmpl.name,
        description=tmpl.description or "",
        sections=sections,
        default_title=tmpl.default_title or "",
        is_builtin=bool(tmpl.is_builtin),
        created_at=tmpl.created_at,
    )


# ── Template CRUD ─────────────────────────────────────────────────────────────

@router.get("/templates", response_model=List[ArtifactTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    q = db.query(models.ArtifactTemplate)
    # Platform built-ins (org_id NULL) are visible to everyone; tenant-created
    # templates are only visible within their owning organization.
    cond = org_scope_filter(models.ArtifactTemplate.org_id, org_id)
    if cond is not None:
        q = q.filter(or_(models.ArtifactTemplate.is_builtin == True, cond))  # noqa: E712
    rows = q.order_by(
        models.ArtifactTemplate.is_builtin.desc(),
        models.ArtifactTemplate.id,
    ).all()
    return [_deserialize(r) for r in rows]


@router.post("/templates", response_model=ArtifactTemplateResponse, status_code=201)
def create_template(
    payload: ArtifactTemplateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("super_admin", "admin", "editor")),
):
    invalid = [s for s in payload.sections if s not in VALID_SECTIONS]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid section(s): {invalid}. Valid: {sorted(VALID_SECTIONS)}",
        )
    org_id = resolve_request_org_id(db, current_user)
    tmpl = models.ArtifactTemplate(
        org_id=persisted_org_id(org_id),
        name=payload.name,
        description=payload.description,
        sections=json.dumps(payload.sections),
        default_title=payload.default_title,
        is_builtin=False,
        created_by=current_user.id,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return _deserialize(tmpl)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(
    template_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    tmpl = db.get(models.ArtifactTemplate, template_id)
    if tmpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.is_builtin:
        raise HTTPException(status_code=403, detail="Built-in templates cannot be deleted")
    # Custom templates may only be deleted from within their owning organization.
    org_id = resolve_request_org_id(db, current_user)
    scoped = get_scoped_record(db, models.ArtifactTemplate, template_id, org_id)
    if not scoped:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(scoped)
    db.commit()
