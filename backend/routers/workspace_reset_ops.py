import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy import bindparam, inspect, or_, text
from sqlalchemy.orm import Session

from backend import models
from backend.tenant_access import persisted_org_id, resolve_request_org_id

logger = logging.getLogger(__name__)

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
        # Model has no org_id at all — treat all rows as legacy/global.
        if org_id is None:
            return query
        return query.filter(text("1=0"))

    # Check if the physical column exists in the DB table.
    table_name = model.__tablename__
    if not _column_exists(db, table_name, "org_id"):
        # Column not yet migrated — all rows belong to legacy workspace.
        if org_id is None:
            return query
        return query.filter(text("1=0"))

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
    return column_name in _physical_columns(db, table_name)


def _physical_columns(db: Session, table_name: str) -> set[str]:
    """Return the set of column names that physically exist in the DB table."""
    bind = db.get_bind()
    if bind is None:
        return set()
    if table_name not in _existing_tables(db):
        return set()
    return {col["name"] for col in inspect(bind).get_columns(table_name)}


def _safe_update(
    db: Session,
    query: Any,
    model: Any,
    values: dict[Any, Any],
) -> int:
    """Run an ORM .update() but only include columns that physically exist."""
    table_name = model.__tablename__
    phys = _physical_columns(db, table_name)
    if not phys:
        return 0
    safe_values = {}
    for col_attr, val in values.items():
        col_name = col_attr.key if hasattr(col_attr, "key") else str(col_attr)
        if col_name in phys:
            safe_values[col_attr] = val
    if not safe_values:
        return 0
    return int(query.update(safe_values, synchronize_session=False) or 0)


def _scoped_where(
    db: Session,
    table_name: str,
    org_id: int | None,
    *,
    existing_tables: set[str] | None = None,
) -> tuple[str, dict[str, object]]:
    params: dict[str, object] = {}
    # If the physical table lacks org_id, legacy mode returns all rows.
    if not _column_exists(db, table_name, "org_id"):
        if org_id is None:
            return "1=1", params
        return "1=0", params
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
    where_sql, params = _scoped_where(db, table_name, org_id)
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
    where_sql, params = _scoped_where(db, table_name, org_id)
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
    where_sql, params = _scoped_where(db, table_name, org_id)
    return int(db.execute(text(f"DELETE FROM {table_name} WHERE {where_sql}"), params).rowcount or 0)


def _delete_scoped_model(db: Session, model: Any, org_id: int | None) -> int:
    table_name = model.__tablename__
    if table_name not in _existing_tables(db):
        return 0
    return int(_scoped_query(db, model, org_id).delete(synchronize_session="fetch") or 0)


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


def _hard_delete_reset_rows(
    db: Session,
    *,
    org_id: int | None,
    entity_ids: list[int],
    authority_ids: list[int],
    rule_ids: list[int],
    harmonization_ids: list[int],
    store_ids: list[int],
    workflow_ids: list[int],
    audit_ids: list[int],
    existing_tables: set[str],
) -> None:
    """Run an idempotent SQL cleanup pass before committing the reset."""
    bind = db.get_bind()
    if bind is None:
        return

    scoped_tables = [
        "entity_relationships",
        "authority_record_links",
        "authority_records",
        "normalization_rules",
        "harmonization_logs",
        "workflow_runs",
        "raw_entities",
    ]
    id_deletes = [
        ("link_dismissals", "entity_a_id", entity_ids),
        ("link_dismissals", "entity_b_id", entity_ids),
        ("harmonization_change_records", "log_id", harmonization_ids),
        ("store_sync_mappings", "store_id", store_ids),
        ("sync_logs", "store_id", store_ids),
        ("sync_queue", "store_id", store_ids),
        ("store_sync_queue", "store_id", store_ids),
        ("workflow_runs", "workflow_id", workflow_ids),
        ("audit_logs", "id", audit_ids),
        ("user_notification_reads", "audit_log_id", audit_ids),
    ]

    if _table_exists(db, "annotations", existing_tables):
        annotation_columns = _physical_columns(db, "annotations")
        if entity_ids and authority_ids and {"entity_id", "authority_id"}.issubset(annotation_columns):
            for entity_id, authority_id in zip(entity_ids, authority_ids):
                db.execute(
                    text("DELETE FROM annotations WHERE entity_id = :entity_id OR authority_id = :authority_id"),
                    {"entity_id": entity_id, "authority_id": authority_id},
                )
        elif entity_ids and "entity_id" in annotation_columns:
            for entity_id in entity_ids:
                db.execute(text("DELETE FROM annotations WHERE entity_id = :entity_id"), {"entity_id": entity_id})
        elif authority_ids and "authority_id" in annotation_columns:
            for authority_id in authority_ids:
                db.execute(
                    text("DELETE FROM annotations WHERE authority_id = :authority_id"),
                    {"authority_id": authority_id},
                )

    for table_name, column_name, values in id_deletes:
        if not values or not _table_exists(db, table_name, existing_tables):
            continue
        if column_name not in _physical_columns(db, table_name):
            continue
        stmt = text(f"DELETE FROM {table_name} WHERE {column_name} IN :values").bindparams(
            bindparam("values", expanding=True)
        )
        db.execute(stmt, {"values": values})

    for table_name in scoped_tables:
        if not _table_exists(db, table_name, existing_tables):
            continue
        if org_id is None:
            if _column_exists(db, table_name, "org_id"):
                db.execute(text(f"DELETE FROM {table_name} WHERE org_id IS NULL"))
            else:
                db.execute(text(f"DELETE FROM {table_name}"))
        else:
            db.execute(text(f"DELETE FROM {table_name} WHERE org_id = :org_id"), {"org_id": org_id})


