"""create secret_rotation_events table

EPIC-017: append-only evidence of secret/credential rotations. Idempotent
create. NOTE: downgrade DROPS the table and therefore DESTROYS all rotation
history — provided for schema reversibility only, never as a routine rollback.

Revision ID: e5f6a7b8c0d1
Revises: d4e5f6a7b8c0
Create Date: 2026-06-05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c0d1"
down_revision = "d4e5f6a7b8c0"
branch_labels = None
depends_on = None

_TABLE = "secret_rotation_events"


def _has_table(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, _TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("secret_name", sa.String(length=60), nullable=False),
        sa.Column("rotated_at", sa.DateTime(), nullable=False),
        sa.Column("operator", sa.String(length=120), nullable=False),
        sa.Column("rows_reencrypted", sa.Integer(), nullable=True),
        sa.Column("old_key_fingerprint", sa.String(length=40), nullable=True),
        sa.Column("new_key_fingerprint", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index(f"ix_{_TABLE}_id", _TABLE, ["id"], unique=False)
    op.create_index(f"ix_{_TABLE}_secret_name", _TABLE, ["secret_name"], unique=False)


def downgrade() -> None:
    # WARNING: destroys all rotation evidence. Schema reversibility only.
    bind = op.get_bind()
    if not _has_table(bind, _TABLE):
        return
    op.drop_index(f"ix_{_TABLE}_secret_name", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_id", table_name=_TABLE)
    op.drop_table(_TABLE)
