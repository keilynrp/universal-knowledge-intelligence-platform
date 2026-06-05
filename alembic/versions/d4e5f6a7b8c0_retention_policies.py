"""create retention_policies table

EPIC-016 US-073: per-org retention configuration for the data lifecycle
purge job. Idempotent create + functional downgrade.

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b9
Create Date: 2026-06-05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c0"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None

_TABLE = "retention_policies"


def _has_table(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, _TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("data_class", sa.String(length=50), nullable=False, server_default="all"),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("org_id", "data_class", name="uq_retention_policy_org_class"),
    )
    op.create_index(f"ix_{_TABLE}_id", _TABLE, ["id"], unique=False)
    op.create_index(f"ix_{_TABLE}_org_id", _TABLE, ["org_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, _TABLE):
        return
    op.drop_index(f"ix_{_TABLE}_org_id", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_id", table_name=_TABLE)
    op.drop_table(_TABLE)
