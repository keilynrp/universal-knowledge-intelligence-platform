"""
Entity CRUD, enrichment, and entity-linker endpoints.
  GET  /entities
  GET  /entities/grouped
  GET  /entities/{entity_id}
  POST /entities/link/find
  POST /entities/link/merge
  POST /entities/link/dismiss
  PUT  /entities/{entity_id}
  DELETE /entities/bulk
  DELETE /entities/all
  DELETE /entities/{entity_id}
  POST /enrich/row/{entity_id}
  POST /enrich/bulk
  POST /enrich/bulk-ids
  GET  /enrich/stats
  GET  /enrich/montecarlo/{entity_id}
"""
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend import database, models, schemas
from backend.analytics.montecarlo import simulate_citation_impact
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend import enrichment_worker
from backend import entity_linker as _entity_linker
from backend.routers.deps import _audit, _dispatch_webhook
from backend.routers.limiter import limiter
from backend.services.entity_service import EntityService

router = APIRouter(tags=["entities"])


# ── Entity list endpoints (must come before wildcard /{entity_id}) ────────────

@router.get("/entities/facets")
def get_entity_facets(
    fields: str = Query(default="entity_type,domain,validation_status,enrichment_status,source"),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """
    Returns value counts for the requested facet fields.
    Response: { field: [{value, count}, ...], ... }
    Unknown fields are silently ignored.
    """
    return EntityService.get_facets(db, fields)


@router.get("/entities", response_model=List[schemas.Entity])
def get_entities(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    search: str = None,
    sort_by: str = Query(default="id", pattern="^(id|quality_score|primary_label|enrichment_status)$"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    min_quality: float = Query(default=None, ge=0.0, le=1.0),
    ft_entity_type:       Optional[str] = Query(default=None),
    ft_domain:            Optional[str] = Query(default=None),
    ft_validation_status: Optional[str] = Query(default=None),
    ft_enrichment_status: Optional[str] = Query(default=None),
    ft_source:            Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    total, entities = EntityService.get_list(
        db=db,
        skip=skip,
        limit=limit,
        search=search,
        sort_by=sort_by,
        order=order,
        min_quality=min_quality,
        ft_entity_type=ft_entity_type,
        ft_domain=ft_domain,
        ft_validation_status=ft_validation_status,
        ft_enrichment_status=ft_enrichment_status,
        ft_source=ft_source,
    )
    response.headers["X-Total-Count"] = str(total)
    return entities


@router.get("/entities/grouped")
def get_entities_grouped(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    search: str = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """
    Group entities by primary_label and show all variants for each entity.
    Similar to OpenRefine's clustering/faceting feature.
    """
    total_groups, results = EntityService.get_grouped(db, skip, limit, search)
    response.headers["X-Total-Count"] = str(total_groups)
    return results


# ── Entity linker (must come before /{entity_id} to avoid shadowing) ──────────

class _LinkFindRequest(BaseModel):
    threshold: float = Field(0.82, ge=0.50, le=0.99)
    limit:     int   = Field(500,  ge=50,   le=2000)


class _LinkMergeRequest(BaseModel):
    primary_id:    int       = Field(..., ge=1)
    secondary_ids: List[int] = Field(..., min_length=1)
    strategy:      str       = Field("keep_non_empty")


class _LinkDismissRequest(BaseModel):
    entity_a_id: int = Field(..., ge=1)
    entity_b_id: int = Field(..., ge=1)


@router.post("/entities/link/find", tags=["entity-linker"])
def link_find(
    payload: _LinkFindRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    dismissed_rows = db.query(models.LinkDismissal).all()
    dismissed_pairs = {(d.entity_a_id, d.entity_b_id) for d in dismissed_rows}
    candidates = _entity_linker.find_candidates(
        db, payload.threshold, payload.limit, dismissed_pairs
    )
    return {
        "candidates": [
            {
                "entity_a":      c.entity_a,
                "entity_b":      c.entity_b,
                "similarity":    c.similarity,
                "common_tokens": c.common_tokens,
            }
            for c in candidates
        ],
        "total":     len(candidates),
        "threshold": payload.threshold,
        "scanned":   payload.limit,
    }


@router.post("/entities/link/merge", tags=["entity-linker"])
def link_merge(
    payload: _LinkMergeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    if payload.primary_id in payload.secondary_ids:
        raise HTTPException(
            status_code=400, detail="primary_id cannot also appear in secondary_ids"
        )
    try:
        merged = _entity_linker.merge_entities(
            db, payload.primary_id, payload.secondary_ids, payload.strategy
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    _audit(
        db, "entity.merge",
        user_id=current_user.id,
        entity_type="entity",
        entity_id=payload.primary_id,
        details={
            "secondary_ids": payload.secondary_ids,
            "strategy":      payload.strategy,
            "deleted":       len(payload.secondary_ids),
        },
    )
    db.commit()
    _dispatch_webhook(
        "entity.merge",
        {"primary_id": payload.primary_id, "deleted": len(payload.secondary_ids)},
        database.SessionLocal,
    )
    return {
        "merged": {
            "id":              merged.id,
            "primary_label":   merged.primary_label,
            "secondary_label": merged.secondary_label,
            "canonical_id":    merged.canonical_id,
            "entity_type":     merged.entity_type,
        },
        "deleted_count": len(payload.secondary_ids),
        "strategy":      payload.strategy,
    }


@router.post("/entities/link/dismiss", tags=["entity-linker"])
def link_dismiss(
    payload: _LinkDismissRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    a_id = min(payload.entity_a_id, payload.entity_b_id)
    b_id = max(payload.entity_a_id, payload.entity_b_id)
    exists = db.query(models.LinkDismissal).filter(
        models.LinkDismissal.entity_a_id == a_id,
        models.LinkDismissal.entity_b_id == b_id,
    ).first()
    if not exists:
        db.add(models.LinkDismissal(entity_a_id=a_id, entity_b_id=b_id))
        db.commit()
    return {"ok": True, "pair": [a_id, b_id]}


# ── Entity CRUD ───────────────────────────────────────────────────────────────

@router.get("/entities/{entity_id}", response_model=schemas.Entity)
def get_entity(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.put("/entities/{entity_id}", response_model=schemas.Entity)
def update_entity(
    entity_id: int = Path(..., ge=1),
    payload: schemas.EntityBase = ...,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entity, field, value)

    _audit(
        db, "entity.update",
        user_id=current_user.id,
        entity_type="entity",
        entity_id=entity_id,
        details={"fields": list(update_data.keys())},
    )
    db.commit()
    db.refresh(entity)
    return entity


class _BulkIdsPayload(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=500)


@router.delete("/entities/bulk", status_code=200)
def delete_entities_bulk(
    payload: _BulkIdsPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Delete a specific list of entities by id."""
    if not payload.ids:
        raise HTTPException(status_code=422, detail="ids list is empty")
    deleted = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.id.in_(payload.ids))
        .delete(synchronize_session=False)
    )
    _audit(
        db, "entity.bulk_delete",
        user_id=current_user.id,
        entity_type="entity",
        details={"ids": payload.ids, "deleted": deleted},
    )
    db.commit()
    return {"deleted": deleted}


class _BulkUpdatePayload(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=500)
    updates: dict = Field(..., description="Fields to update: e.g. {'validation_status': 'confirmed', 'entity_type': 'paper'}")


@router.post("/entities/bulk-update", status_code=200)
def update_entities_bulk(
    payload: _BulkUpdatePayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Batch field updates for a list of entities."""
    if not payload.ids or not payload.updates:
        raise HTTPException(status_code=422, detail="ids and updates are required")
    # Whitelist updatable fields from EntityBase
    allowed_fields = set(schemas.EntityBase.model_fields.keys())
    bad_fields = set(payload.updates.keys()) - allowed_fields
    if bad_fields:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid fields: {', '.join(bad_fields)}. Allowed: {', '.join(sorted(allowed_fields))}",
        )
    updated = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.id.in_(payload.ids))
        .update(payload.updates, synchronize_session=False)
    )
    _audit(
        db, "entity.bulk_update",
        user_id=current_user.id,
        entity_type="entity",
        details={
            "ids": payload.ids[:20],  # limit audit detail size
            "fields": list(payload.updates.keys()),
            "updated": updated,
        },
    )
    db.commit()
    _dispatch_webhook(
        "entity.bulk_update",
        {"count": updated, "fields": list(payload.updates.keys())},
        database.SessionLocal,
    )
    return {"updated": updated, "fields": list(payload.updates.keys())}


@router.delete("/entities/all")
def purge_all_entities(
    include_rules: bool = Query(False),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    entity_count = db.query(func.count(models.RawEntity.id)).scalar() or 0
    db.query(models.RawEntity).delete()

    rules_count = 0
    if include_rules:
        rules_count = db.query(func.count(models.NormalizationRule.id)).scalar() or 0
        db.query(models.NormalizationRule).delete()

    db.commit()
    return {
        "message": "Repository purged successfully",
        "entities_deleted": entity_count,
        "rules_deleted": rules_count,
    }


@router.delete("/entities/{entity_id}")
def delete_entity(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    db.delete(entity)
    _audit(
        db, "entity.delete",
        user_id=current_user.id,
        entity_type="entity",
        entity_id=entity_id,
    )
    db.commit()
    _dispatch_webhook("entity.delete", {"entity_id": entity_id}, database.SessionLocal)
    return {"message": "Entity deleted", "id": entity_id}


# ── Enrichment ────────────────────────────────────────────────────────────────

@router.post("/enrich/row/{entity_id}", response_model=schemas.Entity)
@limiter.limit("30/minute")
def enrich_single_entity(
    request: Request,
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Enriches a single row manually (e.g. from a UI click)."""
    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    enriched = enrichment_worker.enrich_single_record(db, entity)
    return enriched


@router.post("/enrich/bulk")
@limiter.limit("5/minute")
def enrich_bulk_queue(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Queues missing records for background enrichment."""
    count = enrichment_worker.trigger_enrichment_bulk(db, skip=skip, limit=limit)
    return {"message": "Bulk queue triggered", "queued_records": count}


@router.post("/enrich/bulk-ids", status_code=200)
def enrich_bulk_by_ids(
    payload: _BulkIdsPayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Queue a specific list of entities for background enrichment."""
    updated = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.id.in_(payload.ids))
        .update({"enrichment_status": "pending"}, synchronize_session=False)
    )
    db.commit()
    return {"queued": updated}


@router.get("/enrich/stats")
def get_enrichment_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Returns enrichment statistics for the predictive analytics dashboard."""
    total = db.query(func.count(models.RawEntity.id)).scalar() or 0

    status_rows = (
        db.query(models.RawEntity.enrichment_status, func.count(models.RawEntity.id))
        .group_by(models.RawEntity.enrichment_status)
        .all()
    )
    status_breakdown = {row[0] or "none": row[1] for row in status_rows}

    enriched_count = status_breakdown.get("completed", 0)
    pending_count  = status_breakdown.get("pending", 0)
    failed_count   = status_breakdown.get("failed", 0)
    none_count     = status_breakdown.get("none", 0)

    enriched_entities = (
        db.query(models.RawEntity.enrichment_concepts)
        .filter(
            models.RawEntity.enrichment_concepts != None,
            models.RawEntity.enrichment_concepts != "",
        )
        .all()
    )

    concept_freq: dict = {}
    for row in enriched_entities:
        if row[0]:
            for concept in row[0].split(","):
                concept = concept.strip()
                if concept:
                    concept_freq[concept] = concept_freq.get(concept, 0) + 1

    top_concepts = sorted(concept_freq.items(), key=lambda x: x[1], reverse=True)[:20]

    citation_rows = (
        db.query(models.RawEntity.enrichment_citation_count)
        .filter(
            models.RawEntity.enrichment_status == "completed",
            models.RawEntity.enrichment_citation_count != None,
            models.RawEntity.enrichment_citation_count > 0,
        )
        .all()
    )
    citation_values = [r[0] for r in citation_rows if r[0]]

    avg_citations   = round(sum(citation_values) / len(citation_values), 1) if citation_values else 0
    max_citations   = max(citation_values) if citation_values else 0
    total_citations = sum(citation_values)

    buckets = {"0": 0, "1-10": 0, "11-50": 0, "51-200": 0, "200+": 0}
    for v in citation_values:
        if v == 0:
            buckets["0"] += 1
        elif v <= 10:
            buckets["1-10"] += 1
        elif v <= 50:
            buckets["11-50"] += 1
        elif v <= 200:
            buckets["51-200"] += 1
        else:
            buckets["200+"] += 1

    return {
        "total_entities":   total,
        "enriched_count":   enriched_count,
        "pending_count":    pending_count,
        "failed_count":     failed_count,
        "none_count":       none_count,
        "enrichment_coverage_pct": round((enriched_count / total * 100), 1) if total > 0 else 0,
        "top_concepts": [{"concept": c, "count": n} for c, n in top_concepts],
        "citations": {
            "average":      avg_citations,
            "max":          max_citations,
            "total":        total_citations,
            "distribution": buckets,
        },
    }


@router.get("/enrich/montecarlo/{entity_id}")
def get_montecarlo_prediction(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """
    Phase 4: Performs a stochastic Monte Carlo simulation on the future citation trajectory
    of a single enriched entity.
    """
    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    if entity.enrichment_status != "completed":
        raise HTTPException(status_code=400, detail="Cannot predict raw or unenriched data")

    citations = entity.enrichment_citation_count or 0
    predictions = simulate_citation_impact(
        current_citations=citations,
        simulation_years=5,
        num_simulations=5000,
    )
    return predictions
