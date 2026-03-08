"""
Demo Mode endpoints.
  GET    /demo/status  — check if demo data is loaded
  POST   /demo/seed    — load pre-generated demo entities (admin+)
  DELETE /demo/reset   — remove demo entities (admin+)
"""
from __future__ import annotations

import logging
import os
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


def _demo_count(db: Session) -> int:
    return db.query(models.RawEntity).filter(models.RawEntity.source == "demo").count()


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

    # Map DataFrame columns → RawEntity fields
    _FIELD_MAP = {
        "entity_name":              "entity_name",
        "brand_capitalized":        "brand_capitalized",
        "classification":           "classification",
        "creation_date":            "creation_date",
        "enrichment_status":        "enrichment_status",
        "enrichment_citation_count": "enrichment_citation_count",
        "enrichment_concepts":      "enrichment_concepts",
        "enrichment_source":        "enrichment_source",
        "sku":                      "sku",
    }

    rows = df.to_dict(orient="records")
    seeded = 0
    chunk: list[models.RawEntity] = []
    for row in rows:
        kwargs: dict = {"source": "demo"}
        for df_col, model_field in _FIELD_MAP.items():
            val = row.get(df_col)
            if val is not None and not (isinstance(val, float) and val != val):  # NaN check
                kwargs[model_field] = val
        chunk.append(models.RawEntity(**kwargs))
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
