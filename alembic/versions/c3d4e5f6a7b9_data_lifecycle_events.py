"""create data_lifecycle_events table

EPIC-016 US-070: tenant-scoped audit trail for data lifecycle actions
(export, deletion, retention purge). Idempotent create + functional downgrade.

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-06-05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b9"
down_revision = "b2c3d4e5f6a8"
branch_labels = None
depends_on = None

_TABLE = "data_lifecycle_events"


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
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("subject_ref", sa.String(length=200), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="started"),
        sa.Column("scope_json", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(f"ix_{_TABLE}_id", _TABLE, ["id"], unique=False)
    op.create_index(f"ix_{_TABLE}_org_id", _TABLE, ["org_id"], unique=False)
    op.create_index(f"ix_{_TABLE}_action", _TABLE, ["action"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, _TABLE):
        return
    op.drop_index(f"ix_{_TABLE}_action", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_org_id", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_id", table_name=_TABLE)
    op.drop_table(_TABLE)
