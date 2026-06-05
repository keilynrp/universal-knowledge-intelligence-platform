"""EPIC-016 — Data lifecycle service.

Slice 1 (US-070): audit backbone — record_event / complete_event helpers.
Slice 2 (US-071): subject/tenant export (DSAR) — collect_subject_data.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend import models
from backend.tenant_access import persisted_org_id

VALID_ACTIONS = {"export", "deletion", "purge"}
VALID_SUBJECT_TYPES = {"org", "user", "entity_owner"}

# ── DSAR surface catalogue ───────────────────────────────────────────────────
# Each entry: (model_class_name, human_label). Only surfaces that carry
# tenant-owned content; derived/infrastructure tables are excluded.
_EXPORT_SURFACES: list[tuple[str, str]] = [
    ("RawEntity",               "entities"),
    ("Annotation",              "annotations"),
    ("AnalysisContext",         "analysis_contexts"),
    ("UserDashboard",           "dashboards"),
    ("EmbedWidget",             "embed_widgets"),
    ("AlertChannel",            "alert_channels"),
    ("ArtifactTemplate",        "artifact_templates"),
    ("AuthorityRecord",         "authority_records"),
    ("NormalizationRule",       "normalization_rules"),
    ("HarmonizationLog",        "harmonization_logs"),
    ("StoreConnection",         "store_connections"),
    ("ScheduledImport",         "scheduled_imports"),
    ("ScheduledReport",         "scheduled_reports"),
    ("Workflow",                "workflows"),
    ("ImportBatch",             "import_batches"),
    ("DataLifecycleEvent",      "lifecycle_events"),
]


def record_event(
    db: Session,
    *,
    org_id: int | None,
    action: str,
    subject_type: str,
    subject_ref: str,
    requested_by: int | None,
    scope: dict[str, Any] | None = None,
) -> models.DataLifecycleEvent:
    """Persist a 'started' lifecycle event scoped to the active org."""
    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid lifecycle action: {action!r}")
    if subject_type not in VALID_SUBJECT_TYPES:
        raise ValueError(f"Invalid subject_type: {subject_type!r}")

    event = models.DataLifecycleEvent(
        org_id=persisted_org_id(org_id),
        action=action,
        subject_type=subject_type,
        subject_ref=str(subject_ref),
        requested_by=requested_by,
        status="started",
        scope_json=json.dumps(scope or {}, ensure_ascii=False, default=str),
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def complete_event(
    db: Session,
    event: models.DataLifecycleEvent,
    *,
    status: str = "completed",
    evidence: dict[str, Any] | None = None,
) -> models.DataLifecycleEvent:
    """Mark a lifecycle event finished and attach per-store evidence."""
    if status not in {"completed", "failed"}:
        raise ValueError(f"Invalid completion status: {status!r}")
    event.status = status
    event.evidence_json = json.dumps(evidence or {}, ensure_ascii=False, default=str)
    event.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return event


# ── Slice 2 (US-071): DSAR export ────────────────────────────────────────────

def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert an ORM row to a JSON-safe dict."""
    result: dict[str, Any] = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if hasattr(val, "isoformat"):
            result[col.name] = val.isoformat()
        else:
            result[col.name] = val
    return result


def collect_subject_data(
    db: Session,
    org_id: int | None,
) -> dict[str, Any]:
    """Return all tenant-owned data for *org_id* across every DSAR surface.

    The result is a dict keyed by surface label with the rows for that surface,
    plus a ``_counts`` summary. Used by the admin export endpoint to build a
    portable bundle and to record evidence counts in the lifecycle event.

    ``org_id=None`` (super_admin global scope) returns data across all orgs —
    callers must validate that the requesting user is allowed that scope.
    """
    from backend.tenant_access import scope_query_to_org

    bundle: dict[str, Any] = {}
    counts: dict[str, int] = {}

    for model_name, label in _EXPORT_SURFACES:
        model_cls = getattr(models, model_name, None)
        if model_cls is None:
            continue
        rows = scope_query_to_org(db.query(model_cls), model_cls, org_id).all()
        bundle[label] = [_row_to_dict(r) for r in rows]
        counts[label] = len(rows)

    bundle["_counts"] = counts
    return bundle
