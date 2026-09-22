# ruff: noqa: B008 — Depends(...) in defaults is the FastAPI dependency idiom.
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend import models
from backend.auth import require_role
from backend.database import get_db
from backend.routers.workspace_reset_ops import (
    CONFIRMATION_TEXT,
    PRESERVED_RESOURCES,
    _audit_log_query,
    _delete_annotations,
    _delete_link_dismissals,
    _delete_reset_dependencies_orm,
    _delete_scoped_model,
    _delete_where_ids,
    _existing_tables,
    _hard_delete_reset_rows,
    _ids,
    _member_user_ids,
    _preview_counts,
    _reset_workspace_counters_sql,
    _safe_update,
    _scope_details,
    _scoped_query,
)
from backend.services import data_lifecycle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/workspace-reset", tags=["admin"])


class WorkspaceResetPreview(BaseModel):
    scope_type: str
    scope_label: str
    confirmation_text: str = CONFIRMATION_TEXT
    counts: dict[str, int]
    preserved: list[str] = Field(default_factory=lambda: PRESERVED_RESOURCES.copy())


class WorkspaceResetRequest(BaseModel):
    confirmation_text: str = Field(..., min_length=1, max_length=32)


class WorkspaceResetResponse(BaseModel):
    reset: bool = True
    scope_type: str
    scope_label: str
    deleted: dict[str, int]
    reset_counters: dict[str, int]
    preserved: list[str] = Field(default_factory=lambda: PRESERVED_RESOURCES.copy())


def _close_lifecycle_event(db: Session, event_id: int, *, status: str, evidence: dict) -> None:
    """Finish the reset's lifecycle event.

    The reset expunges the session mid-way, so the event recorded before it is
    detached by now: re-load it by id. Evidence that cannot be written must not
    turn a completed reset into a 500, so a failure here is logged, loudly.
    """
    event = db.get(models.DataLifecycleEvent, event_id)
    if event is None:
        logger.error("Lifecycle event %s for the workspace reset disappeared", event_id)
        return
    try:
        data_lifecycle.complete_event(db, event, status=status, evidence=evidence)
    except Exception:
        logger.exception("Could not close lifecycle event %s for the workspace reset", event_id)


