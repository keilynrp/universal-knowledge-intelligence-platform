"""create background_jobs table

Durable Background Job Runtime (ADR-007), Phase 2. Broker-free PostgreSQL lease
queue. Idempotent create. NOTE: downgrade DROPS the table and destroys queued and
historical job state — schema reversibility only, never a routine rollback.

Revision ID: c1d2e3f4a5b6
Revises: b7c8d9e0f1a2
Create Date: 2026-07-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None

_TABLE = "background_jobs"


def _has_table(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, _TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("lease_owner", sa.String(length=80), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("replay_of", sa.String(length=64), nullable=True),
        sa.UniqueConstraint(
            "org_id", "job_type", "idempotency_key", name="uq_background_job_idempotency"
        ),
    )
    op.create_index(f"ix_{_TABLE}_id", _TABLE, ["id"])
    op.create_index(f"ix_{_TABLE}_job_id", _TABLE, ["job_id"], unique=True)
    op.create_index(f"ix_{_TABLE}_job_type", _TABLE, ["job_type"])
    op.create_index(f"ix_{_TABLE}_org_id", _TABLE, ["org_id"])
    op.create_index(f"ix_{_TABLE}_status", _TABLE, ["status"])
    op.create_index(f"ix_{_TABLE}_available_at", _TABLE, ["available_at"])
    op.create_index(f"ix_{_TABLE}_lease_expires_at", _TABLE, ["lease_expires_at"])
    op.create_index(f"ix_{_TABLE}_created_at", _TABLE, ["created_at"])
    op.create_index(f"ix_{_TABLE}_correlation_id", _TABLE, ["correlation_id"])
    op.create_index(f"ix_{_TABLE}_replay_of", _TABLE, ["replay_of"])
    op.create_index("ix_background_job_claim", _TABLE, ["status", "available_at", "priority", "id"])


def downgrade() -> None:
    # WARNING: destroys all queued and historical job state. Schema reversibility only.
    bind = op.get_bind()
    if not _has_table(bind, _TABLE):
        return
    op.drop_table(_TABLE)
