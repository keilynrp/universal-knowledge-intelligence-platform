import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, inspect, or_, text
from sqlalchemy.orm import Session

from backend import models
from backend.auth import require_role
from backend.database import get_db
from backend.tenant_access import persisted_org_id, resolve_request_org_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/workspace-reset", tags=["admin"])

CONFIRMATION_TEXT = "RESET"
PRESERVED_RESOURCES = [
    "users",
    "organization membership",
    "branding settings",
    "notification settings",
    "api keys",
    "webhooks and alert channels",
    "scheduled import and report definitions",
    "workflow definitions",
]


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


def _scope_details(db: Session, current_user: models.User) -> tuple[int | None, str, str]:
    requested_org_id = resolve_request_org_id(
        db,
        current_user,
        allow_super_admin_global=False,
        allow_legacy_global=True,
    )
    org_id = persisted_org_id(requested_org_id)
    if org_id is None:
        return None, "legacy_global", "Default workspace"

    org = db.get(models.Organization, org_id)
    if not org or not org.is_active:
        raise HTTPException(status_code=404, detail="Active organization not found")
    return org_id, "organization", org.name


def _scoped_query(db: Session, model: Any, org_id: int | None):
    query = db.query(model)
    org_column = getattr(model, "org_id", None)
    if org_column is None:
        raise ValueError(f"Model {model.__name__} does not expose org_id")
    if org_id is None:
        return query.filter(org_column.is_(None))
    return query.filter(org_column == org_id)


def _ids(query, column) -> list[int]:
    return [value for (value,) in query.with_entities(column).all()]


def _existing_tables(db: Session) -> set[str]:
    bind = db.get_bind()
    if bind is None:
        return set()
    return set(inspect(bind).get_table_names())


def _table_exists(db: Session, table_name: str, existing_tables: set[str] | None = None) -> bool:
    tables = existing_tables if existing_tables is not None else _existing_tables(db)
    return table_name in tables


def _column_exists(db: Session, table_name: str, column_name: str) -> bool:
    bind = db.get_bind()
    if bind is None:
        return False
    if table_name not in _existing_tables(db):
        return False
    return column_name in {col["name"] for col in inspect(bind).get_columns(table_name)}


def _scoped_where(table_name: str, org_id: int | None) -> tuple[str, dict[str, object]]:
    params: dict[str, object] = {}
    if org_id is None:
        return f"{table_name}.org_id IS NULL", params
    params["org_id"] = org_id
    return f"{table_name}.org_id = :org_id", params


def _count_table(
    db: Session,
    table_name: str,
    *,
    org_id: int | None,
    existing_tables: set[str] | None = None,
) -> int:
    if not _table_exists(db, table_name, existing_tables):
        return 0
    where_sql, params = _scoped_where(table_name, org_id)
    return int(
        db.execute(
            text(f"SELECT COUNT(*) FROM {table_name} WHERE {where_sql}"),
            params,
        ).scalar()
        or 0
    )


def _ids_for_table(
    db: Session,
    table_name: str,
    *,
    org_id: int | None,
    existing_tables: set[str] | None = None,
) -> list[int]:
    if not _table_exists(db, table_name, existing_tables):
        return []
    where_sql, params = _scoped_where(table_name, org_id)
    rows = db.execute(
        text(f"SELECT id FROM {table_name} WHERE {where_sql}"),
        params,
    ).fetchall()
    return [int(row[0]) for row in rows]


def _count_annotation_rows(
    db: Session,
    entity_ids: list[int],
    authority_ids: list[int],
    *,
    existing_tables: set[str] | None = None,
) -> int:
    if not _table_exists(db, "annotations", existing_tables):
        return 0
    if not (entity_ids or authority_ids):
        return 0
    clauses: list[str] = []
    params: dict[str, object] = {}
    bind_params = []
    if entity_ids and _column_exists(db, "annotations", "entity_id"):
        clauses.append("entity_id IN :entity_ids")
        params["entity_ids"] = entity_ids
        bind_params.append(bindparam("entity_ids", expanding=True))
    if authority_ids and _column_exists(db, "annotations", "authority_id"):
        clauses.append("authority_id IN :authority_ids")
        params["authority_ids"] = authority_ids
        bind_params.append(bindparam("authority_ids", expanding=True))
    if not clauses:
        return 0
    stmt = text(f"SELECT COUNT(*) FROM annotations WHERE {' OR '.join(clauses)}")
    if bind_params:
        stmt = stmt.bindparams(*bind_params)
    return int(db.execute(stmt, params).scalar() or 0)


def _delete_where_ids(
    db: Session,
    table_name: str,
    column_name: str,
    values: list[int],
    *,
    existing_tables: set[str] | None = None,
) -> int:
    if not values or not _table_exists(db, table_name, existing_tables):
        return 0
    stmt = text(f"DELETE FROM {table_name} WHERE {column_name} IN :values").bindparams(
        bindparam("values", expanding=True)
    )
    return int(db.connection().execute(stmt, {"values": values}).rowcount or 0)


