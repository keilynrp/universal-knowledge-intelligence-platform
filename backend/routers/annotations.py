"""
Collaborative Annotations endpoints (Sprint 42).
  GET    /annotations           — list by entity_id or authority_id
  POST   /annotations           — create (editor+)
  GET    /annotations/{id}      — single annotation
  PUT    /annotations/{id}      — update content (editor+, own or admin+)
  DELETE /annotations/{id}      — delete (editor+, own or admin+)
"""
from __future__ import annotations

import json as _json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.tenant_access import (
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_or_404(ann_id: int, db: Session, org_id: int | None) -> models.Annotation:
    ann = get_scoped_record(db, models.Annotation, ann_id, org_id)
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
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    q = scope_query_to_org(db.query(models.Annotation), models.Annotation, org_id)
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
    # entity_id / authority_id are soft references (not enforced FKs), so we do
    # not assert their existence here. Tenant isolation is guaranteed by stamping
    # the annotation with the caller's org and filtering every read by org_id:
    # an annotation created in org A is never visible to org B regardless of which
    # entity_id it points at.
    org_id = resolve_request_org_id(db, current_user)
    ann = models.Annotation(
        org_id=persisted_org_id(org_id),
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


# ── GET /annotations/stats/{entity_id} ────────────────────────────────────────
# NOTE: must be registered BEFORE /annotations/{ann_id} to avoid route shadowing

@router.get("/annotations/stats/{entity_id}", tags=["annotations"])
def annotation_stats(
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Thread statistics for an entity: total / resolved / unresolved top-level threads."""
    org_id = resolve_request_org_id(db, current_user)
    threads = (
        scope_query_to_org(db.query(models.Annotation), models.Annotation, org_id)
        .filter(
            models.Annotation.entity_id == entity_id,
            models.Annotation.parent_id.is_(None),
        )
        .all()
    )
    total = len(threads)
    resolved = sum(1 for t in threads if t.is_resolved)
    total_reactions = sum(
        sum(len(v) for v in _json.loads(t.emoji_reactions or "{}").values())
        for t in threads
    )
    return {
        "entity_id": entity_id,
        "total_threads": total,
        "resolved_threads": resolved,
        "unresolved_threads": total - resolved,
        "total_reactions": total_reactions,
    }


# ── GET /annotations/{id} ─────────────────────────────────────────────────────

@router.get("/annotations/{ann_id}", tags=["annotations"])
def get_annotation(
    ann_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    return schemas.AnnotationResponse.model_validate(_get_or_404(ann_id, db, org_id))


# ── PUT /annotations/{id} ─────────────────────────────────────────────────────

@router.put("/annotations/{ann_id}", tags=["annotations"])
def update_annotation(
    ann_id: int,
    payload: schemas.AnnotationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    ann = _get_or_404(ann_id, db, org_id)
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
    org_id = resolve_request_org_id(db, current_user)
    ann = _get_or_404(ann_id, db, org_id)
    _check_ownership(ann, current_user)
    db.delete(ann)
    db.commit()
    logger.info("Annotation %d deleted by %s", ann_id, current_user.username)
    return {"deleted": ann_id}


# ── POST /annotations/{id}/resolve ────────────────────────────────────────────

@router.post("/annotations/{ann_id}/resolve", tags=["annotations"])
def toggle_resolve(
    ann_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Toggle the resolved state of a top-level annotation thread."""
    org_id = resolve_request_org_id(db, current_user)
    ann = _get_or_404(ann_id, db, org_id)
    if ann.parent_id is not None:
        raise HTTPException(status_code=400, detail="Only top-level annotations can be resolved")
    ann.is_resolved = not ann.is_resolved
    if ann.is_resolved:
        ann.resolved_at = datetime.now(timezone.utc)
        ann.resolved_by_id = current_user.id
    else:
        ann.resolved_at = None
        ann.resolved_by_id = None
    db.commit()
    db.refresh(ann)
    logger.info("Annotation %d resolved=%s by %s", ann_id, ann.is_resolved, current_user.username)
    return schemas.AnnotationResponse.model_validate(ann)


# ── POST /annotations/{id}/react ──────────────────────────────────────────────

_ALLOWED_REACTIONS = {"👍", "❤️", "🚀", "👀", "✅", "😄", "🎉"}


@router.post("/annotations/{ann_id}/react", tags=["annotations"])
def react_to_annotation(
    ann_id: int,
    emoji: str = Query(..., description="Emoji character, e.g. 👍"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Add or remove an emoji reaction (toggle).
    Pass ?emoji=👍 (URL-encoded) as a query param.
    Allowed: 👍 ❤️ 🚀 👀 ✅ 😄 🎉
    """
    if emoji not in _ALLOWED_REACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Emoji '{emoji}' not allowed. Use: {sorted(_ALLOWED_REACTIONS)}",
        )
    org_id = resolve_request_org_id(db, current_user)
    ann = _get_or_404(ann_id, db, org_id)
    try:
        reactions: dict = _json.loads(ann.emoji_reactions or "{}")
    except Exception:
        reactions = {}
    users = reactions.get(emoji, [])
    if current_user.id in users:
        users.remove(current_user.id)   # toggle off
    else:
        users.append(current_user.id)   # toggle on
    if users:
        reactions[emoji] = users
    else:
        reactions.pop(emoji, None)
    ann.emoji_reactions = _json.dumps(reactions, ensure_ascii=False)
    db.commit()
    db.refresh(ann)
    return schemas.AnnotationResponse.model_validate(ann)