def _delete_reset_dependencies_orm(
    db: Session,
    *,
    entity_ids: list[int],
    authority_ids: list[int],
    harmonization_ids: list[int],
    store_ids: list[int],
    workflow_ids: list[int],
    audit_ids: list[int],
) -> None:
    annotation_filters = []
    if entity_ids:
        annotation_filters.append(models.Annotation.entity_id.in_(entity_ids))
    if authority_ids:
        annotation_filters.append(models.Annotation.authority_id.in_(authority_ids))
    if annotation_filters:
        db.query(models.Annotation).filter(or_(*annotation_filters)).delete(synchronize_session=False)

    if audit_ids:
        db.query(models.UserNotificationRead).filter(
            models.UserNotificationRead.audit_log_id.in_(audit_ids)
        ).delete(synchronize_session=False)
        db.query(models.AuditLog).filter(models.AuditLog.id.in_(audit_ids)).delete(synchronize_session=False)

    if entity_ids:
        db.query(models.LinkDismissal).filter(
            or_(
                models.LinkDismissal.entity_a_id.in_(entity_ids),
                models.LinkDismissal.entity_b_id.in_(entity_ids),
            )
        ).delete(synchronize_session=False)

    if harmonization_ids:
        db.query(models.HarmonizationChangeRecord).filter(
            models.HarmonizationChangeRecord.log_id.in_(harmonization_ids)
        ).delete(synchronize_session=False)

    if store_ids:
        db.query(models.StoreSyncMapping).filter(
            models.StoreSyncMapping.store_id.in_(store_ids)
        ).delete(synchronize_session=False)
        db.query(models.SyncLog).filter(models.SyncLog.store_id.in_(store_ids)).delete(synchronize_session=False)
        db.query(models.SyncQueueItem).filter(models.SyncQueueItem.store_id.in_(store_ids)).delete(
            synchronize_session=False
        )

    if workflow_ids:
        db.query(models.WorkflowRun).filter(models.WorkflowRun.workflow_id.in_(workflow_ids)).delete(
            synchronize_session=False
        )


def _reset_workspace_counters_sql(
    db: Session,
    *,
    org_id: int | None,
    store_ids: list[int],
) -> None:
    scope_where, scope_params = (
        ("org_id IS NULL", {}) if org_id is None else ("org_id = :org_id", {"org_id": org_id})
    )
    db.execute(
        text(f"UPDATE store_connections SET entity_count = 0, last_sync_at = NULL WHERE {scope_where}"),
        scope_params,
    )
    if store_ids:
        db.query(models.StoreConnection).filter(models.StoreConnection.id.in_(store_ids)).update(
            {models.StoreConnection.entity_count: 0, models.StoreConnection.last_sync_at: None},
            synchronize_session=False,
        )
    db.execute(
        text(
            "UPDATE scheduled_imports SET last_run_at = NULL, next_run_at = NULL, last_status = NULL, "
            f"last_result = NULL, total_runs = 0, total_entities_imported = 0 WHERE {scope_where}"
        ),
        scope_params,
    )
    db.execute(
        text(
            "UPDATE scheduled_reports SET last_run_at = NULL, next_run_at = NULL, last_status = 'pending', "
            f"last_error = NULL, total_sent = 0 WHERE {scope_where}"
        ),
        scope_params,
    )
    db.execute(
        text(f"UPDATE workflows SET last_run_at = NULL, run_count = 0, last_run_status = NULL WHERE {scope_where}"),
        scope_params,
    )
    db.execute(
        text(
            "UPDATE web_scraper_configs SET last_run_at = NULL, last_run_status = NULL, "
            f"total_runs = 0, total_enriched = 0 WHERE {scope_where}"
        ),
        scope_params,
    )


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
