"""add tenant scope columns to collaboration + template surfaces

EPIC-012 Wave 2-3, second slice. Adds an idempotent org_id column (+FK +index)
to the remaining tenant-owned tables and backfills it from the owning record:
  - annotations        -> raw_entities.org_id (via entity_id),
                          else authority_records.org_id (via authority_id)
  - user_dashboards    -> users.org_id (via user_id)
  - artifact_templates -> users.org_id (via created_by); built-ins keep NULL
  - alert_channels     -> no owner link; left NULL (legacy-global scope)

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-06-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None

_TENANT_TABLES = (
    "annotations",
    "alert_channels",
    "user_dashboards",
    "artifact_templates",
)


def _column_names(bind, table_name: str) -> set[str]:
    return {col["name"] for col in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table_name)}


def _has_org_fk(bind, table_name: str) -> bool:
    for fk in sa.inspect(bind).get_foreign_keys(table_name):
        if fk.get("referred_table") == "organizations" and fk.get("constrained_columns") == ["org_id"]:
            return True
    return False


def _add_org_id_column(table_name: str) -> None:
    bind = op.get_bind()
    idx_name = f"ix_{table_name}_org_id"
    fk_name = f"fk_{table_name}_org_id_organizations"

    columns = _column_names(bind, table_name)
    indexes = _index_names(bind, table_name)
    has_fk = _has_org_fk(bind, table_name)

    with op.batch_alter_table(table_name) as batch_op:
        if "org_id" not in columns:
            batch_op.add_column(sa.Column("org_id", sa.Integer(), nullable=True))
        if not has_fk:
            batch_op.create_foreign_key(
                fk_name,
                "organizations",
                ["org_id"],
                ["id"],
            )
        if idx_name not in indexes:
            batch_op.create_index(idx_name, ["org_id"], unique=False)


def _drop_org_id_column(table_name: str) -> None:
    bind = op.get_bind()
    idx_name = f"ix_{table_name}_org_id"
    fk_name = f"fk_{table_name}_org_id_organizations"

    columns = _column_names(bind, table_name)
    if "org_id" not in columns:
        return

    indexes = _index_names(bind, table_name)
    has_fk = _has_org_fk(bind, table_name)

    with op.batch_alter_table(table_name) as batch_op:
        if idx_name in indexes:
            batch_op.drop_index(idx_name)
        if has_fk:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.drop_column("org_id")


def upgrade() -> None:
    for table_name in _TENANT_TABLES:
        _add_org_id_column(table_name)

    # annotations: inherit tenant from the referenced entity, then authority.
    op.execute(
        sa.text(
            """
            UPDATE annotations
            SET org_id = (
                SELECT raw_entities.org_id
                FROM raw_entities
                WHERE raw_entities.id = annotations.entity_id
            )
            WHERE org_id IS NULL AND entity_id IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE annotations
            SET org_id = (
                SELECT authority_records.org_id
                FROM authority_records
                WHERE authority_records.id = annotations.authority_id
            )
            WHERE org_id IS NULL AND authority_id IS NOT NULL
            """
        )
    )

    # user_dashboards: inherit tenant from the owning user.
    op.execute(
        sa.text(
            """
            UPDATE user_dashboards
            SET org_id = (
                SELECT users.org_id
                FROM users
                WHERE users.id = user_dashboards.user_id
            )
            WHERE org_id IS NULL
            """
        )
    )

    # artifact_templates: inherit tenant from the creating user; built-ins
    # (created_by IS NULL) intentionally remain global (org_id NULL).
    op.execute(
        sa.text(
            """
            UPDATE artifact_templates
            SET org_id = (
                SELECT users.org_id
                FROM users
                WHERE users.id = artifact_templates.created_by
            )
            WHERE org_id IS NULL AND created_by IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    for table_name in reversed(_TENANT_TABLES):
        _drop_org_id_column(table_name)
