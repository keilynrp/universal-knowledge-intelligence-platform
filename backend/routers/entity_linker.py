"""
Entity Linker — detect and resolve potential duplicate entities.

GET    /linker/candidates              → List[LinkCandidateResponse]
POST   /linker/merge                   → merged RawEntity
POST   /linker/dismiss                 → {"ok": True, "id": <dismissal_id>}
GET    /linker/dismissals              → List[DismissalResponse]
DELETE /linker/dismissals/{id}  (204)  → undo dismissal
"""
import logging
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from thefuzz import fuzz

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.routers.deps import _audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/linker", tags=["entity-linker"])

_SCAN_LIMIT = 1_000   # max entities loaded for pairwise scan
_MAX_PAIRS  = 50      # hard cap on returned candidates

# ── Local schemas ─────────────────────────────────────────────────────────────

class EntitySnap(BaseModel):
    id:                int
    entity_name:       Optional[str] = None
    brand_capitalized: Optional[str] = None
    model:             Optional[str] = None
    sku:               Optional[str] = None
    enrichment_status: str
    validation_status: str


class LinkCandidateResponse(BaseModel):
    entity_a:      EntitySnap
    entity_b:      EntitySnap
    score:         float          # 0.0 – 1.0
    matched_fields: List[str]


class MergeRequest(BaseModel):
    winner_id: int = Field(..., description="Entity to keep")
    loser_id:  int = Field(..., description="Entity to absorb then delete")


class DismissRequest(BaseModel):
    entity_a_id: int
    entity_b_id: int


class DismissalResponse(BaseModel):
    id:          int
    entity_a_id: int
    entity_b_id: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _snap(e: models.RawEntity) -> EntitySnap:
    return EntitySnap(
        id=e.id,
        entity_name=e.entity_name,
        brand_capitalized=e.brand_capitalized,
        model=e.model,
        sku=e.sku,
        enrichment_status=e.enrichment_status,
        validation_status=e.validation_status,
    )


def _pair_score(a: models.RawEntity, b: models.RawEntity):
    """Return (score 0–1, matched_fields) for a candidate pair."""
    weights: list = []
    matched: list = []

    if a.entity_name and b.entity_name:
        s = fuzz.token_sort_ratio(a.entity_name, b.entity_name) / 100
        weights.append((s, 0.5))
        if s >= 0.75:
            matched.append("entity_name")

    if a.model and b.model:
        s = fuzz.token_sort_ratio(a.model, b.model) / 100
        weights.append((s, 0.3))
        if s >= 0.75:
            matched.append("model")

    if a.sku and b.sku:
        s = fuzz.ratio(a.sku, b.sku) / 100
        weights.append((s, 0.2))
        if s >= 0.9:
            matched.append("sku")

    if not weights:
        return 0.0, []

    total_w = sum(w for _, w in weights)
    score = sum(s * w for s, w in weights) / total_w
    return round(score, 3), matched


def _dismissed_set(db: Session) -> set:
    rows = db.query(
        models.LinkDismissal.entity_a_id,
        models.LinkDismissal.entity_b_id,
    ).all()
    return {(r.entity_a_id, r.entity_b_id) for r in rows}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/candidates", response_model=List[LinkCandidateResponse])
def get_candidates(
    threshold: float   = Query(default=0.75, ge=0.0, le=1.0),
    limit:     int     = Query(default=20, ge=1, le=_MAX_PAIRS),
    db:        Session = Depends(get_db),
    _:         models.User = Depends(get_current_user),
):
    """Return entity pairs that are likely duplicates (score ≥ threshold)."""
    entities = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.entity_name != None)  # noqa: E711
        .limit(_SCAN_LIMIT)
        .all()
    )
    dismissed = _dismissed_set(db)

    # Brand-based blocking: only compare within same brand group
    buckets: dict = defaultdict(list)
    for e in entities:
        key = (e.brand_capitalized or "").lower().strip() or "_ungrouped"
        buckets[key].append(e)

    candidates = []
    seen: set = set()

    for bucket in buckets.values():
        if len(bucket) < 2:
            continue
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                if len(candidates) >= limit:
                    break
                a, b = bucket[i], bucket[j]
                pair_key = (min(a.id, b.id), max(a.id, b.id))
                if pair_key in seen or pair_key in dismissed:
                    continue
                score, matched = _pair_score(a, b)
                if score >= threshold:
                    seen.add(pair_key)
                    candidates.append(
                        LinkCandidateResponse(
                            entity_a=_snap(a),
                            entity_b=_snap(b),
                            score=score,
                            matched_fields=matched,
                        )
                    )
            if len(candidates) >= limit:
                break

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:limit]


@router.post("/merge")
def merge_entities(
    payload:      MergeRequest,
    db:           Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Merge *loser* into *winner*: fill winner's null fields, then delete loser."""
    if payload.winner_id == payload.loser_id:
        raise HTTPException(status_code=422, detail="winner_id and loser_id must differ")

    winner = db.get(models.RawEntity, payload.winner_id)
    loser  = db.get(models.RawEntity, payload.loser_id)

    if not winner:
        raise HTTPException(status_code=404, detail=f"Entity {payload.winner_id} not found")
    if not loser:
        raise HTTPException(status_code=404, detail=f"Entity {payload.loser_id} not found")

    _FILL_FIELDS = [
        "entity_name", "brand_capitalized", "brand_lower", "model", "sku", "variant",
        "classification", "entity_type", "gtin", "barcode", "unit_of_measure", "measure",
        "enrichment_doi", "enrichment_concepts", "enrichment_source",
    ]
    for field in _FILL_FIELDS:
        if not getattr(winner, field) and getattr(loser, field):
            setattr(winner, field, getattr(loser, field))

    # Adopt enrichment if loser is enriched but winner is not
    if winner.enrichment_status != "completed" and loser.enrichment_status == "completed":
        winner.enrichment_status = loser.enrichment_status
        winner.enrichment_citation_count = loser.enrichment_citation_count

    _audit(db, "MERGE", user_id=current_user.id, entity_type="entity",
           entity_id=winner.id, details={"absorbed": loser.id})

    db.delete(loser)
    db.commit()
    db.refresh(winner)
    return winner


@router.post("/dismiss", status_code=200)
def dismiss_pair(
    payload: DismissRequest,
    db:      Session = Depends(get_db),
    _:       models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Mark an entity pair as 'not a duplicate'. Idempotent."""
    a_id = min(payload.entity_a_id, payload.entity_b_id)
    b_id = max(payload.entity_a_id, payload.entity_b_id)

    existing = db.query(models.LinkDismissal).filter_by(
        entity_a_id=a_id, entity_b_id=b_id
    ).first()
    if existing:
        return {"ok": True, "id": existing.id}

    row = models.LinkDismissal(entity_a_id=a_id, entity_b_id=b_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


@router.get("/dismissals", response_model=List[DismissalResponse])
def list_dismissals(
    db: Session = Depends(get_db),
    _:  models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.LinkDismissal)
        .order_by(models.LinkDismissal.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        DismissalResponse(id=r.id, entity_a_id=r.entity_a_id, entity_b_id=r.entity_b_id)
        for r in rows
    ]


@router.delete("/dismissals/{dismissal_id}", status_code=204)
def undo_dismissal(
    dismissal_id: int     = Path(..., ge=1),
    db:           Session = Depends(get_db),
    _:            models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Remove a dismissal so the pair can surface as a candidate again."""
    row = db.get(models.LinkDismissal, dismissal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Dismissal not found")
    db.delete(row)
    db.commit()
