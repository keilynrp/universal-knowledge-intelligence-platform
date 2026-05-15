"""
Sprint 80 — Custom Dashboard Builder: per-user dashboard CRUD.

Provides:
  GET    /dashboards               — list caller's dashboards
  POST   /dashboards               — create a dashboard (201)
  GET    /dashboards/{id}          — get single
  PUT    /dashboards/{id}          — update name / layout
  DELETE /dashboards/{id}          — delete
  POST   /dashboards/{id}/default  — set as caller's default dashboard
  GET    /dashboards/widget-types  — catalogue of available widget types
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user
from backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboards"])

# ── Widget type catalogue ─────────────────────────────────────────────────────
#
# These are the valid widget type identifiers the frontend can use.
# Each entry describes what the widget shows and its default dimensions (cols).

WIDGET_CATALOGUE = [
    {
        "type":        "entity_kpi",
        "label":       "Entity KPIs",
        "description": "Total entities, enriched %, avg quality score",
        "default_cols": 4,
        "icon":        "chart-bar",
    },
    {
        "type":        "enrichment_coverage",
        "label":       "Enrichment Coverage",
        "description": "Donut chart showing enrichment status breakdown",
        "default_cols": 4,
        "icon":        "beaker",
    },
    {
        "type":        "top_entities",
        "label":       "Top Entities",
        "description": "Table of highest-quality entities in the domain",
        "default_cols": 8,
        "icon":        "table-cells",
    },
    {
        "type":        "top_brands",
        "label":       "Top Brands / Values",
        "description": "Bar chart of most frequent field values",
        "default_cols": 6,
        "icon":        "tag",
    },
    {
        "type":        "concept_cloud",
        "label":       "Coocurrencia temática",
        "description": "Mapa de áreas con pares de keywords depurados por similitud léxica",
        "default_cols": 6,
        "icon":        "sparkles",
    },
    {
        "type":        "recent_activity",
        "label":       "Recent Activity",
        "description": "Latest audit log entries — imports, edits, exports",
        "default_cols": 6,
        "icon":        "clock",
    },
    {
        "type":        "quality_histogram",
        "label":       "Quality Histogram",
        "description": "Distribution of entity quality scores (0–100)",
        "default_cols": 6,
        "icon":        "chart-bar-square",
    },
    {
        "type":        "olap_snapshot",
        "label":       "OLAP Snapshot",
        "description": "Mini pivot table from a saved OLAP query",
        "default_cols": 8,
        "icon":        "cube",
    },
]

_VALID_WIDGET_TYPES = {w["type"] for w in WIDGET_CATALOGUE}


# ── Schemas ───────────────────────────────────────────────────────────────────

class WidgetConfig(BaseModel):
    id:    str                = Field(min_length=1, max_length=64)
    type:  str                = Field(min_length=1, max_length=64)
    title: Optional[str]      = Field(default=None, max_length=200)
    cols:  int                = Field(default=6, ge=1, le=12)
    config: dict[str, Any]   = Field(default_factory=dict)


class DashboardCreate(BaseModel):
    name:   str              = Field(min_length=1, max_length=200)
    layout: List[WidgetConfig] = Field(default_factory=list)


class DashboardUpdate(BaseModel):
    name:   Optional[str]              = Field(default=None, min_length=1, max_length=200)
    layout: Optional[List[WidgetConfig]] = None


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialize(d: models.UserDashboard) -> dict:
    return {
        "id":         d.id,
        "user_id":    d.user_id,
        "name":       d.name,
        "layout":     json.loads(d.layout) if d.layout else [],
        "is_default": d.is_default,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


# ── Widget catalogue endpoint ─────────────────────────────────────────────────

@router.get("/dashboards/widget-types", tags=["dashboards"])
def list_widget_types(_: models.User = Depends(get_current_user)):
    """Return the catalogue of available widget types."""
    return WIDGET_CATALOGUE


# ── CRUD endpoints ────────────────────────────────────────────────────────────

@router.get("/dashboards", tags=["dashboards"])
def list_dashboards(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    items = (
        db.query(models.UserDashboard)
        .filter(models.UserDashboard.user_id == current_user.id)
        .order_by(models.UserDashboard.is_default.desc(), models.UserDashboard.id.desc())
        .all()
    )
    return [_serialize(d) for d in items]


@router.post("/dashboards", status_code=201, tags=["dashboards"])
def create_dashboard(
    payload: DashboardCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Validate widget types
    invalid = [w.type for w in payload.layout if w.type not in _VALID_WIDGET_TYPES]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown widget type(s): {invalid}. Valid: {sorted(_VALID_WIDGET_TYPES)}",
        )

    now = datetime.now(timezone.utc)
    # First dashboard for this user becomes default
    existing_count = (
        db.query(models.UserDashboard)
        .filter(models.UserDashboard.user_id == current_user.id)
        .count()
    )
    d = models.UserDashboard(
        user_id=current_user.id,
        name=payload.name.strip(),
        layout=json.dumps([w.model_dump() for w in payload.layout]),
        is_default=(existing_count == 0),
        created_at=now,
        updated_at=now,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return _serialize(d)


@router.get("/dashboards/{dashboard_id}", tags=["dashboards"])
def get_dashboard(
    dashboard_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    d = db.get(models.UserDashboard, dashboard_id)
    if not d or d.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return _serialize(d)


@router.put("/dashboards/{dashboard_id}", tags=["dashboards"])
def update_dashboard(
    dashboard_id: int = Path(..., ge=1),
    payload: DashboardUpdate = ...,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    d = db.get(models.UserDashboard, dashboard_id)
    if not d or d.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    if payload.name is not None:
        d.name = payload.name.strip()
    if payload.layout is not None:
        invalid = [w.type for w in payload.layout if w.type not in _VALID_WIDGET_TYPES]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown widget type(s): {invalid}",
            )
        d.layout = json.dumps([w.model_dump() for w in payload.layout])
    d.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(d)
    return _serialize(d)


@router.delete("/dashboards/{dashboard_id}", tags=["dashboards"])
def delete_dashboard(
    dashboard_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    d = db.get(models.UserDashboard, dashboard_id)
    if not d or d.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    was_default = d.is_default
    db.delete(d)
    db.commit()
    # Promote the most recent remaining dashboard to default
    if was_default:
        remaining = (
            db.query(models.UserDashboard)
            .filter(models.UserDashboard.user_id == current_user.id)
            .order_by(models.UserDashboard.id.desc())
            .first()
        )
        if remaining:
            remaining.is_default = True
            db.commit()
    return {"deleted": dashboard_id}


@router.post("/dashboards/{dashboard_id}/default", tags=["dashboards"])
def set_default_dashboard(
    dashboard_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Mark this dashboard as the caller's default, clearing any previous default."""
    target = db.get(models.UserDashboard, dashboard_id)
    if not target or target.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    # Clear existing default
    db.query(models.UserDashboard).filter(
        models.UserDashboard.user_id == current_user.id,
        models.UserDashboard.is_default == True,  # noqa: E712
    ).update({"is_default": False})
    target.is_default = True
    db.commit()
    db.refresh(target)
    return _serialize(target)
