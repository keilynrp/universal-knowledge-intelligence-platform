"""Add scope to backup_assurance_events and backfill existing rows.

Revision ID: b8c9d0e1f2a3
Revises: d1e2f3a4b5c6
Create Date: 2026-09-20

Freshness used to be judged by whichever backup finished last, whatever it
covered (#320). Once the ukip_static_data volume archive started being
recorded — five minutes after the PostgreSQL dump — it became the "latest
backup", so a failing dump alongside a succeeding volume job would have kept
/ops/backups/status green.

The backfill does not default every existing row to `database`: production
already holds a volume archive, and mislabelling it would recreate the defect
in the data. Rows are classified from what they recorded about themselves,
matching backend.backup_assurance.classify_legacy_scope.
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
        sa.Column(
            "scope",
            sa.String(length=20),
            nullable=False,
            server_default="database",
        ),
    )
    op.create_index(
        "ix_backup_assurance_events_scope",
        "backup_assurance_events",
        ["scope"],
    )
    op.execute(
        """
        UPDATE backup_assurance_events
           SET scope = 'volume'
         WHERE lower(coalesce(provider, '')) LIKE '%volume%'
            OR lower(coalesce(backup_id, '')) LIKE '%.tar'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_backup_assurance_events_scope", table_name="backup_assurance_events")
    op.drop_column("backup_assurance_events", "scope")
