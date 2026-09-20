"""Add scope to backup_assurance_events.

Revision ID: b8c9d0e1f2a3
Revises: d1e2f3a4b5c6
Create Date: 2026-09-20

Freshness used to be judged by whichever backup finished last, whatever it
covered (#320). Once the ukip_static_data volume archive started being
recorded — five minutes after the PostgreSQL dump — it became the "latest
backup", so a failing dump alongside a succeeding volume job would have kept
/ops/backups/status green.

The column is nullable and is NOT backfilled. The first version of this
migration tried, and production refused it:

    psycopg2.errors.RaiseException: backup_assurance_events is append-only

That trigger is the control this issue exists to establish — recorded evidence
is not rewritten — so the migration leaves the existing rows exactly as they
were. Their scope is derived when read, from what they already recorded
(backend.backup_assurance.scope_filter / classify_legacy_scope). Every row
written since carries its own scope.
"""
import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "backup_assurance_events",
        sa.Column("scope", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "ix_backup_assurance_events_scope",
        "backup_assurance_events",
        ["scope"],
    )


def downgrade() -> None:
    op.drop_index("ix_backup_assurance_events_scope", table_name="backup_assurance_events")
    op.drop_column("backup_assurance_events", "scope")
