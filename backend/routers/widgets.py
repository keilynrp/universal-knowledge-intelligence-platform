"""
Sprint 93 — Widget SDK router.

Authenticated endpoints (CRUD):
  POST   /widgets                    — create widget (admin+)
  GET    /widgets                    — list widgets (viewer+)
  GET    /widgets/{id}               — fetch one (viewer+)
  PUT    /widgets/{id}               — update widget (admin+)
  DELETE /widgets/{id}               — delete widget (admin+)

Public endpoints (no auth — token-gated):
  GET    /embed/{token}/config       — widget metadata (for embed page)
  GET    /embed/{token}/data         — widget data payload
  GET    /embed/{token}/snippet      — HTML iframe + JS embed snippet

Widget types
------------
entity_stats     — total, enriched, enrichment rate, by-domain breakdown
top_concepts     — top N concept tags extracted from enrichment_concepts
recent_entities  — last N ingested entities (label + domain + date)
quality_score    — average quality score + distribution buckets
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.tenant_access import (
    LEGACY_GLOBAL_ORG_ID,
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["widgets"])

_VALID_TYPES = {"entity_stats", "top_concepts", "recent_entities", "quality_score"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class WidgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    widget_type: str = Field(..., pattern="^(entity_stats|top_concepts|recent_entities|quality_score)$")
    config: dict[str, Any] = Field(default_factory=dict)
    allowed_origins: str = Field(default="*", max_length=2000)
    is_active: bool = True


class WidgetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    widget_type: str | None = Field(None, pattern="^(entity_stats|top_concepts|recent_entities|quality_score)$")
    config: dict[str, Any] | None = None
    allowed_origins: str | None = None
    is_active: bool | None = None


def _serialize(w: models.EmbedWidget) -> dict:
    return {
        "id": w.id,
        "name": w.name,
        "widget_type": w.widget_type,
        "config": json.loads(w.config or "{}"),
        "public_token": w.public_token,
        "allowed_origins": w.allowed_origins,
        "is_active": w.is_active,
        "view_count": w.view_count,
        "created_by": w.created_by,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "last_viewed_at": w.last_viewed_at.isoformat() if w.last_viewed_at else None,
    }


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/widgets", status_code=201)
def create_widget(
    payload: WidgetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    w = models.EmbedWidget(
        org_id=persisted_org_id(org_id),
        name=payload.name,
        widget_type=payload.widget_type,
        config=json.dumps(payload.config),
        public_token=str(uuid.uuid4()),
        allowed_origins=payload.allowed_origins,
        is_active=payload.is_active,
        created_by=current_user.id,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return _serialize(w)


@router.get("/widgets")
def list_widgets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    base = scope_query_to_org(db.query(models.EmbedWidget), models.EmbedWidget, org_id)
    total = base.count()
    items = (
        base
        .order_by(models.EmbedWidget.created_at.desc())
        .offset(skip).limit(limit).all()
    )
    return {"total": total, "items": [_serialize(w) for w in items]}


@router.get("/widgets/{widget_id}")
def get_widget(
    widget_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    w = get_scoped_record(db, models.EmbedWidget, widget_id, org_id)
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    return _serialize(w)


@router.put("/widgets/{widget_id}")
def update_widget(
    payload: WidgetUpdate,
    widget_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    w = get_scoped_record(db, models.EmbedWidget, widget_id, org_id)
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    if payload.name is not None:
        w.name = payload.name
    if payload.widget_type is not None:
        w.widget_type = payload.widget_type
    if payload.config is not None:
        w.config = json.dumps(payload.config)
    if payload.allowed_origins is not None:
        w.allowed_origins = payload.allowed_origins
    if payload.is_active is not None:
        w.is_active = payload.is_active
    db.commit()
    db.refresh(w)
    return _serialize(w)


@router.delete("/widgets/{widget_id}")
def delete_widget(
    widget_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    w = get_scoped_record(db, models.EmbedWidget, widget_id, org_id)
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    db.delete(w)
    db.commit()
    return {"deleted": True}


# ── Data providers ────────────────────────────────────────────────────────────

def _configured_domain(cfg: dict) -> str | None:
    value = cfg.get("domain_id") or cfg.get("domain")
    if value is None:
        return None
    domain = str(value).strip()
    return domain or None


def _scoped_entities(db: Session, org_scope: int | None):
    """RawEntity query filtered to the embed widget's owning tenant.

    org_scope is None only for direct/unit callers (no tenant filter); the public
    embed path always passes a concrete scope so tenant data never leaks.
    """
    return scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_scope)


def _data_entity_stats(db: Session, cfg: dict, org_scope: int | None = None) -> dict:
    domain = _configured_domain(cfg)
    q = _scoped_entities(db, org_scope)
    if domain:
        q = q.filter(models.RawEntity.domain == domain)
    total = q.count()
    enriched = q.filter(models.RawEntity.enrichment_status == "completed").count()
    by_domain_query = scope_query_to_org(
        db.query(models.RawEntity.domain, func.count(models.RawEntity.id)),
        models.RawEntity,
        org_scope,
    )
    if domain:
        by_domain_query = by_domain_query.filter(models.RawEntity.domain == domain)
    by_domain = (
        by_domain_query
        .group_by(models.RawEntity.domain)
        .order_by(func.count(models.RawEntity.id).desc())
        .limit(10).all()
    )
    return {
        "total": total,
        "enriched": enriched,
        "enrichment_rate": round(enriched / total * 100, 1) if total else 0,
        "by_domain": [{"domain": d, "count": c} for d, c in by_domain],
    }


def _data_top_concepts(db: Session, cfg: dict, org_scope: int | None = None) -> dict:
    domain = _configured_domain(cfg)
    limit = min(int(cfg.get("limit", 20)), 50)
    q = scope_query_to_org(
        db.query(models.RawEntity.enrichment_concepts), models.RawEntity, org_scope
    ).filter(
        models.RawEntity.enrichment_concepts != None,
        models.RawEntity.enrichment_concepts != "",
    )
    if domain:
        q = q.filter(models.RawEntity.domain == domain)
    counter: Counter = Counter()
    for (row,) in q.all():
        for tag in (t.strip() for t in row.split(",") if t.strip()):
            counter[tag] += 1
    top = [{"concept": t, "count": c} for t, c in counter.most_common(limit)]
    return {"concepts": top, "total_unique": len(counter)}


def _data_recent_entities(db: Session, cfg: dict, org_scope: int | None = None) -> dict:
    domain = _configured_domain(cfg)
    limit = min(int(cfg.get("limit", 10)), 50)
    q = _scoped_entities(db, org_scope)
    if domain:
        q = q.filter(models.RawEntity.domain == domain)
    rows = q.order_by(models.RawEntity.id.desc()).limit(limit).all()
    return {
        "entities": [
            {
                "id": e.id,
                "primary_label": e.primary_label,
                "domain": e.domain,
                "enrichment_status": e.enrichment_status,
            }
            for e in rows
        ]
    }


def _data_quality_score(db: Session, cfg: dict, org_scope: int | None = None) -> dict:
    domain = _configured_domain(cfg)
    q = _scoped_entities(db, org_scope).filter(models.RawEntity.quality_score != None)
    if domain:
        q = q.filter(models.RawEntity.domain == domain)
    scores = [row.quality_score for row in q.all()]
    if not scores:
        return {"average": None, "count": 0, "distribution": []}
    avg = round(sum(scores) / len(scores), 2)
    buckets = {"0-25": 0, "26-50": 0, "51-75": 0, "76-100": 0}
    for s in scores:
        pct = s * 100
        if pct <= 25:
            buckets["0-25"] += 1
        elif pct <= 50:
            buckets["26-50"] += 1
        elif pct <= 75:
            buckets["51-75"] += 1
        else:
            buckets["76-100"] += 1
    return {
        "average": avg,
        "count": len(scores),
        "distribution": [{"bucket": k, "count": v} for k, v in buckets.items()],
    }


_DATA_PROVIDERS = {
    "entity_stats": _data_entity_stats,
    "top_concepts": _data_top_concepts,
    "recent_entities": _data_recent_entities,
    "quality_score": _data_quality_score,
}


# ── Public embed endpoints ────────────────────────────────────────────────────

def _get_active_widget(token: str, db: Session) -> models.EmbedWidget:
    w = db.query(models.EmbedWidget).filter(
        models.EmbedWidget.public_token == token,
        models.EmbedWidget.is_active == True,  # noqa: E712
    ).first()
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found or inactive")
    return w


def _record_view(w: models.EmbedWidget, db: Session) -> None:
    w.view_count = (w.view_count or 0) + 1
    w.last_viewed_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/embed/{token}/config")
def embed_config(token: str, db: Session = Depends(get_db)):
    """Public — returns widget metadata (name, type, config) without auth."""
    w = _get_active_widget(token, db)
    return {
        "name": w.name,
        "widget_type": w.widget_type,
        "config": json.loads(w.config or "{}"),
    }


@router.get("/embed/{token}/data")
def embed_data(token: str, request: Request, db: Session = Depends(get_db)):
    """
    Public — returns live widget data without auth.
    Validates Origin header against allowed_origins when not '*'.
    """
    w = _get_active_widget(token, db)

    # Origin check
    if w.allowed_origins and w.allowed_origins.strip() != "*":
        origin = request.headers.get("origin", "")
        allowed = [o.strip() for o in w.allowed_origins.split(",") if o.strip()]
        if origin and origin not in allowed:
            raise HTTPException(status_code=403, detail="Origin not allowed")

    cfg = json.loads(w.config or "{}")
    provider = _DATA_PROVIDERS.get(w.widget_type)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Unknown widget type: {w.widget_type}")

    # Public embeds must only ever surface data from the widget's owning tenant.
    # A widget persisted with org_id IS NULL is a legacy/global widget and maps to
    # the legacy-global scope (org_id IS NULL rows) rather than an unfiltered query.
    org_scope = w.org_id if w.org_id is not None else LEGACY_GLOBAL_ORG_ID
    data = provider(db, cfg, org_scope)
    _record_view(w, db)

    return {
        "widget_type": w.widget_type,
        "name": w.name,
        "data": data,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/embed/{token}/snippet")
def embed_snippet(token: str, db: Session = Depends(get_db)):
    """Public — returns ready-to-paste HTML iframe + JS embed snippets."""
    w = _get_active_widget(token, db)
    api_base = "http://localhost:8000"  # consumers replace with their deployed URL

    iframe_snippet = (
        f'<iframe\n'
        f'  src="{api_base}/embed/{token}/frame"\n'
        f'  width="480" height="320"\n'
        f'  frameborder="0"\n'
        f'  title="{w.name}"\n'
        f'></iframe>'
    )
    js_snippet = (
        f"<div id=\"ukip-widget-{token[:8]}\"></div>\n"
        f"<script>\n"
        f"  fetch('{api_base}/embed/{token}/data')\n"
        f"    .then(r => r.json())\n"
        f"    .then(d => {{\n"
        f"      document.getElementById('ukip-widget-{token[:8]}').innerHTML =\n"
        f"        '<pre>' + JSON.stringify(d.data, null, 2) + '</pre>';\n"
        f"    }});\n"
        f"</script>"
    )
    return {
        "token": token,
        "widget_type": w.widget_type,
        "name": w.name,
        "iframe_snippet": iframe_snippet,
        "js_snippet": js_snippet,
    }
