"""align postgres schema with models — full schema drift fix

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-08

Fixes all schema drift between backend/models.py and the live PostgreSQL
database accumulated across sprints 1-107.  Covers:

  - Missing tables (6): store_sync_mappings, sync_logs, sync_queue,
    webhook_deliveries, user_dashboards, organization_members
  - Renamed columns on store_connections, ai_integrations, annotations,
    api_keys, harmonization_logs, analysis_contexts, alert_channels
  - Missing columns across 10+ tables
  - Missing indexes on FK and frequently-queried columns
  - Missing foreign-key constraints
  - Default-value mismatches (normalization_rules.rule_type, etc.)

Data-preserving: all column renames use ALTER TABLE … RENAME COLUMN so
existing data is kept.  New NOT-NULL columns use server_default where
needed to backfill existing rows.
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col_exists(table: str, column: str) -> bool:
    """Check whether a column already exists (idempotent guard)."""
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return column in {c["name"] for c in insp.get_columns(table)}


def _table_exists(table: str) -> bool:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return table in insp.get_table_names()


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _index_exists(index_name: str) -> bool:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    for table in insp.get_table_names():
        if any(index.get("name") == index_name for index in insp.get_indexes(table)):
            return True
    return False


def _fk_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if table not in insp.get_table_names():
        return False
    for fk in insp.get_foreign_keys(table):
        if column in (fk.get("constrained_columns") or []):
            return True
    return False


def _safe_add_column(table: str, column: sa.Column):
    if not _col_exists(table, column.name):
        op.add_column(table, column)


def _safe_rename_column(table: str, old: str, new: str):
    if _col_exists(table, old) and not _col_exists(table, new):
        op.alter_column(table, old, new_column_name=new)


def _safe_alter_column(table: str, column: str, **kw):
    if _is_sqlite():
        return
    if _col_exists(table, column):
        op.alter_column(table, column, **kw)


def _safe_create_index(name: str, table: str, columns: list, **kw):
    if not _index_exists(name):
        op.create_index(name, table, columns, **kw)


def _safe_create_fk(name: str, source_table: str, referent_table: str, local_cols, remote_cols):
    if _is_sqlite():
        return
    if not _fk_exists(source_table, local_cols[0]):
        op.create_foreign_key(name, source_table, referent_table, local_cols, remote_cols)


# ═══════════════════════════════════════════════════════════════════════════
# UPGRADE
# ═══════════════════════════════════════════════════════════════════════════

def upgrade() -> None:
    # ── 1. store_connections: rename legacy columns ───────────────────────
    _safe_rename_column("store_connections", "store_type", "platform")
    _safe_rename_column("store_connections", "consumer_key", "api_key")
    _safe_rename_column("store_connections", "consumer_secret", "api_secret")
    _safe_rename_column("store_connections", "api_token", "access_token")
    _safe_rename_column("store_connections", "last_sync", "last_sync_at")

    _safe_add_column("store_connections", sa.Column(
        "entity_count", sa.Integer, server_default="0",
    ))
    _safe_add_column("store_connections", sa.Column(
        "sync_direction", sa.String, server_default="bidirectional",
    ))
    _safe_add_column("store_connections", sa.Column(
        "notes", sa.Text, nullable=True,
    ))

    _safe_create_index("ix_store_connections_name", "store_connections", ["name"])
    _safe_create_index("ix_store_connections_platform", "store_connections", ["platform"])
    _safe_create_index("ix_store_connections_org_id", "store_connections", ["org_id"])

    # ── 2. ai_integrations: rename + add ─────────────────────────────────
    _safe_rename_column("ai_integrations", "provider", "provider_name")

    _safe_add_column("ai_integrations", sa.Column(
        "base_url", sa.String, nullable=True,
    ))

    # Make api_key nullable (model says nullable=True, DB says NOT NULL)
    _safe_alter_column("ai_integrations", "api_key", nullable=True)

    _safe_create_index("ix_ai_integrations_provider_name", "ai_integrations", ["provider_name"], unique=True)

    # ── 3. annotations: rename + add missing ─────────────────────────────
    _safe_rename_column("annotations", "user_id", "author_id")
    _safe_rename_column("annotations", "text", "content")

    _safe_add_column("annotations", sa.Column("author_name", sa.String, server_default=""))
    _safe_add_column("annotations", sa.Column("authority_id", sa.Integer, nullable=True))
    _safe_add_column("annotations", sa.Column("parent_id", sa.Integer, nullable=True))
    _safe_add_column("annotations", sa.Column("updated_at", sa.DateTime, nullable=True))

    # Backfill author_name from users table
    if _is_sqlite():
        op.execute(sa.text("""
            UPDATE annotations
            SET author_name = COALESCE(
                (SELECT COALESCE(users.display_name, users.username, '')
                 FROM users
                 WHERE users.id = annotations.author_id),
                ''
            )
            WHERE author_name IS NULL OR author_name = ''
        """))
    else:
        op.execute(sa.text("""
            UPDATE annotations a
            SET author_name = COALESCE(u.display_name, u.username, '')
            FROM users u
            WHERE a.author_id = u.id
              AND (a.author_name IS NULL OR a.author_name = '')
        """))

    # Make entity_id nullable (model says nullable=True, DB says NOT NULL)
    _safe_alter_column("annotations", "entity_id", nullable=True)

    _safe_create_index("ix_annotations_entity_id", "annotations", ["entity_id"])
    _safe_create_index("ix_annotations_authority_id", "annotations", ["authority_id"])

    # ── 4. api_keys: rename key_prefix ───────────────────────────────────
    _safe_rename_column("api_keys", "prefix", "key_prefix")

    _safe_create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    _safe_create_fk("fk_api_keys_user_id", "api_keys", "users", ["user_id"], ["id"])

    # ── 5. harmonization_logs: rename + add ──────────────────────────────
    _safe_rename_column("harmonization_logs", "affected_count", "records_updated")
    _safe_rename_column("harmonization_logs", "step_params", "fields_modified")
    _safe_rename_column("harmonization_logs", "created_at", "executed_at")
    _safe_rename_column("harmonization_logs", "snapshot_json", "details")

    _safe_add_column("harmonization_logs", sa.Column(
        "step_id", sa.String, nullable=True,
    ))

    # Backfill step_id from step_name where missing
    op.execute(sa.text("""
        UPDATE harmonization_logs
        SET step_id = LOWER(REPLACE(step_name, ' ', '_'))
        WHERE step_id IS NULL
    """))

    _safe_create_index("ix_harmonization_logs_step_id", "harmonization_logs", ["step_id"])
    _safe_create_index("ix_harmonization_logs_org_id", "harmonization_logs", ["org_id"])

    # ── 6. analysis_contexts: rename + add ───────────────────────────────
    # Drop any existing FK on entity_id before renaming/retyping
    if not _is_sqlite() and _col_exists("analysis_contexts", "entity_id"):
        # Find and drop FK constraints referencing entity_id
        conn = op.get_bind()
        fk_rows = conn.execute(sa.text("""
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND kcu.table_name = 'analysis_contexts'
              AND kcu.column_name = 'entity_id'
        """)).fetchall()
        for (fk_name,) in fk_rows:
            op.drop_constraint(fk_name, "analysis_contexts", type_="foreignkey")

    _safe_rename_column("analysis_contexts", "entity_id", "domain_id")
    _safe_rename_column("analysis_contexts", "context_text", "context_snapshot")

    _safe_add_column("analysis_contexts", sa.Column("label", sa.String, server_default=""))

    # domain_id was INTEGER (entity_id), model expects String — cast it
    _safe_alter_column(
        "analysis_contexts", "domain_id",
        type_=sa.String,
        postgresql_using="domain_id::text",
    )

    _safe_create_index("ix_analysis_contexts_domain_id", "analysis_contexts", ["domain_id"])

    # ── 7. alert_channels: rename + add ──────────────────────────────────
    _safe_rename_column("alert_channels", "channel_type", "type")
    _safe_rename_column("alert_channels", "config_json", "webhook_url")

    _safe_add_column("alert_channels", sa.Column("events", sa.Text, server_default="[]"))
    _safe_add_column("alert_channels", sa.Column("last_fired_at", sa.DateTime, nullable=True))
    _safe_add_column("alert_channels", sa.Column("last_fire_status", sa.String(10), nullable=True))
    _safe_add_column("alert_channels", sa.Column("total_fired", sa.Integer, server_default="0"))

    # ── 8. organizations: add missing columns ────────────────────────────
    _safe_add_column("organizations", sa.Column("description", sa.Text, nullable=True))

    # owner_id is NOT NULL in model but we need a default for existing rows.
    # Set to the first super_admin user ID, or 1 as fallback.
    _safe_add_column("organizations", sa.Column(
        "owner_id", sa.Integer, nullable=True,
    ))
    if _col_exists("organizations", "owner_id"):
        op.execute(sa.text("""
            UPDATE organizations
            SET owner_id = COALESCE(
                (SELECT id FROM users WHERE role = 'super_admin' ORDER BY id LIMIT 1),
                1
            )
            WHERE owner_id IS NULL
        """))
        _safe_alter_column("organizations", "owner_id", nullable=False)
        _safe_create_fk("fk_organizations_owner_id", "organizations", "users", ["owner_id"], ["id"])

    # ── 9. webhooks: add missing columns ─────────────────────────────────
    _safe_add_column("webhooks", sa.Column("last_triggered_at", sa.DateTime, nullable=True))
    _safe_add_column("webhooks", sa.Column("last_status", sa.Integer, nullable=True))

    # ── 10. normalization_rules: fix default ─────────────────────────────
    # DB has default 'literal', model expects 'exact'
    if _col_exists("normalization_rules", "rule_type"):
        _safe_alter_column(
            "normalization_rules", "rule_type",
            server_default="exact",
        )
        # Update existing 'literal' values to 'exact'
        op.execute(sa.text("""
            UPDATE normalization_rules
            SET rule_type = 'exact'
            WHERE rule_type = 'literal'
        """))

    _safe_add_column("normalization_rules", sa.Column("is_active", sa.Boolean, server_default="true"))
    _safe_create_index("ix_normalization_rules_field_name", "normalization_rules", ["field_name"])
    _safe_create_index("ix_normalization_rules_original_value", "normalization_rules", ["original_value"])
    _safe_create_index("ix_normalization_rules_org_id", "normalization_rules", ["org_id"])

    # ── 11. Create missing tables ────────────────────────────────────────

    # store_sync_mappings
    if not _table_exists("store_sync_mappings"):
        op.create_table(
            "store_sync_mappings",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("store_id", sa.Integer, index=True),
            sa.Column("local_entity_id", sa.Integer, index=True),
            sa.Column("remote_entity_id", sa.String, nullable=True),
            sa.Column("canonical_url", sa.String, index=True),
            sa.Column("remote_sku", sa.String, nullable=True),
            sa.Column("remote_name", sa.String, nullable=True),
            sa.Column("remote_price", sa.String, nullable=True),
            sa.Column("remote_stock", sa.String, nullable=True),
            sa.Column("remote_status", sa.String, nullable=True),
            sa.Column("remote_data_json", sa.Text, nullable=True),
            sa.Column("sync_status", sa.String, server_default="pending"),
            sa.Column("last_synced_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime),
        )

    # sync_logs
    if not _table_exists("sync_logs"):
        op.create_table(
            "sync_logs",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("store_id", sa.Integer, index=True),
            sa.Column("action", sa.String),
            sa.Column("status", sa.String),
            sa.Column("records_affected", sa.Integer, server_default="0"),
            sa.Column("details", sa.Text, nullable=True),
            sa.Column("executed_at", sa.DateTime),
        )

    # sync_queue (model expects sync_queue; DB has store_sync_queue)
    if not _table_exists("sync_queue"):
        op.create_table(
            "sync_queue",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("store_id", sa.Integer, index=True),
            sa.Column("mapping_id", sa.Integer, nullable=True, index=True),
            sa.Column("direction", sa.String),
            sa.Column("entity_name", sa.String, nullable=True),
            sa.Column("canonical_url", sa.String, nullable=True),
            sa.Column("field", sa.String),
            sa.Column("local_value", sa.Text, nullable=True),
            sa.Column("remote_value", sa.Text, nullable=True),
            sa.Column("status", sa.String, server_default="pending", index=True),
            sa.Column("created_at", sa.DateTime),
            sa.Column("resolved_at", sa.DateTime, nullable=True),
        )

    # webhook_deliveries
    if not _table_exists("webhook_deliveries"):
        op.create_table(
            "webhook_deliveries",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("webhook_id", sa.Integer, index=True, nullable=False),
            sa.Column("event", sa.String, nullable=False),
            sa.Column("url", sa.String, nullable=False),
            sa.Column("status_code", sa.Integer, nullable=True),
            sa.Column("response_body", sa.Text, nullable=True),
            sa.Column("latency_ms", sa.Integer, nullable=True),
            sa.Column("error", sa.String, nullable=True),
            sa.Column("success", sa.Boolean, server_default="false"),
            sa.Column("created_at", sa.DateTime, index=True),
        )

    # user_dashboards
    if not _table_exists("user_dashboards"):
        op.create_table(
            "user_dashboards",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("layout", sa.Text, server_default="[]"),
            sa.Column("is_default", sa.Boolean, server_default="false"),
            sa.Column("created_at", sa.DateTime),
            sa.Column("updated_at", sa.DateTime),
        )

    # organization_members
    if not _table_exists("organization_members"):
        op.create_table(
            "organization_members",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("role", sa.String(20), server_default="member"),
            sa.Column("joined_at", sa.DateTime),
        )

    # ── 12. Missing indexes across existing tables ───────────────────────

    # audit_logs
    _safe_create_index("ix_audit_logs_action", "audit_logs", ["action"])
    _safe_create_index("ix_audit_logs_username", "audit_logs", ["username"])
    _safe_create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # authority_records
    _safe_create_index("ix_authority_records_field_name", "authority_records", ["field_name"])
    _safe_create_index("ix_authority_records_original_value", "authority_records", ["original_value"])
    _safe_create_index("ix_authority_records_authority_source", "authority_records", ["authority_source"])
    _safe_create_index("ix_authority_records_status", "authority_records", ["status"])
    _safe_create_index("ix_authority_records_resolution_status", "authority_records", ["resolution_status"])
    _safe_create_index("ix_authority_records_resolution_route", "authority_records", ["resolution_route"])
    _safe_create_index("ix_authority_records_complexity_score", "authority_records", ["complexity_score"])
    _safe_create_index("ix_authority_records_review_required", "authority_records", ["review_required"])
    _safe_create_index("ix_authority_records_nil_score", "authority_records", ["nil_score"])
    _safe_create_index("ix_authority_records_reformulation_applied", "authority_records", ["reformulation_applied"])
    _safe_create_index("ix_authority_records_org_id", "authority_records", ["org_id"])

    # entity_relationships
    _safe_create_index("ix_entity_relationships_source_id", "entity_relationships", ["source_id"])
    _safe_create_index("ix_entity_relationships_target_id", "entity_relationships", ["target_id"])
    _safe_create_index("ix_entity_relationships_relation_type", "entity_relationships", ["relation_type"])
    _safe_create_index("ix_entity_relationships_org_id", "entity_relationships", ["org_id"])

    # authority_record_links
    if _table_exists("authority_record_links"):
        _safe_create_index("ix_authority_record_links_source_id", "authority_record_links", ["source_authority_record_id"])
        _safe_create_index("ix_authority_record_links_target_id", "authority_record_links", ["target_authority_record_id"])
        _safe_create_index("ix_authority_record_links_link_type", "authority_record_links", ["link_type"])
        _safe_create_index("ix_authority_record_links_status", "authority_record_links", ["status"])
        _safe_create_index("ix_authority_record_links_org_id", "authority_record_links", ["org_id"])

    # embed_widgets
    _safe_create_index("ix_embed_widgets_widget_type", "embed_widgets", ["widget_type"])
    _safe_create_index("ix_embed_widgets_is_active", "embed_widgets", ["is_active"])

    # workflow_runs
    _safe_create_index("ix_workflow_runs_workflow_id", "workflow_runs", ["workflow_id"])
    _safe_create_index("ix_workflow_runs_org_id", "workflow_runs", ["org_id"])

    # workflows
    _safe_create_index("ix_workflows_is_active", "workflows", ["is_active"])
    _safe_create_index("ix_workflows_trigger_type", "workflows", ["trigger_type"])
    _safe_create_index("ix_workflows_org_id", "workflows", ["org_id"])

    # scheduled_imports
    _safe_create_index("ix_scheduled_imports_store_id", "scheduled_imports", ["store_id"])
    _safe_create_index("ix_scheduled_imports_org_id", "scheduled_imports", ["org_id"])

    # scheduled_reports
    _safe_create_index("ix_scheduled_reports_org_id", "scheduled_reports", ["org_id"])

    # web_scraper_configs
    _safe_create_index("ix_web_scraper_configs_is_active", "web_scraper_configs", ["is_active"])
    _safe_create_index("ix_web_scraper_configs_org_id", "web_scraper_configs", ["org_id"])

    # import_batches
    _safe_create_index("ix_import_batches_entity_type_hint", "import_batches", ["entity_type_hint"])

    # users
    _safe_create_index("ix_users_org_id", "users", ["org_id"])
    _safe_create_fk("fk_users_org_id", "users", "organizations", ["org_id"], ["id"])

    # raw_entities
    _safe_create_index("ix_raw_entities_org_id", "raw_entities", ["org_id"])
    _safe_create_index("ix_raw_entities_import_batch_id", "raw_entities", ["import_batch_id"])
    _safe_create_index("ix_raw_entities_quality_score", "raw_entities", ["quality_score"])

    # link_dismissals
    _safe_create_index("ix_link_dismissals_entity_a_id", "link_dismissals", ["entity_a_id"])
    _safe_create_index("ix_link_dismissals_entity_b_id", "link_dismissals", ["entity_b_id"])

    # ── 13. Missing FK constraints ───────────────────────────────────────
    _safe_create_fk("fk_raw_entities_org_id", "raw_entities", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_raw_entities_import_batch_id", "raw_entities", "import_batches", ["import_batch_id"], ["id"])
    _safe_create_fk("fk_entity_relationships_org_id", "entity_relationships", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_entity_relationships_source_id", "entity_relationships", "raw_entities", ["source_id"], ["id"])
    _safe_create_fk("fk_entity_relationships_target_id", "entity_relationships", "raw_entities", ["target_id"], ["id"])
    _safe_create_fk("fk_normalization_rules_org_id", "normalization_rules", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_harmonization_logs_org_id", "harmonization_logs", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_store_connections_org_id", "store_connections", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_authority_records_org_id", "authority_records", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_scheduled_imports_org_id", "scheduled_imports", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_scheduled_reports_org_id", "scheduled_reports", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_web_scraper_configs_org_id", "web_scraper_configs", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_workflows_org_id", "workflows", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_workflow_runs_org_id", "workflow_runs", "organizations", ["org_id"], ["id"])
    _safe_create_fk("fk_workflow_runs_workflow_id", "workflow_runs", "workflows", ["workflow_id"], ["id"])


def downgrade() -> None:
    # ── FK constraints (reverse order) ───────────────────────────────────
    fks_to_drop = [
        ("workflow_runs", "fk_workflow_runs_workflow_id"),
        ("workflow_runs", "fk_workflow_runs_org_id"),
        ("workflows", "fk_workflows_org_id"),
        ("web_scraper_configs", "fk_web_scraper_configs_org_id"),
        ("scheduled_reports", "fk_scheduled_reports_org_id"),
        ("scheduled_imports", "fk_scheduled_imports_org_id"),
        ("authority_records", "fk_authority_records_org_id"),
        ("store_connections", "fk_store_connections_org_id"),
        ("harmonization_logs", "fk_harmonization_logs_org_id"),
        ("normalization_rules", "fk_normalization_rules_org_id"),
        ("entity_relationships", "fk_entity_relationships_target_id"),
        ("entity_relationships", "fk_entity_relationships_source_id"),
        ("entity_relationships", "fk_entity_relationships_org_id"),
        ("raw_entities", "fk_raw_entities_import_batch_id"),
        ("raw_entities", "fk_raw_entities_org_id"),
        ("users", "fk_users_org_id"),
        ("api_keys", "fk_api_keys_user_id"),
        ("organizations", "fk_organizations_owner_id"),
    ]
    for table, fk_name in fks_to_drop:
        try:
            op.drop_constraint(fk_name, table, type_="foreignkey")
        except Exception:
            pass

    # ── Drop created tables ──────────────────────────────────────────────
    for t in ["organization_members", "user_dashboards", "webhook_deliveries",
              "sync_queue", "sync_logs", "store_sync_mappings"]:
        if _table_exists(t):
            op.drop_table(t)

    # ── Reverse column renames ───────────────────────────────────────────
    _safe_rename_column("store_connections", "platform", "store_type")
    _safe_rename_column("store_connections", "api_key", "consumer_key")
    _safe_rename_column("store_connections", "api_secret", "consumer_secret")
    _safe_rename_column("store_connections", "access_token", "api_token")
    _safe_rename_column("store_connections", "last_sync_at", "last_sync")
    _safe_rename_column("ai_integrations", "provider_name", "provider")
    _safe_rename_column("annotations", "author_id", "user_id")
    _safe_rename_column("annotations", "content", "text")
    _safe_rename_column("api_keys", "key_prefix", "prefix")
    _safe_rename_column("harmonization_logs", "records_updated", "affected_count")
    _safe_rename_column("harmonization_logs", "fields_modified", "step_params")
    _safe_rename_column("harmonization_logs", "executed_at", "created_at")
    _safe_rename_column("harmonization_logs", "details", "snapshot_json")
    _safe_rename_column("analysis_contexts", "domain_id", "entity_id")
    _safe_rename_column("analysis_contexts", "context_snapshot", "context_text")
    _safe_rename_column("alert_channels", "type", "channel_type")
    _safe_rename_column("alert_channels", "webhook_url", "config_json")

    # ── Drop added columns ───────────────────────────────────────────────
    added_cols = [
        ("store_connections", "entity_count"),
        ("store_connections", "sync_direction"),
        ("store_connections", "notes"),
        ("ai_integrations", "base_url"),
        ("annotations", "author_name"),
        ("annotations", "authority_id"),
        ("annotations", "parent_id"),
        ("annotations", "updated_at"),
        ("organizations", "description"),
        ("organizations", "owner_id"),
        ("webhooks", "last_triggered_at"),
        ("webhooks", "last_status"),
        ("alert_channels", "events"),
        ("alert_channels", "last_fired_at"),
        ("alert_channels", "last_fire_status"),
        ("alert_channels", "total_fired"),
        ("harmonization_logs", "step_id"),
        ("analysis_contexts", "label"),
        ("normalization_rules", "is_active"),
    ]
    for table, col in added_cols:
        if _col_exists(table, col):
            op.drop_column(table, col)

    # Restore rule_type default
    if _col_exists("normalization_rules", "rule_type"):
        _safe_alter_column("normalization_rules", "rule_type", server_default="literal")
        op.execute(sa.text("""
            UPDATE normalization_rules
            SET rule_type = 'literal'
            WHERE rule_type = 'exact'
        """))

    # Note: index drops are omitted — extra indexes are harmless and
    # dropping them manually is error-prone across different environments.
