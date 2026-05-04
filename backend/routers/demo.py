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

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# Relative to project root (where the process is started from)
_DEMO_FILE = Path("data/demo/demo_entities.xlsx")

_SEED_CHUNK = 500

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


# ── GET /demo/status ──────────────────────────────────────────────────────────

@router.get("/demo/status", tags=["demo"])
def demo_status(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    count = _demo_count(db)
    return {"demo_seeded": count > 0, "demo_entity_count": count}


# ── POST /demo/seed ───────────────────────────────────────────────────────────

@router.post("/demo/seed", status_code=201, tags=["demo"])
def demo_seed(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
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
    seeded = 0
    chunk: list[models.RawEntity] = []
    for row in rows:
        chunk.append(models.RawEntity(**_row_to_raw_entity_kwargs(row)))
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
    return {"seeded": seeded, "message": f"Demo dataset loaded: {seeded} entities ready."}


# ── DELETE /demo/reset ────────────────────────────────────────────────────────

@router.delete("/demo/reset", tags=["demo"])
def demo_reset(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Remove all demo entities without touching user-imported data."""
    deleted = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.source == "demo")
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info("Demo reset: %d entities deleted", deleted)
    return {"deleted": deleted}