def _delete_scoped_table(
    db: Session,
    table_name: str,
    *,
    org_id: int | None,
    existing_tables: set[str] | None = None,
) -> int:
    if not _table_exists(db, table_name, existing_tables):
        return 0
    where_sql, params = _scoped_where(table_name, org_id)
    return int(db.execute(text(f"DELETE FROM {table_name} WHERE {where_sql}"), params).rowcount or 0)


def _delete_scoped_model(db: Session, model: Any, org_id: int | None) -> int:
    return int(_scoped_query(db, model, org_id).delete(synchronize_session=False) or 0)


def _count_where_ids(
    db: Session,
    table_name: str,
    column_name: str,
    values: list[int],
    *,
    existing_tables: set[str] | None = None,
) -> int:
    if not values or not _table_exists(db, table_name, existing_tables):
        return 0
    stmt = text(f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} IN :values").bindparams(
        bindparam("values", expanding=True)
    )
    return int(db.execute(stmt, {"values": tuple(values)}).scalar() or 0)


def _delete_annotations(
    db: Session,
    entity_ids: list[int],
    authority_ids: list[int],
    *,
    existing_tables: set[str] | None = None,
) -> int:
    if not _table_exists(db, "annotations", existing_tables):
        return 0
    if not (entity_ids or authority_ids):
        return 0
    clauses: list[str] = []
    params: dict[str, object] = {}
    if entity_ids and _column_exists(db, "annotations", "entity_id"):
        clauses.append("entity_id IN :entity_ids")
        params["entity_ids"] = entity_ids
    if authority_ids and _column_exists(db, "annotations", "authority_id"):
        clauses.append("authority_id IN :authority_ids")
        params["authority_ids"] = authority_ids
    if not clauses:
        return 0

    stmt = text(f"DELETE FROM annotations WHERE {' OR '.join(clauses)}")
    bind_params = []
    if "entity_ids" in params:
        bind_params.append(bindparam("entity_ids", expanding=True))
    if "authority_ids" in params:
        bind_params.append(bindparam("authority_ids", expanding=True))
    if bind_params:
        stmt = stmt.bindparams(*bind_params)
    return int(db.execute(stmt, params).rowcount or 0)


def _delete_link_dismissals(db: Session, entity_ids: list[int]) -> int:
    if not entity_ids:
        return 0
    return int(
        db.query(models.LinkDismissal)
        .filter(
            or_(
                models.LinkDismissal.entity_a_id.in_(entity_ids),
                models.LinkDismissal.entity_b_id.in_(entity_ids),
            )
        )
        .delete(synchronize_session=False)
        or 0
    )


def _audit_log_query(
    db: Session,
    entity_ids: list[int],
    authority_ids: list[int],
    rule_ids: list[int],
) -> Any:
    query = db.query(models.AuditLog)
    conditions = []
    if entity_ids:
        conditions.append(
            ((models.AuditLog.entity_type == "entity") | (models.AuditLog.entity_type.is_(None)))
            & models.AuditLog.entity_id.in_(entity_ids)
        )
    if authority_ids:
        conditions.append(
            (models.AuditLog.entity_type == "authority_record")
            & models.AuditLog.entity_id.in_(authority_ids)
        )
    if rule_ids:
        conditions.append(
            ((models.AuditLog.entity_type == "rule") | (models.AuditLog.entity_type == "normalization_rule"))
            & models.AuditLog.entity_id.in_(rule_ids)
        )
    if not conditions:
        return query.filter(text("1=0"))
    return query.filter(or_(*conditions))


def _delete_audit_logs(db: Session, audit_ids: list[int]) -> int:
    if not audit_ids:
        return 0
    return int(
        db.query(models.AuditLog)
        .filter(models.AuditLog.id.in_(audit_ids))
        .delete(synchronize_session=False)
        or 0
    )


def _member_user_ids(db: Session, org_id: int | None) -> list[int]:
    if org_id is None:
        return []
    return [
        user_id
        for (user_id,) in (
            db.query(models.OrganizationMember.user_id)
            .filter(models.OrganizationMember.org_id == org_id)
            .all()
        )
    ]


