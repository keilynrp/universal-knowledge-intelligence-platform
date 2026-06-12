"""create backup assurance events table

Revision ID: a8b9c0d1e2f3
Revises: e5f6a7b8c0d1
Create Date: 2026-06-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a8b9c0d1e2f3"
down_revision = "e5f6a7b8c0d1"
branch_labels = None
depends_on = None

_TABLE = "backup_assurance_events"
_INDEX_COLUMNS = (
    "id",
    "event_type",
    "status",
    "environment",
    "backup_id",
    "completed_at",
    "created_at",
)


def _has_table(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, _TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("environment", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("backup_id", sa.String(length=200), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("release", sa.String(length=120), nullable=True),
        sa.Column("alembic_revision", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("integrity_ref", sa.String(length=200), nullable=True),
        sa.Column("encrypted", sa.Boolean(), nullable=True),
        sa.Column("storage_region", sa.String(length=120), nullable=True),
        sa.Column("retention_class", sa.String(length=30), nullable=True),
        sa.Column("operator", sa.String(length=120), nullable=False),
        sa.Column("expected_rpo_hours", sa.Float(), nullable=True),
        sa.Column("expected_rto_hours", sa.Float(), nullable=True),
        sa.Column("achieved_rpo_hours", sa.Float(), nullable=True),
        sa.Column("achieved_rto_hours", sa.Float(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for column in _INDEX_COLUMNS:
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, _TABLE):
        return
    for column in reversed(_INDEX_COLUMNS):
        op.drop_index(f"ix_{_TABLE}_{column}", table_name=_TABLE)
    op.drop_table(_TABLE)
