"""EPIC-016 — Data lifecycle service.

Slice 1 (US-070): audit backbone — record_event / complete_event.
Slice 2 (US-071): DSAR export — collect_subject_data.
Slice 3 (US-072): cascade deletion — delete_subject_data.
Slice 4 (US-073): retention purge — purge_expired_orgs, RetentionPurger.
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


# ── Slice 3 (US-072): Cascade deletion / right to erasure ────────────────────

# Surfaces deleted in dependency-safe order (children before parents).
# DataLifecycleEvent intentionally excluded — audit records are retained as
# compliance evidence even after the underlying tenant data is erased.
_DELETION_SURFACES: list[tuple[str, str]] = [
    ("Annotation",              "annotations"),
    ("AnalysisContext",         "analysis_contexts"),
    ("UserDashboard",           "dashboards"),
    ("EmbedWidget",             "embed_widgets"),
    ("AlertChannel",            "alert_channels"),
    ("ArtifactTemplate",        "artifact_templates"),
    ("AuthorityRecord",         "authority_records"),
    ("NormalizationRule",       "normalization_rules"),
    ("HarmonizationLog",        "harmonization_logs"),
    ("ScheduledImport",         "scheduled_imports"),
    ("ScheduledReport",         "scheduled_reports"),
    ("Workflow",                "workflows"),
    ("ImportBatch",             "import_batches"),
    ("StoreConnection",         "store_connections"),
    # Entities last — ChromaDB doc_ids are collected from them first.
    ("RawEntity",               "entities"),
]


def delete_subject_data(
    db: Session,
    org_id: int | None,
) -> dict[str, int]:
    """Erase all tenant-owned data for *org_id* across every store.

    Returns a dict of per-surface deleted counts (evidence for the lifecycle
    event). The caller is responsible for recording the event.

    Cascade steps:
    1. Collect entity ids for ChromaDB doc_id derivation (before deletion).
    2. Delete every row in _DELETION_SURFACES scoped to org_id.
    3. Delete corresponding ChromaDB documents (entity-<id> per entity).

    DataLifecycleEvent rows are intentionally retained as compliance evidence.
    """
    from backend.analytics.vector_store import VectorStoreService
    from backend.tenant_access import scope_query_to_org

    counts: dict[str, int] = {}

    # Step 1: collect entity ids before any deletion.
    entity_ids: list[int] = [
        row.id for row in
        scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).all()
    ]

    # Step 2: delete DB surfaces in dependency-safe order.
    for model_name, label in _DELETION_SURFACES:
        model_cls = getattr(models, model_name, None)
        if model_cls is None:
            counts[label] = 0
            continue
        rows = scope_query_to_org(db.query(model_cls), model_cls, org_id).all()
        count = len(rows)
        for row in rows:
            db.delete(row)
        db.flush()
        counts[label] = count

    db.commit()

    # Step 3: delete ChromaDB documents.
    chroma_deleted = 0
    chroma_errors = 0
    for entity_id in entity_ids:
        try:
            VectorStoreService.delete_document(f"entity-{entity_id}")
            chroma_deleted += 1
        except Exception:  # noqa: BLE001 — log but don't abort the overall deletion
            chroma_errors += 1

    counts["chromadb_deleted"] = chroma_deleted
    if chroma_errors:
        counts["chromadb_errors"] = chroma_errors


# ── Slice 4 (US-073): Retention purge ────────────────────────────────────────

import logging as _logging

_logger = _logging.getLogger(__name__)

_DEFAULT_PURGE_INTERVAL_SECONDS = 86_400  # 24 h


def purge_expired_orgs(db: Session) -> dict[str, Any]:
    """Run one retention-purge tick: find every org with an expired policy and
    delete its data via the existing cascade.

    Returns a summary dict: {org_id: per-store counts, ...}.
    """
    from backend.tenant_access import LEGACY_GLOBAL_ORG_ID

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for comparison
    policies = db.query(models.RetentionPolicy).filter(
        models.RetentionPolicy.retention_days.isnot(None)
    ).all()

    summary: dict[str, Any] = {}

    for policy in policies:
        if policy.retention_days is None:
            continue
        org_id = policy.org_id  # None = legacy-global default; skip auto-purge
        if org_id is None:
            continue

        # Find entities older than the retention window.
        cutoff = now
        from datetime import timedelta
        cutoff_dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=policy.retention_days
        )

        # Check if any entity predates the cutoff — if not, skip.
        has_expired = db.query(models.RawEntity).filter(
            models.RawEntity.org_id == org_id,
            models.RawEntity.updated_at <= cutoff_dt,
        ).first()
        if not has_expired:
            continue

        event = record_event(
            db,
            org_id=org_id,
            action="purge",
            subject_type="org",
            subject_ref=str(org_id),
            requested_by=None,
            scope={"retention_days": policy.retention_days, "cutoff": cutoff_dt.isoformat()},
        )
        try:
            counts = delete_subject_data(db, org_id)
            complete_event(db, event, status="completed", evidence=counts)
            summary[str(org_id)] = counts
            _logger.info("Retention purge completed for org_id=%s: %s", org_id, counts)
        except Exception as exc:
            complete_event(db, event, status="failed", evidence={"error": str(exc)})
            _logger.exception("Retention purge failed for org_id=%s", org_id)

    return summary


class RetentionPurger:
    """Async loop that runs purge_expired_orgs on a configurable interval.

    Follows the same pattern as EnrichmentScheduler. Start via:
        asyncio.create_task(RetentionPurger().start_loop())
    """

    def __init__(self, interval_seconds: int = _DEFAULT_PURGE_INTERVAL_SECONDS) -> None:
        self.interval_seconds = interval_seconds

    def run_once(self, db: Session) -> dict[str, Any]:
        return purge_expired_orgs(db)

    async def start_loop(self) -> None:
        import asyncio
        from backend.database import SessionLocal

        _logger.info("RetentionPurger started (interval=%ds)", self.interval_seconds)
        while True:
            try:
                with SessionLocal() as db:
                    result = self.run_once(db)
                if result:
                    _logger.info("RetentionPurger tick purged %d orgs", len(result))
            except Exception:
                _logger.exception("RetentionPurger loop error")
            await asyncio.sleep(self.interval_seconds)
