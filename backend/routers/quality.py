"""
Sprint 72 — Entity Quality Score endpoints.
  POST /entities/quality/compute   — bulk compute + persist (admin+)
  GET  /entities/{entity_id}/quality — single entity breakdown
"""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from backend import database, models, schemas
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.notifications.emit import emit_outbound
from backend.quality_scorer import (
    compute_all,
    compute_one,
    domain_quality_averages,
    quality_low_crossings,
    quality_low_threshold,
)

router = APIRouter(tags=["quality"])


@router.post("/entities/quality/compute", status_code=200)
def bulk_compute_quality(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Recompute and persist quality_score for every entity in the catalog."""
    before = domain_quality_averages(db)
    count = compute_all(db)
    after = domain_quality_averages(db)
    for crossing in quality_low_crossings(before, after, quality_low_threshold()):
        emit_outbound("quality.low", crossing, database.SessionLocal)
    return {"computed": count, "message": f"Quality scores updated for {count} entities."}


@router.get("/entities/{entity_id}/quality", response_model=schemas.QualityBreakdown)
def get_entity_quality(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Return live quality score + dimension breakdown for a single entity."""
    entity = db.query(models.UniversalEntity).filter(
        models.UniversalEntity.id == entity_id
    ).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    result = compute_one(entity, db)
    return schemas.QualityBreakdown(
        entity_id=entity_id,
        score=result["score"],
        stored_score=entity.quality_score,
        breakdown=result["breakdown"],
    )
