"""
Sprint 95 — Onboarding API.

Auto-detects user progress from existing DB state — no extra schema required.

Steps (in order):
  import_data       Entity count > 0
  enrich_entity     Any entity with enrichment_status='completed'
  create_rule       Any NormalizationRule exists
  create_workflow   Any Workflow exists  (Sprint 92)
  explore_analytics Any visit to /dashboard/summary in AuditLog

GET  /onboarding/status  — returns step list with completion flags + pct
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user
from backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ── Step definitions ──────────────────────────────────────────────────────────

_STEPS = [
    {
        "key": "import_data",
        "label": "Import your first data",
        "description": "Upload a CSV, Excel, or BibTeX file to create your knowledge base.",
        "href": "/import-export",
        "icon": "upload",
    },
    {
        "key": "enrich_entity",
        "label": "Enrich an entity",
        "description": "Run automatic enrichment to pull metadata from academic APIs.",
        "href": "/",
        "icon": "sparkles",
    },
    {
        "key": "create_rule",
        "label": "Create a harmonization rule",
        "description": "Standardize labels with normalization rules.",
        "href": "/disambiguation",
        "icon": "adjustments",
    },
    {
        "key": "create_workflow",
        "label": "Automate with a workflow",
        "description": "Set up a trigger → action workflow to automate data operations.",
        "href": "/workflows",
        "icon": "bolt",
    },
    {
        "key": "explore_analytics",
        "label": "Explore the analytics dashboard",
        "description": "View KPIs, enrichment trends, and concept clusters.",
        "href": "/analytics/dashboard",
        "icon": "chart",
    },
]


def _check_steps(db: Session, user: models.User) -> list[dict]:
    """Auto-detect which steps are complete from existing DB state."""

    entity_count = db.query(func.count(models.RawEntity.id)).scalar() or 0
    enriched_count = (
        db.query(func.count(models.RawEntity.id))
        .filter(models.RawEntity.enrichment_status == "completed")
        .scalar() or 0
    )
    rule_count = db.query(func.count(models.NormalizationRule.id)).scalar() or 0
    workflow_count = db.query(func.count(models.Workflow.id)).scalar() or 0
    analytics_visited = (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.endpoint.like("%/dashboard/summary%"),
            models.AuditLog.user_id == user.id,
        )
        .first()
    ) is not None

    completion = {
        "import_data": entity_count > 0,
        "enrich_entity": enriched_count > 0,
        "create_rule": rule_count > 0,
        "create_workflow": workflow_count > 0,
        "explore_analytics": analytics_visited,
    }

    return [
        {**step, "completed": completion.get(step["key"], False)}
        for step in _STEPS
    ]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
def onboarding_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Return onboarding checklist with auto-detected completion status.
    No DB writes — purely derived from existing tables.
    """
    steps = _check_steps(db, current_user)
    completed = sum(1 for s in steps if s["completed"])
    return {
        "steps": steps,
        "completed": completed,
        "total": len(steps),
        "percent": round(completed / len(steps) * 100) if steps else 0,
        "all_done": completed == len(steps),
    }