def _preview_counts(db: Session, org_id: int | None) -> dict[str, int]:
    existing_tables = _existing_tables(db)
    entity_query = _scoped_query(db, models.RawEntity, org_id)
    authority_query = _scoped_query(db, models.AuthorityRecord, org_id)
    rule_query = _scoped_query(db, models.NormalizationRule, org_id)
    harmonization_query = _scoped_query(db, models.HarmonizationLog, org_id)
    store_query = _scoped_query(db, models.StoreConnection, org_id)

    entity_ids = _ids(entity_query, models.RawEntity.id)
    authority_ids = _ids(authority_query, models.AuthorityRecord.id)
    rule_ids = _ids(rule_query, models.NormalizationRule.id)
    store_ids = _ids(store_query, models.StoreConnection.id)
    member_ids = _member_user_ids(db, org_id)

    annotation_count = _count_annotation_rows(db, entity_ids, authority_ids, existing_tables=existing_tables)

    sync_count = 0
    if store_ids:
        sync_count += _count_where_ids(db, "store_sync_mappings", "store_id", store_ids, existing_tables=existing_tables)
        sync_count += _count_where_ids(db, "sync_logs", "store_id", store_ids, existing_tables=existing_tables)
        sync_count += _count_where_ids(db, "sync_queue", "store_id", store_ids, existing_tables=existing_tables)
        sync_count += _count_where_ids(db, "store_sync_queue", "store_id", store_ids, existing_tables=existing_tables)

    entity_count = _count_table(db, "raw_entities", org_id=org_id, existing_tables=existing_tables)
    authority_count = _count_table(db, "authority_records", org_id=org_id, existing_tables=existing_tables)
    authority_link_count = _count_table(db, "authority_record_links", org_id=org_id, existing_tables=existing_tables)
    normalization_count = _count_table(db, "normalization_rules", org_id=org_id, existing_tables=existing_tables)
    harmonization_count = _count_table(db, "harmonization_logs", org_id=org_id, existing_tables=existing_tables)
    workflow_run_count = _count_table(db, "workflow_runs", org_id=org_id, existing_tables=existing_tables)
    relationship_count = _count_table(db, "entity_relationships", org_id=org_id, existing_tables=existing_tables)

    analysis_count = 0
    if member_ids:
        analysis_count = (
            db.query(models.AnalysisContext)
            .filter(models.AnalysisContext.user_id.in_(member_ids))
            .count()
        )

    audit_count = _audit_log_query(db, entity_ids, authority_ids, rule_ids).count()

    return {
        "entities": entity_count,
        "relationships": relationship_count,
        "authority_records": authority_count,
        "authority_record_links": authority_link_count,
        "normalization_rules": normalization_count,
        "harmonization_runs": harmonization_count,
        "annotations": annotation_count,
        "sync_artifacts": sync_count,
        "workflow_runs": workflow_run_count,
        "analysis_snapshots": analysis_count,
        "audit_entries": audit_count,
    }


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
    existing_tables = _existing_tables(db)

    entity_query = _scoped_query(db, models.RawEntity, org_id)
    relationship_query = _scoped_query(db, models.EntityRelationship, org_id)
    authority_query = _scoped_query(db, models.AuthorityRecord, org_id)
    authority_link_query = _scoped_query(db, models.AuthorityRecordLink, org_id)
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

    audit_query = _audit_log_query(db, entity_ids, authority_ids, rule_ids)
    audit_ids = _ids(audit_query, models.AuditLog.id)

    deleted: dict[str, int] = {}
    reset_counters: dict[str, int] = {}

    try:
        db.flush()
        db.expunge_all()

        if audit_ids:
            deleted["notification_reads"] = (
                db.query(models.UserNotificationRead)
                .filter(models.UserNotificationRead.audit_log_id.in_(audit_ids))
                .delete(synchronize_session=False)
            )
        else:
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

        deleted["audit_logs"] = 0

        reset_counters["store_connections"] = store_query.update(
            {
                models.StoreConnection.entity_count: 0,
                models.StoreConnection.last_sync_at: None,
            },
            synchronize_session=False,
        )
        reset_counters["scheduled_imports"] = scheduled_import_query.update(
            {
                models.ScheduledImport.last_run_at: None,
                models.ScheduledImport.next_run_at: None,
                models.ScheduledImport.last_status: None,
                models.ScheduledImport.last_result: None,
                models.ScheduledImport.total_runs: 0,
                models.ScheduledImport.total_entities_imported: 0,
            },
            synchronize_session=False,
        )
        reset_counters["scheduled_reports"] = scheduled_report_query.update(
            {
                models.ScheduledReport.last_run_at: None,
                models.ScheduledReport.next_run_at: None,
                models.ScheduledReport.last_status: "pending",
                models.ScheduledReport.last_error: None,
                models.ScheduledReport.total_sent: 0,
            },
            synchronize_session=False,
        )
        reset_counters["workflows"] = workflow_query.update(
            {
                models.Workflow.last_run_at: None,
                models.Workflow.run_count: 0,
                models.Workflow.last_run_status: None,
            },
            synchronize_session=False,
        )
        reset_counters["web_scrapers"] = scraper_query.update(
            {
                models.WebScraperConfig.last_run_at: None,
                models.WebScraperConfig.last_run_status: None,
                models.WebScraperConfig.total_runs: 0,
                models.WebScraperConfig.total_enriched: 0,
            },
            synchronize_session=False,
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
            # FTS table exists only in SQLite test mode.
            pass

        db.expunge_all()
        with db.no_autoflush:
            deleted["audit_logs"] = _delete_audit_logs(db, audit_ids)
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

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Workspace reset failed for scope %s (%s)", scope_label, scope_type)
        raise

    logger.warning(
        "Workspace data reset executed by %s for scope %s (%s)",
        current_user.username,
        scope_label,
        scope_type,
    )
    return WorkspaceResetResponse(
        scope_type=scope_type,
        scope_label=scope_label,
        deleted=deleted,
        reset_counters=reset_counters,
    )
