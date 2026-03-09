"""
Collaborative Annotations endpoints (Sprint 42).
  GET    /annotations           — list by entity_id or authority_id
  POST   /annotations           — create (editor+)
  GET    /annotations/{id}      — single annotation
  PUT    /annotations/{id}      — update content (editor+, own or admin+)
  DELETE /annotations/{id}      — delete (editor+, own or admin+)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import get_current_user, require_role
from backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_or_404(ann_id: int, db: Session) -> models.Annotation:
    ann = db.get(models.Annotation, ann_id)
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return ann


def _check_ownership(ann: models.Annotation, current_user: models.User) -> None:
    """Raise 403 if caller is not the author and not an admin-level user."""
    is_admin = current_user.role in ("super_admin", "admin")
    if ann.author_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="You can only edit your own annotations")


# ── GET /annotations ──────────────────────────────────────────────────────────

@router.get("/annotations", tags=["annotations"])
def list_annotations(
    entity_id:    Optional[int] = Query(None),
    authority_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.Annotation)
    if entity_id is not None:
        q = q.filter(models.Annotation.entity_id == entity_id)
    if authority_id is not None:
        q = q.filter(models.Annotation.authority_id == authority_id)
    annotations = q.order_by(models.Annotation.created_at).all()
    return [schemas.AnnotationResponse.model_validate(a) for a in annotations]


# ── POST /annotations ─────────────────────────────────────────────────────────

@router.post("/annotations", status_code=201, tags=["annotations"])
def create_annotation(
    payload: schemas.AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    if payload.entity_id is None and payload.authority_id is None:
        raise HTTPException(
            status_code=422,
            detail="At least one of entity_id or authority_id must be provided",
        )
    ann = models.Annotation(
        entity_id=payload.entity_id,
        authority_id=payload.authority_id,
        parent_id=payload.parent_id,
        content=payload.content,
        author_id=current_user.id,
        author_name=current_user.username,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    logger.info("Annotation %d created by %s", ann.id, current_user.username)
    return schemas.AnnotationResponse.model_validate(ann)


# ── GET /annotations/{id} ─────────────────────────────────────────────────────

@router.get("/annotations/{ann_id}", tags=["annotations"])
def get_annotation(
    ann_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    return schemas.AnnotationResponse.model_validate(_get_or_404(ann_id, db))


# ── PUT /annotations/{id} ─────────────────────────────────────────────────────

@router.put("/annotations/{ann_id}", tags=["annotations"])
def update_annotation(
    ann_id: int,
    payload: schemas.AnnotationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    ann = _get_or_404(ann_id, db)
    _check_ownership(ann, current_user)
    ann.content = payload.content
    db.commit()
    db.refresh(ann)
    return schemas.AnnotationResponse.model_validate(ann)


# ── DELETE /annotations/{id} ──────────────────────────────────────────────────

@router.delete("/annotations/{ann_id}", tags=["annotations"])
def delete_annotation(
    ann_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    ann = _get_or_404(ann_id, db)
    _check_ownership(ann, current_user)
    db.delete(ann)
    db.commit()
    logger.info("Annotation %d deleted by %s", ann_id, current_user.username)
    return {"deleted": ann_id}
