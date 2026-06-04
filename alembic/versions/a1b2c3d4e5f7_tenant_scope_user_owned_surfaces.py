"""add tenant scope columns to user-owned surfaces (analysis_contexts, embed_widgets)

EPIC-012 Wave 3. Both tables previously had no org_id, so their routers could
not enforce tenant isolation. This adds an idempotent org_id column (+FK +index)
and backfills it from the owning user's organization:
  - analysis_contexts.user_id   -> users.org_id
  - embed_widgets.created_by     -> users.org_id

Revision ID: a1b2c3d4e5f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None

# (table, owner_column) — owner_column joins to users.id to derive the org.
_TENANT_TABLES = (
    ("analysis_contexts", "user_id"),
    ("embed_widgets", "created_by"),
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
    for table_name, _owner_col in _TENANT_TABLES:
        _add_org_id_column(table_name)

    # Backfill org_id from the owning user's organization.
    for table_name, owner_col in _TENANT_TABLES:
        op.execute(
            sa.text(
                f"""
                UPDATE {table_name}
                SET org_id = (
                    SELECT users.org_id
                    FROM users
                    WHERE users.id = {table_name}.{owner_col}
                )
                WHERE org_id IS NULL
                """
            )
        )


def downgrade() -> None:
    for table_name, _owner_col in reversed(_TENANT_TABLES):
        _drop_org_id_column(table_name)
