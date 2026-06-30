"""
Sprint 108+ — Catalog Portals (US-071A)
  GET    /catalogs
  POST   /catalogs
  GET    /catalogs/{slug}
  PUT    /catalogs/{slug}
  GET    /catalogs/{slug}/results
  GET    /catalogs/{slug}/records/{entity_id}
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query as SAQuery, Session

from backend import models, schemas
from backend.auth import get_current_user, get_current_user_optional, require_role
from backend.database import get_db
from backend.schema_registry import registry
from backend.services.entity_service import EntityService
from backend.tenant_access import persisted_org_id, resolve_request_org_id, scope_query_to_org

router = APIRouter(tags=["catalogs"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,118}[a-z0-9]$")
_ALLOWED_SORTS = {"id", "quality_score", "primary_label", "enrichment_status"}
_ALLOWED_ORDERS = {"asc", "desc"}
_ALLOWED_FACETS = {
    "entity_type",
    "domain",
    "validation_status",
    "enrichment_status",
    "source",
    "journal_metric_signal",
}
_JOURNAL_NIF_BAYES_READY = "nif_bayes_ready"
_PORTAL_FACETS_DEFAULT = tuple(schemas.CATALOG_PORTAL_FACETS_DEFAULT)


def _normalize_featured_facets(fields: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for field in fields or []:
        if field == "domain":
            continue
        if field in _ALLOWED_FACETS and field not in normalized:
            normalized.append(field)
    if "journal_metric_signal" not in normalized:
        normalized.append("journal_metric_signal")
    return normalized or list(_PORTAL_FACETS_DEFAULT)


def _parse_json(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _normalize_slug(slug: str) -> str:
    normalized = slug.strip().lower()
    if not _SLUG_RE.match(normalized):
        raise HTTPException(
            status_code=422,
            detail="slug must be 3-120 lowercase alphanumeric characters or hyphens",
        )
    return normalized


def _ensure_domain_exists(domain_id: str) -> None:
    if not registry.get_domain(domain_id):
        raise HTTPException(status_code=422, detail="Unknown domain")


def _portal_query_defaults(portal: models.CatalogPortal) -> dict[str, Any]:
    defaults = _parse_json(portal.query_json, {})
    if not isinstance(defaults, dict):
        defaults = {}
    return {
        "search": defaults.get("search"),
        "min_quality": defaults.get("min_quality"),
        "ft_entity_type": defaults.get("ft_entity_type"),
        "ft_validation_status": defaults.get("ft_validation_status"),
        "ft_enrichment_status": defaults.get("ft_enrichment_status"),
        "ft_source": defaults.get("ft_source"),
        "ft_journal_metric_signal": defaults.get("ft_journal_metric_signal"),
        "sort_by": defaults.get("sort_by") or portal.default_sort or "primary_label",
        "order": defaults.get("order") or "asc",
    }


def _serialize_portal(portal: models.CatalogPortal) -> dict[str, Any]:
    defaults = _portal_query_defaults(portal)
    return {
        "id": portal.id,
        "org_id": portal.org_id,
        "source_batch_id": portal.source_batch_id,
        "title": portal.title,
        "slug": portal.slug,
        "description": portal.description,
        "domain_id": portal.domain_id,
        "visibility": portal.visibility,
        "source_label": portal.source_label,
        "source_context": _parse_json(portal.source_context_json, {}),
        "search": defaults["search"],
        "min_quality": defaults["min_quality"],
        "ft_entity_type": defaults["ft_entity_type"],
        "ft_validation_status": defaults["ft_validation_status"],
        "ft_enrichment_status": defaults["ft_enrichment_status"],
        "ft_source": defaults["ft_source"],
        "default_sort": defaults["sort_by"],
        "default_order": defaults["order"],
        "featured_facets": _parse_json(portal.featured_facets_json, []),
        "created_by": portal.created_by,
        "created_at": portal.created_at,
        "updated_at": portal.updated_at,
    }


def _serialize_import_batch(batch: models.ImportBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "org_id": batch.org_id,
        "domain_id": batch.domain_id,
        "source_type": batch.source_type,
        "file_name": batch.file_name,
        "file_format": batch.file_format,
        "source_label": batch.source_label,
        "total_rows": batch.total_rows,
        "entity_type_hint": batch.entity_type_hint,
        "created_by": batch.created_by,
        "created_at": batch.created_at,
    }


def _get_scoped_portal_or_404(db: Session, slug: str, org_id: int | None) -> models.CatalogPortal:
    query = scope_query_to_org(db.query(models.CatalogPortal), models.CatalogPortal, org_id)
    portal = query.filter(models.CatalogPortal.slug == slug).first()
    if not portal:
        raise HTTPException(status_code=404, detail="Catalog portal not found")
    return portal


def _get_scoped_import_batch_or_404(db: Session, batch_id: int, org_id: int | None) -> models.ImportBatch:
    query = scope_query_to_org(db.query(models.ImportBatch), models.ImportBatch, org_id)
    batch = query.filter(models.ImportBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return batch


def _get_public_portal_or_404(db: Session, slug: str) -> models.CatalogPortal:
    portal = (
        db.query(models.CatalogPortal)
        .filter(
            models.CatalogPortal.slug == slug,
            models.CatalogPortal.visibility == "public",
        )
        .first()
    )
    if not portal:
        raise HTTPException(status_code=404, detail="Catalog portal not found")
    return portal


def _resolve_portal_access(
    db: Session,
    slug: str,
    current_user: models.User | None,
) -> tuple[models.CatalogPortal, int | None]:
    if current_user is not None:
        user_org_id = resolve_request_org_id(db, current_user)
        scoped_portal = (
            scope_query_to_org(db.query(models.CatalogPortal), models.CatalogPortal, user_org_id)
            .filter(models.CatalogPortal.slug == slug)
            .first()
        )
        if scoped_portal:
            return scoped_portal, user_org_id

    public_portal = _get_public_portal_or_404(db, slug)
    return public_portal, public_portal.org_id


def _apply_entity_filters(
    query: SAQuery,
    *,
    search: str | None,
    min_quality: float | None,
    ft_entity_type: str | None,
    ft_validation_status: str | None,
    ft_enrichment_status: str | None,
    ft_source: str | None,
    ft_journal_metric_signal: str | None = None,
    org_id: int | None = None,
) -> SAQuery:
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                models.RawEntity.primary_label.ilike(search_filter),
                models.RawEntity.canonical_id.ilike(search_filter),
                models.RawEntity.secondary_label.ilike(search_filter),
                models.RawEntity.entity_type.ilike(search_filter),
            )
        )
    if min_quality is not None:
        query = query.filter(models.RawEntity.quality_score >= min_quality)
    if ft_entity_type:
        query = query.filter(models.RawEntity.entity_type == ft_entity_type)
    if ft_validation_status:
        query = query.filter(models.RawEntity.validation_status == ft_validation_status)
    if ft_enrichment_status:
        query = query.filter(models.RawEntity.enrichment_status == ft_enrichment_status)
    if ft_source:
        query = query.filter(models.RawEntity.source == ft_source)
    if ft_journal_metric_signal == _JOURNAL_NIF_BAYES_READY:
        query = query.join(
            models.JournalMetric,
            and_(
                models.RawEntity.enrichment_issn_l == models.JournalMetric.issn_l,
                models.JournalMetric.org_id == org_id,
                models.JournalMetric.normalized_impact_factor.isnot(None),
                models.JournalMetric.nif_bayes.isnot(None),
            ),
        )
    return query


def _resolve_filters(
    portal: models.CatalogPortal,
    *,
    search: str | None,
    min_quality: float | None,
    ft_entity_type: str | None,
    ft_validation_status: str | None,
    ft_enrichment_status: str | None,
    ft_source: str | None,
    ft_journal_metric_signal: str | None,
    sort_by: str | None,
    order: str | None,
) -> dict[str, Any]:
    defaults = _portal_query_defaults(portal)
    resolved = {
        "search": search if search is not None else defaults["search"],
        "min_quality": min_quality if min_quality is not None else defaults["min_quality"],
        "ft_entity_type": ft_entity_type if ft_entity_type is not None else defaults["ft_entity_type"],
        "ft_validation_status": ft_validation_status if ft_validation_status is not None else defaults["ft_validation_status"],
        "ft_enrichment_status": ft_enrichment_status if ft_enrichment_status is not None else defaults["ft_enrichment_status"],
        "ft_source": ft_source if ft_source is not None else defaults["ft_source"],
        "ft_journal_metric_signal": (
            ft_journal_metric_signal
            if ft_journal_metric_signal == _JOURNAL_NIF_BAYES_READY
            else None
        ),
        "sort_by": sort_by if sort_by is not None else defaults["sort_by"],
        "order": order if order is not None else defaults["order"],
    }
    if resolved["sort_by"] not in _ALLOWED_SORTS:
        resolved["sort_by"] = "primary_label"
    if resolved["order"] not in _ALLOWED_ORDERS:
        resolved["order"] = "asc"
    return resolved


def _portal_entity_query(
    db: Session,
    portal: models.CatalogPortal,
    org_id: int | None,
    *,
    search: str | None,
    min_quality: float | None,
    ft_entity_type: str | None,
    ft_validation_status: str | None,
    ft_enrichment_status: str | None,
    ft_source: str | None,
    ft_journal_metric_signal: str | None = None,
) -> SAQuery:
    query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
    if portal.source_batch_id:
        query = query.filter(models.RawEntity.import_batch_id == portal.source_batch_id)
    else:
        query = query.filter(models.RawEntity.domain == portal.domain_id)
    query = _apply_entity_filters(
        query,
        search=search,
        min_quality=min_quality,
        ft_entity_type=ft_entity_type,
        ft_validation_status=ft_validation_status,
        ft_enrichment_status=ft_enrichment_status,
        ft_source=ft_source,
        ft_journal_metric_signal=ft_journal_metric_signal,
        org_id=org_id,
    )
    return query


@router.get("/catalogs", response_model=list[schemas.CatalogPortalResponse])
def list_catalog_portals(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    portals = (
        scope_query_to_org(db.query(models.CatalogPortal), models.CatalogPortal, org_id)
        .order_by(models.CatalogPortal.created_at.desc(), models.CatalogPortal.id.desc())
        .all()
    )
    return [_serialize_portal(portal) for portal in portals]


@router.get("/catalogs/import-candidates")
def list_catalog_import_candidates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    candidates: list[dict[str, Any]] = []

    batches = (
        scope_query_to_org(db.query(models.ImportBatch), models.ImportBatch, org_id)
        .order_by(models.ImportBatch.created_at.desc(), models.ImportBatch.id.desc())
        .limit(12)
        .all()
    )
    for batch in batches:
        candidates.append(
            {
                "kind": "batch",
                "batch_id": batch.id,
                "domain_id": batch.domain_id,
                "source": batch.source_type,
                "entity_type": batch.entity_type_hint,
                "total_records": batch.total_rows,
                "avg_quality": None,
                "source_label": batch.source_label or batch.file_name or f"Batch #{batch.id}",
                "search": None,
                "min_quality": None,
                "ft_source": None,
                "ft_entity_type": batch.entity_type_hint,
                "created_at": batch.created_at,
                "file_format": batch.file_format,
            }
        )

    rows = (
        scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
        .filter(models.RawEntity.import_batch_id.is_(None))
        .with_entities(
            models.RawEntity.domain.label("domain_id"),
            models.RawEntity.source.label("source"),
            models.RawEntity.entity_type.label("entity_type"),
            func.count(models.RawEntity.id).label("total_records"),
            func.avg(models.RawEntity.quality_score).label("avg_quality"),
        )
        .group_by(
            models.RawEntity.domain,
            models.RawEntity.source,
            models.RawEntity.entity_type,
        )
        .order_by(
            func.count(models.RawEntity.id).desc(),
            models.RawEntity.domain.asc(),
            models.RawEntity.source.asc(),
        )
        .limit(max(0, 12 - len(candidates)))
        .all()
    )
    for row in rows:
        domain_id = row.domain_id or "default"
        source = row.source or "user"
        entity_type = row.entity_type
        source_label = f"{domain_id} · {source}"
        if entity_type:
            source_label = f"{source_label} · {entity_type}"
        candidates.append(
            {
                "kind": "legacy_scope",
                "batch_id": None,
                "domain_id": domain_id,
                "source": source,
                "entity_type": entity_type,
                "total_records": int(row.total_records or 0),
                "avg_quality": round(float(row.avg_quality), 3) if row.avg_quality is not None else None,
                "source_label": source_label,
                "search": None,
                "min_quality": None,
                "ft_source": source,
                "ft_entity_type": entity_type,
            }
        )
    return candidates


@router.get("/catalogs/import-batches", response_model=list[schemas.ImportBatchResponse])
def list_import_batches(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    batches = (
        scope_query_to_org(db.query(models.ImportBatch), models.ImportBatch, org_id)
        .order_by(models.ImportBatch.created_at.desc(), models.ImportBatch.id.desc())
        .all()
    )
    return [_serialize_import_batch(batch) for batch in batches]


@router.post("/catalogs", response_model=schemas.CatalogPortalResponse, status_code=201)
def create_catalog_portal(
    payload: schemas.CatalogPortalCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    _ensure_domain_exists(payload.domain_id)
    normalized_slug = _normalize_slug(payload.slug)
    if db.query(models.CatalogPortal).filter(models.CatalogPortal.slug == normalized_slug).first():
        raise HTTPException(status_code=409, detail="Catalog portal slug already exists")
    source_batch_id = None
    if payload.source_batch_id is not None:
        batch = _get_scoped_import_batch_or_404(db, payload.source_batch_id, org_id)
        if batch.domain_id != payload.domain_id:
            raise HTTPException(status_code=422, detail="Import batch domain does not match portal domain")
        source_batch_id = batch.id

    featured_facets = _normalize_featured_facets(payload.featured_facets)
    query_json = json.dumps(
        {
            "search": payload.search,
            "min_quality": payload.min_quality,
            "ft_entity_type": payload.ft_entity_type,
            "ft_validation_status": payload.ft_validation_status,
            "ft_enrichment_status": payload.ft_enrichment_status,
            "ft_source": payload.ft_source,
            "ft_journal_metric_signal": None,
            "sort_by": payload.default_sort,
            "order": payload.default_order,
        }
    )
    now = datetime.now(timezone.utc)
    portal = models.CatalogPortal(
        org_id=persisted_org_id(org_id),
        source_batch_id=source_batch_id,
        domain_id=payload.domain_id,
        title=payload.title.strip(),
        slug=normalized_slug,
        description=payload.description,
        visibility=payload.visibility,
        source_label=payload.source_label,
        source_context_json=json.dumps(payload.source_context or {}),
        query_json=query_json,
        featured_facets_json=json.dumps(featured_facets),
        default_sort=payload.default_sort,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(portal)
    db.commit()
    db.refresh(portal)
    return _serialize_portal(portal)


@router.get("/catalogs/{slug}", response_model=schemas.CatalogPortalSummaryResponse)
def get_catalog_portal(
    slug: str = Path(..., min_length=3),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
):
    portal, org_id = _resolve_portal_access(db, slug, current_user)
    defaults = _portal_query_defaults(portal)
    query = _portal_entity_query(
        db,
        portal,
        org_id,
        search=defaults["search"],
        min_quality=defaults["min_quality"],
        ft_entity_type=defaults["ft_entity_type"],
        ft_validation_status=defaults["ft_validation_status"],
        ft_enrichment_status=defaults["ft_enrichment_status"],
        ft_source=defaults["ft_source"],
    )
    total_records = query.count()
    enriched_records = query.filter(models.RawEntity.enrichment_status == "completed").count()
    avg_quality = query.with_entities(models.RawEntity.quality_score).all()
    quality_values = [row[0] for row in avg_quality if row[0] is not None]

    data = _serialize_portal(portal)
    data["summary"] = {
        "total_records": total_records,
        "enriched_records": enriched_records,
        "enriched_pct": round((enriched_records / total_records) * 100, 1) if total_records else 0.0,
        "avg_quality": round(sum(quality_values) / len(quality_values), 3) if quality_values else None,
    }
    return data


@router.put("/catalogs/{slug}", response_model=schemas.CatalogPortalResponse)
def update_catalog_portal(
    payload: schemas.CatalogPortalUpdate,
    slug: str = Path(..., min_length=3),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    portal = _get_scoped_portal_or_404(db, slug, org_id)
    defaults = _portal_query_defaults(portal)

    if payload.title is not None:
        portal.title = payload.title.strip()
    if payload.description is not None:
        portal.description = payload.description
    if payload.source_batch_id is not None:
        batch = _get_scoped_import_batch_or_404(db, payload.source_batch_id, org_id)
        if batch.domain_id != portal.domain_id:
            raise HTTPException(status_code=422, detail="Import batch domain does not match portal domain")
        portal.source_batch_id = batch.id
    if payload.visibility is not None:
        portal.visibility = payload.visibility
    if payload.source_label is not None:
        portal.source_label = payload.source_label
    if payload.source_context is not None:
        portal.source_context_json = json.dumps(payload.source_context)
    if payload.default_sort is not None:
        portal.default_sort = payload.default_sort

    if payload.featured_facets is not None:
        portal.featured_facets_json = json.dumps(_normalize_featured_facets(payload.featured_facets))

    query_payload = {
        "search": payload.search if payload.search is not None else defaults["search"],
        "min_quality": payload.min_quality if payload.min_quality is not None else defaults["min_quality"],
        "ft_entity_type": payload.ft_entity_type if payload.ft_entity_type is not None else defaults["ft_entity_type"],
        "ft_validation_status": payload.ft_validation_status if payload.ft_validation_status is not None else defaults["ft_validation_status"],
        "ft_enrichment_status": payload.ft_enrichment_status if payload.ft_enrichment_status is not None else defaults["ft_enrichment_status"],
        "ft_source": payload.ft_source if payload.ft_source is not None else defaults["ft_source"],
        "sort_by": payload.default_sort if payload.default_sort is not None else defaults["sort_by"],
        "order": payload.default_order if payload.default_order is not None else defaults["order"],
    }
    portal.query_json = json.dumps(query_payload)
    portal.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(portal)
    return _serialize_portal(portal)


@router.delete("/catalogs/{slug}", status_code=204)
def delete_catalog_portal(
    slug: str = Path(..., min_length=3),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    portal = _get_scoped_portal_or_404(db, slug, org_id)
    db.delete(portal)
    db.commit()
    return None


@router.get("/catalogs/{slug}/results")
def get_catalog_results(
    slug: str = Path(..., min_length=3),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
    search: str | None = Query(default=None),
    min_quality: float | None = Query(default=None, ge=0.0, le=1.0),
    ft_entity_type: str | None = Query(default=None),
    ft_validation_status: str | None = Query(default=None),
    ft_enrichment_status: str | None = Query(default=None),
    ft_source: str | None = Query(default=None),
    ft_journal_metric_signal: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    order: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
):
    portal, org_id = _resolve_portal_access(db, slug, current_user)
    filters = _resolve_filters(
        portal,
        search=search,
        min_quality=min_quality,
        ft_entity_type=ft_entity_type,
        ft_validation_status=ft_validation_status,
        ft_enrichment_status=ft_enrichment_status,
        ft_source=ft_source,
        ft_journal_metric_signal=ft_journal_metric_signal,
        sort_by=sort_by,
        order=order,
    )

    query = _portal_entity_query(
        db,
        portal,
        org_id,
        search=filters["search"],
        min_quality=filters["min_quality"],
        ft_entity_type=filters["ft_entity_type"],
        ft_validation_status=filters["ft_validation_status"],
        ft_enrichment_status=filters["ft_enrichment_status"],
        ft_source=filters["ft_source"],
        ft_journal_metric_signal=filters["ft_journal_metric_signal"],
    )
    sort_col = {
        "id": models.RawEntity.id,
        "quality_score": models.RawEntity.quality_score,
        "primary_label": models.RawEntity.primary_label,
        "enrichment_status": models.RawEntity.enrichment_status,
    }[filters["sort_by"]]
    query = query.order_by(sort_col.desc() if filters["order"] == "desc" else sort_col.asc())
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    EntityService.attach_journal_metrics(db, items, org_id)

    featured_facets = _normalize_featured_facets(_parse_json(portal.featured_facets_json, []))
    facet_fields = ",".join(featured_facets)
    facets = EntityService.get_facets(
        db,
        facet_fields,
        search=filters["search"],
        min_quality=filters["min_quality"],
        import_batch_id=portal.source_batch_id,
        ft_entity_type=filters["ft_entity_type"],
        ft_domain=None if portal.source_batch_id else portal.domain_id,
        ft_validation_status=filters["ft_validation_status"],
        ft_enrichment_status=filters["ft_enrichment_status"],
        ft_source=filters["ft_source"],
        ft_journal_metric_signal=filters["ft_journal_metric_signal"],
        org_id=org_id,
    )

    return {
        "portal": _serialize_portal(portal),
        "filters": {**filters, "domain_id": portal.domain_id},
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [schemas.Entity.model_validate(item).model_dump() for item in items],
        "facets": facets,
    }


@router.get("/catalogs/{slug}/records/{entity_id}", response_model=schemas.Entity)
def get_catalog_record(
    slug: str = Path(..., min_length=3),
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
):
    portal, org_id = _resolve_portal_access(db, slug, current_user)
    defaults = _portal_query_defaults(portal)
    record = (
        _portal_entity_query(
            db,
            portal,
            org_id,
            search=None,
            min_quality=defaults["min_quality"],
            ft_entity_type=defaults["ft_entity_type"],
            ft_validation_status=defaults["ft_validation_status"],
            ft_enrichment_status=defaults["ft_enrichment_status"],
            ft_source=defaults["ft_source"],
        )
        .filter(models.RawEntity.id == entity_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Catalog record not found")
    EntityService.attach_journal_metrics(db, [record], org_id)
    return record
