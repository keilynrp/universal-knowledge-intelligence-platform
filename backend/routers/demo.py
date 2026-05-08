"""
Demo Mode endpoints.
  GET    /demo/status  — check if demo data is loaded
  POST   /demo/seed    — load pre-generated demo entities (admin+)
  DELETE /demo/reset   — remove demo entities (admin+)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.tenant_access import persisted_org_id, resolve_request_org_id

logger = logging.getLogger(__name__)

router = APIRouter()

# Relative to project root (where the process is started from)
_DEMO_FILE = Path("data/demo/demo_entities.xlsx")

_SEED_CHUNK = 500
_DEMO_BATCH_SOURCE_TYPE = "demo"
_DEMO_BATCH_SOURCE_LABEL = "UKIP Demo Dataset"
_DEMO_PORTAL_SLUG = "ukip-demo-catalog"
_DEMO_PORTAL_TITLE = "Portal demo UKIP"
_DEMO_PORTAL_DESCRIPTION = (
    "Portal de descubrimiento generado automáticamente desde la demo UKIP "
    "para explorar 1,000 entidades pregeneradas."
)

_CURRENT_FIELD_MAP = {
    "primary_label":             "primary_label",
    "secondary_label":           "secondary_label",
    "canonical_id":              "canonical_id",
    "entity_type":               "entity_type",
    "domain":                    "domain",
    "validation_status":         "validation_status",
    "enrichment_status":         "enrichment_status",
    "enrichment_citation_count": "enrichment_citation_count",
    "enrichment_concepts":       "enrichment_concepts",
    "enrichment_source":         "enrichment_source",
    "enrichment_doi":            "enrichment_doi",
}

_LEGACY_FALLBACKS = {
    "primary_label": "entity_name",
    "secondary_label": "brand_capitalized",
    "canonical_id": "sku",
}

_LEGACY_ATTRIBUTE_COLUMNS = ("brand_lower", "classification", "creation_date", "status")


def _demo_count(db: Session) -> int:
    return db.query(models.RawEntity).filter(models.RawEntity.source == "demo").count()


def _demo_file_name() -> str:
    name = getattr(_DEMO_FILE, "name", None)
    return name if isinstance(name, str) else "demo_entities.xlsx"


def _demo_portal(db: Session) -> models.CatalogPortal | None:
    return (
        db.query(models.CatalogPortal)
        .filter(models.CatalogPortal.source_label == _DEMO_BATCH_SOURCE_LABEL)
        .order_by(models.CatalogPortal.created_at.desc(), models.CatalogPortal.id.desc())
        .first()
    )


def _demo_status_payload(db: Session) -> dict:
    count = _demo_count(db)
    portal = _demo_portal(db)
    return {
        "demo_seeded": count > 0,
        "demo_entity_count": count,
        "catalog_portal": (
            {
                "title": portal.title,
                "slug": portal.slug,
                "url": f"/catalogs/{portal.slug}",
            }
            if portal
            else None
        ),
    }


def _is_present(value: object) -> bool:
    return value is not None and not pd.isna(value)


def _normalize_domain(raw_value: object) -> str:
    if not _is_present(raw_value):
        return "default"
    return str(raw_value).strip().lower() or "default"


def _row_to_raw_entity_kwargs(row: dict) -> dict:
    kwargs: dict = {"source": "demo"}

    for df_col, model_field in _CURRENT_FIELD_MAP.items():
        value = row.get(df_col)
        if _is_present(value):
            kwargs[model_field] = value

    for model_field, legacy_column in _LEGACY_FALLBACKS.items():
        if model_field not in kwargs:
            value = row.get(legacy_column)
            if _is_present(value):
                kwargs[model_field] = value

    if "domain" not in kwargs:
        kwargs["domain"] = _normalize_domain(row.get("entity_type"))

    legacy_attributes = {
        key: row.get(key)
        for key in _LEGACY_ATTRIBUTE_COLUMNS
        if _is_present(row.get(key))
    }
    if legacy_attributes:
        kwargs["attributes_json"] = json.dumps(legacy_attributes)

    # Any remaining columns that are not known model fields go into
    # normalized_json so the disambiguation engine can find them.
    _known = (
        set(_CURRENT_FIELD_MAP.keys())
        | set(_LEGACY_FALLBACKS.values())
        | set(_LEGACY_ATTRIBUTE_COLUMNS)
        | {"entity_name", "brand_capitalized", "sku"}  # legacy label columns
    )
    extra = {k: str(v) for k, v in row.items() if k not in _known and _is_present(v)}
    if extra:
        kwargs["normalized_json"] = json.dumps(extra, ensure_ascii=False)

    return kwargs


def _ensure_unique_demo_slug(db: Session) -> str:
    if not db.query(models.CatalogPortal).filter(models.CatalogPortal.slug == _DEMO_PORTAL_SLUG).first():
        return _DEMO_PORTAL_SLUG

    suffix = 2
    while True:
        candidate = f"{_DEMO_PORTAL_SLUG}-{suffix}"
        if not db.query(models.CatalogPortal).filter(models.CatalogPortal.slug == candidate).first():
            return candidate
        suffix += 1


def _create_demo_batch_and_portal(
    db: Session,
    *,
    current_user: models.User,
    total_rows: int,
) -> tuple[models.ImportBatch, models.CatalogPortal]:
    org_id = resolve_request_org_id(db, current_user)
    now = datetime.now(timezone.utc)
    batch = models.ImportBatch(
        org_id=persisted_org_id(org_id),
        domain_id="science",
        source_type=_DEMO_BATCH_SOURCE_TYPE,
        file_name=_demo_file_name(),
        file_format="xlsx",
        source_label=_DEMO_BATCH_SOURCE_LABEL,
        total_rows=total_rows,
        entity_type_hint=None,
        created_by=current_user.id,
        created_at=now,
    )
    db.add(batch)
    db.flush()

    portal = models.CatalogPortal(
        org_id=persisted_org_id(org_id),
        source_batch_id=batch.id,
        domain_id=batch.domain_id,
        title=_DEMO_PORTAL_TITLE,
        slug=_ensure_unique_demo_slug(db),
        description=_DEMO_PORTAL_DESCRIPTION,
        visibility="org",
        source_label=_DEMO_BATCH_SOURCE_LABEL,
        source_context_json=json.dumps(
            {
                "kind": "demo_seed",
                "file": _demo_file_name(),
                "rows": total_rows,
                "provider": "UKIP demo",
            }
        ),
        query_json=json.dumps(
            {
                "search": None,
                "min_quality": None,
                "ft_entity_type": None,
                "ft_validation_status": None,
                "ft_enrichment_status": None,
                "ft_source": None,
                "sort_by": "primary_label",
                "order": "asc",
            }
        ),
        featured_facets_json=json.dumps(["entity_type", "enrichment_status", "source"]),
        default_sort="primary_label",
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(portal)
    db.flush()
    return batch, portal


# ── GET /demo/status ──────────────────────────────────────────────────────────

@router.get("/demo/status", tags=["demo"])
def demo_status(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    return _demo_status_payload(db)


# ── POST /demo/seed ───────────────────────────────────────────────────────────

@router.post("/demo/seed", status_code=201, tags=["demo"])
def demo_seed(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Load the pre-generated demo dataset into the database."""
    if not _DEMO_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Demo file not found at {_DEMO_FILE}. Run scripts/generate_demo_dataset.py first.",
        )

    if _demo_count(db) > 0:
        raise HTTPException(
            status_code=409,
            detail="Demo data already seeded. Call DELETE /demo/reset first.",
        )

    try:
        df = pd.read_excel(_DEMO_FILE)
    except Exception as exc:
        logger.exception("Failed to read demo Excel file")
        raise HTTPException(status_code=500, detail=f"Failed to read demo file: {exc}") from exc

    rows = df.to_dict(orient="records")
    batch, portal = _create_demo_batch_and_portal(db, current_user=current_user, total_rows=len(rows))
    seeded = 0
    chunk: list[models.RawEntity] = []
    for row in rows:
        entity_kwargs = _row_to_raw_entity_kwargs(row)
        entity_kwargs["import_batch_id"] = batch.id
        entity_kwargs["org_id"] = batch.org_id
        chunk.append(models.RawEntity(**entity_kwargs))
        if len(chunk) >= _SEED_CHUNK:
            db.add_all(chunk)
            db.commit()
            seeded += len(chunk)
            chunk = []

    if chunk:
        db.add_all(chunk)
        db.commit()
        seeded += len(chunk)

    logger.info("Demo seed: %d entities inserted", seeded)
    return {
        "seeded": seeded,
        "message": f"Demo dataset loaded: {seeded} entities ready.",
        "catalog_portal": {
            "title": portal.title,
            "slug": portal.slug,
            "url": f"/catalogs/{portal.slug}",
        },
    }


# ── DELETE /demo/reset ────────────────────────────────────────────────────────

@router.delete("/demo/reset", tags=["demo"])
def demo_reset(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Remove all demo entities without touching user-imported data."""
    demo_batch_ids = [
        row[0]
        for row in db.query(models.ImportBatch.id)
        .filter(models.ImportBatch.source_type == _DEMO_BATCH_SOURCE_TYPE)
        .all()
    ]
    if demo_batch_ids:
        (
            db.query(models.CatalogPortal)
            .filter(models.CatalogPortal.source_batch_id.in_(demo_batch_ids))
            .delete(synchronize_session=False)
        )
    (
        db.query(models.CatalogPortal)
        .filter(models.CatalogPortal.source_label == _DEMO_BATCH_SOURCE_LABEL)
        .delete(synchronize_session=False)
    )
    deleted = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.source == "demo")
        .delete(synchronize_session=False)
    )
    if demo_batch_ids:
        (
            db.query(models.ImportBatch)
            .filter(models.ImportBatch.id.in_(demo_batch_ids))
            .delete(synchronize_session=False)
        )
    db.commit()
    logger.info("Demo reset: %d entities deleted", deleted)
    return {"deleted": deleted}
