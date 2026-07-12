"""create retrospective_events and retrospective_snapshots tables

Retrospective Intelligence Layer (ADR-006), Phase 2. Append-only historical
event and point-in-time snapshot tables. Idempotent create. NOTE: downgrade
DROPS the tables and therefore DESTROYS all retrospective history — provided for
schema reversibility only, never as a routine rollback.

Revision ID: b7c8d9e0f1a2
Revises: e6f7a8b9c0d2
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b7c8d9e0f1a2"
down_revision = "e6f7a8b9c0d2"
branch_labels = None
depends_on = None

_EVENTS = "retrospective_events"
_SNAPSHOTS = "retrospective_snapshots"


def _has_table(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, _EVENTS):
        op.create_table(
            _EVENTS,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_id", sa.String(length=64), nullable=False),
            sa.Column("event_type", sa.String(length=80), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
            sa.Column("domain_object_type", sa.String(length=60), nullable=False),
            sa.Column("domain_object_id", sa.String(length=120), nullable=False),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("recorded_at", sa.DateTime(), nullable=False),
            sa.Column("source", sa.String(length=80), nullable=False),
            sa.Column("actor_type", sa.String(length=20), nullable=False),
            sa.Column("actor_id", sa.String(length=120), nullable=True),
            sa.Column("correlation_id", sa.String(length=64), nullable=True),
            sa.Column("idempotency_key", sa.String(length=120), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("lineage", sa.Text(), nullable=True),
            sa.UniqueConstraint(
                "org_id", "event_type", "idempotency_key",
                name="uq_retro_event_idempotency",
            ),
        )
        op.create_index(f"ix_{_EVENTS}_id", _EVENTS, ["id"])
        op.create_index(f"ix_{_EVENTS}_event_id", _EVENTS, ["event_id"], unique=True)
        op.create_index(f"ix_{_EVENTS}_event_type", _EVENTS, ["event_type"])
        op.create_index(f"ix_{_EVENTS}_org_id", _EVENTS, ["org_id"])
        op.create_index(f"ix_{_EVENTS}_domain_object_id", _EVENTS, ["domain_object_id"])
        op.create_index(f"ix_{_EVENTS}_occurred_at", _EVENTS, ["occurred_at"])
        op.create_index(f"ix_{_EVENTS}_recorded_at", _EVENTS, ["recorded_at"])
        op.create_index(f"ix_{_EVENTS}_correlation_id", _EVENTS, ["correlation_id"])
        op.create_index(
            "ix_retro_event_type_recorded", _EVENTS, ["event_type", "recorded_at"]
        )

    if not _has_table(bind, _SNAPSHOTS):
        op.create_table(
            _SNAPSHOTS,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("snapshot_id", sa.String(length=64), nullable=False),
            sa.Column("snapshot_type", sa.String(length=80), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
            sa.Column("subject_type", sa.String(length=60), nullable=False),
            sa.Column("subject_id", sa.String(length=120), nullable=False),
            sa.Column("valid_at", sa.DateTime(), nullable=False),
            sa.Column("recorded_at", sa.DateTime(), nullable=False),
            sa.Column("idempotency_key", sa.String(length=120), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("lineage", sa.Text(), nullable=True),
            sa.UniqueConstraint(
                "org_id", "snapshot_type", "idempotency_key",
                name="uq_retro_snapshot_idempotency",
            ),
        )
        op.create_index(f"ix_{_SNAPSHOTS}_id", _SNAPSHOTS, ["id"])
        op.create_index(f"ix_{_SNAPSHOTS}_snapshot_id", _SNAPSHOTS, ["snapshot_id"], unique=True)
        op.create_index(f"ix_{_SNAPSHOTS}_snapshot_type", _SNAPSHOTS, ["snapshot_type"])
        op.create_index(f"ix_{_SNAPSHOTS}_org_id", _SNAPSHOTS, ["org_id"])
        op.create_index(f"ix_{_SNAPSHOTS}_subject_id", _SNAPSHOTS, ["subject_id"])
        op.create_index(f"ix_{_SNAPSHOTS}_valid_at", _SNAPSHOTS, ["valid_at"])
        op.create_index(f"ix_{_SNAPSHOTS}_recorded_at", _SNAPSHOTS, ["recorded_at"])
        op.create_index(
            "ix_retro_snapshot_subject_valid",
            _SNAPSHOTS,
            ["subject_type", "subject_id", "valid_at"],
        )


def downgrade() -> None:
    # WARNING: destroys all retrospective history. Schema reversibility only.
    bind = op.get_bind()
    if _has_table(bind, _SNAPSHOTS):
        op.drop_table(_SNAPSHOTS)
    if _has_table(bind, _EVENTS):
        op.drop_table(_EVENTS)