@router.get("/preview", response_model=WorkspaceResetPreview)
def preview_workspace_reset(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id, scope_type, scope_label = _scope_details(db, current_user)
    return WorkspaceResetPreview(
        scope_type=scope_type,
        scope_label=scope_label,
        counts=_preview_counts(db, org_id),
    )


@router.post("", response_model=WorkspaceResetResponse)
def reset_workspace_data(
    payload: WorkspaceResetRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    if payload.confirmation_text.strip().upper() != CONFIRMATION_TEXT:
        raise HTTPException(status_code=422, detail=f'Type "{CONFIRMATION_TEXT}" to confirm the reset')

    org_id, scope_type, scope_label = _scope_details(db, current_user)
    # Read the operator BEFORE anything commits: recording the lifecycle event
    # commits, which expires these attributes, and the reset then expunges the
    # session, leaving current_user detached and unreadable.
    operator_id, operator_username = current_user.id, current_user.username
    existing_tables = _existing_tables(db)

    entity_query = _scoped_query(db, models.RawEntity, org_id)
    authority_query = _scoped_query(db, models.AuthorityRecord, org_id)
    rule_query = _scoped_query(db, models.NormalizationRule, org_id)
    harmonization_query = _scoped_query(db, models.HarmonizationLog, org_id)
    store_query = _scoped_query(db, models.StoreConnection, org_id)
    scheduled_import_query = _scoped_query(db, models.ScheduledImport, org_id)
    scheduled_report_query = _scoped_query(db, models.ScheduledReport, org_id)
    workflow_query = _scoped_query(db, models.Workflow, org_id)
    workflow_run_query = _scoped_query(db, models.WorkflowRun, org_id)
    scraper_query = _scoped_query(db, models.WebScraperConfig, org_id)

    entity_ids = _ids(entity_query, models.RawEntity.id)
    authority_ids = _ids(authority_query, models.AuthorityRecord.id)
    rule_ids = _ids(rule_query, models.NormalizationRule.id)
    harmonization_ids = _ids(harmonization_query, models.HarmonizationLog.id)
    store_ids = _ids(store_query, models.StoreConnection.id)
    workflow_ids = _ids(workflow_query, models.Workflow.id)
    member_ids = _member_user_ids(db, org_id)

    # The audit trail is EVIDENCE, not workspace content: the data lifecycle
    # policy retains operational audit events indefinitely, and an incident is
    # exactly when someone would want them gone (#368). The reset counts them
    # and keeps them; the ids are never handed to a delete path.
    audit_query = _audit_log_query(db, entity_ids, authority_ids, rule_ids)
    retained_audit_logs = audit_query.count()

    deleted: dict[str, int] = {}
    reset_counters: dict[str, int] = {}

    # Recorded before anything is deleted, so an interrupted reset still leaves
    # a trace of what was attempted, by whom.
    lifecycle_event_id = data_lifecycle.record_event(
        db,
        org_id=org_id,
        action="deletion",
        # Always "org": this is a workspace-wide reset, not the erasure of one
        # data subject, and the policy's taxonomy separates the two.
        subject_type="org",
        subject_ref=str(org_id) if org_id is not None else "legacy_global",
        requested_by=operator_id,
        scope={
            "operation": "workspace_reset",
            "scope_type": scope_type,
            "scope_label": scope_label,
            "entities": len(entity_ids),
            "authority_records": len(authority_ids),
            "audit_logs_retained": retained_audit_logs,
        },
    ).id

    try:
        db.flush()
        db.expunge_all()

        # Read markers point at retained audit rows, so they stay too.
        deleted["notification_reads"] = 0

        if member_ids:
            reset_counters["notification_states"] = (
                db.query(models.UserNotificationState)
                .filter(models.UserNotificationState.user_id.in_(member_ids))
                .update({"last_read_at": None}, synchronize_session=False)
            )
        else:
            reset_counters["notification_states"] = 0

        if harmonization_ids:
            deleted["harmonization_change_records"] = (
                db.query(models.HarmonizationChangeRecord)
                .filter(models.HarmonizationChangeRecord.log_id.in_(harmonization_ids))
                .delete(synchronize_session=False)
            )
        else:
            deleted["harmonization_change_records"] = 0

        deleted["annotations"] = 0
        deleted["link_dismissals"] = _delete_link_dismissals(db, entity_ids)

        if store_ids:
            deleted["sync_queue_items"] = 0
            deleted["sync_logs"] = 0
            deleted["sync_mappings"] = 0
        else:
            deleted["sync_queue_items"] = 0
            deleted["sync_logs"] = 0
            deleted["sync_mappings"] = 0

        if member_ids:
            deleted["analysis_contexts"] = (
                db.query(models.AnalysisContext)
                .filter(models.AnalysisContext.user_id.in_(member_ids))
                .delete(synchronize_session=False)
            )
        else:
            deleted["analysis_contexts"] = 0

        if workflow_ids:
            deleted["workflow_runs"] = 0
        else:
            deleted["workflow_runs"] = workflow_run_query.delete(synchronize_session=False)

        deleted["audit_logs"] = 0  # retained on purpose; see above

        reset_counters["store_connections"] = _safe_update(
            db, store_query, models.StoreConnection, {
                models.StoreConnection.entity_count: 0,
                models.StoreConnection.last_sync_at: None,
            },
        )
        reset_counters["scheduled_imports"] = _safe_update(
            db, scheduled_import_query, models.ScheduledImport, {
                models.ScheduledImport.last_run_at: None,
                models.ScheduledImport.next_run_at: None,
                models.ScheduledImport.last_status: None,
                models.ScheduledImport.last_result: None,
                models.ScheduledImport.total_runs: 0,
                models.ScheduledImport.total_entities_imported: 0,
            },
        )
        reset_counters["scheduled_reports"] = _safe_update(
            db, scheduled_report_query, models.ScheduledReport, {
                models.ScheduledReport.last_run_at: None,
                models.ScheduledReport.next_run_at: None,
                models.ScheduledReport.last_status: "pending",
                models.ScheduledReport.last_error: None,
                models.ScheduledReport.total_sent: 0,
            },
        )
        reset_counters["workflows"] = _safe_update(
            db, workflow_query, models.Workflow, {
                models.Workflow.last_run_at: None,
                models.Workflow.run_count: 0,
                models.Workflow.last_run_status: None,
            },
        )
        reset_counters["web_scrapers"] = _safe_update(
            db, scraper_query, models.WebScraperConfig, {
                models.WebScraperConfig.last_run_at: None,
                models.WebScraperConfig.last_run_status: None,
                models.WebScraperConfig.total_runs: 0,
                models.WebScraperConfig.total_enriched: 0,
            },
        )

        if store_ids:
            deleted["sync_queue_items"] += _delete_where_ids(
                db,
                "sync_queue",
                "store_id",
                store_ids,
                existing_tables=existing_tables,
            )
            deleted["sync_queue_items"] += _delete_where_ids(
                db,
                "store_sync_queue",
                "store_id",
                store_ids,
                existing_tables=existing_tables,
            )
            deleted["sync_logs"] += _delete_where_ids(
                db,
                "sync_logs",
                "store_id",
                store_ids,
                existing_tables=existing_tables,
            )
            deleted["sync_mappings"] += _delete_where_ids(
                db,
                "store_sync_mappings",
                "store_id",
                store_ids,
                existing_tables=existing_tables,
            )
        if workflow_ids:
            deleted["workflow_runs"] += _delete_where_ids(
                db,
                "workflow_runs",
                "workflow_id",
                workflow_ids,
                existing_tables=existing_tables,
            )

        try:
            db.execute(text("DELETE FROM search_index"))
        except Exception:
            logger.debug("search_index not present; skipping its reset", exc_info=True)

        with db.no_autoflush:
            deleted["annotations"] = _delete_annotations(
                db,
                entity_ids,
                authority_ids,
                existing_tables=existing_tables,
            )
            deleted["entity_relationships"] = _delete_scoped_model(db, models.EntityRelationship, org_id)
            deleted["authority_record_links"] = _delete_scoped_model(db, models.AuthorityRecordLink, org_id)
            deleted["authority_records"] = _delete_scoped_model(db, models.AuthorityRecord, org_id)
            deleted["normalization_rules"] = _delete_scoped_model(db, models.NormalizationRule, org_id)
            deleted["harmonization_logs"] = _delete_scoped_model(db, models.HarmonizationLog, org_id)
            deleted["raw_entities"] = _delete_scoped_model(db, models.RawEntity, org_id)

        _hard_delete_reset_rows(
            db,
            org_id=org_id,
            entity_ids=entity_ids,
            authority_ids=authority_ids,
            rule_ids=rule_ids,
            harmonization_ids=harmonization_ids,
            store_ids=store_ids,
            workflow_ids=workflow_ids,
            existing_tables=existing_tables,
        )
        db.commit()
        _hard_delete_reset_rows(
            db,
            org_id=org_id,
            entity_ids=entity_ids,
            authority_ids=authority_ids,
            rule_ids=rule_ids,
            harmonization_ids=harmonization_ids,
            store_ids=store_ids,
            workflow_ids=workflow_ids,
            existing_tables=existing_tables,
        )
        _delete_reset_dependencies_orm(
            db,
            entity_ids=entity_ids,
            authority_ids=authority_ids,
            harmonization_ids=harmonization_ids,
            store_ids=store_ids,
            workflow_ids=workflow_ids,
        )
        _reset_workspace_counters_sql(db, org_id=org_id, store_ids=store_ids)
        _delete_reset_dependencies_orm(
            db,
            entity_ids=entity_ids,
            authority_ids=authority_ids,
            harmonization_ids=harmonization_ids,
            store_ids=store_ids,
            workflow_ids=workflow_ids,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        _close_lifecycle_event(
            db,
            lifecycle_event_id,
            status="failed",
            evidence={"error": type(exc).__name__, "deleted_before_failure": deleted},
        )
        logger.exception("Workspace reset failed for scope %s (%s)", scope_label, scope_type)
        raise HTTPException(
            status_code=500,
            detail="Workspace reset failed. Check server logs for details.",
        )

    _close_lifecycle_event(
        db,
        lifecycle_event_id,
        status="completed",
        evidence={
            "deleted": deleted,
            "reset_counters": reset_counters,
            "audit_logs_retained": retained_audit_logs,
        },
    )
    logger.warning(
        "Workspace data reset executed by %s for scope %s (%s)",
        operator_username,
        scope_label,
        scope_type,
    )
    return WorkspaceResetResponse(
        scope_type=scope_type,
        scope_label=scope_label,
        deleted=deleted,
        reset_counters=reset_counters,
    )
