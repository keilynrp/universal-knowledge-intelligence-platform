"""create backup assurance events table

Revision ID: a8b9c0d1e2f3
Revises: e5f6a7b8c0d1
Create Date: 2026-06-12

UNRELEASED: this revision must not be considered released before feature merge.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a8b9c0d1e2f3"
down_revision = "e5f6a7b8c0d1"
branch_labels = None
depends_on = None

_TABLE = "backup_assurance_events"
_SQLITE_UPDATE_TRIGGER = "trg_backup_assurance_events_no_update"
_SQLITE_DELETE_TRIGGER = "trg_backup_assurance_events_no_delete"
_POSTGRES_FUNCTION = "reject_backup_assurance_event_mutation"
_POSTGRES_UPDATE_TRIGGER = "trg_backup_assurance_events_no_update"
_POSTGRES_DELETE_TRIGGER = "trg_backup_assurance_events_no_delete"
_STATUS_LOOKUP_INDEX = "ix_backup_assurance_status_lookup"
_INDEX_COLUMNS = (
    "id",
    "event_type",
    "status",
    "environment",
    "backup_id",
    "completed_at",
    "created_at",
)


def _create_append_only_triggers(bind) -> None:
    if bind.dialect.name == "sqlite":
        op.execute(f"""
            CREATE TRIGGER {_SQLITE_UPDATE_TRIGGER}
            BEFORE UPDATE ON {_TABLE}
            BEGIN
                SELECT RAISE(ABORT, '{_TABLE} is append-only');
            END
        """)
        op.execute(f"""
            CREATE TRIGGER {_SQLITE_DELETE_TRIGGER}
            BEFORE DELETE ON {_TABLE}
            BEGIN
                SELECT RAISE(ABORT, '{_TABLE} is append-only');
            END
        """)
    elif bind.dialect.name == "postgresql":
        op.execute(f"""
            CREATE FUNCTION {_POSTGRES_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION '{_TABLE} is append-only';
                RETURN OLD;
            END;
            $$
        """)
        op.execute(f"""
            CREATE TRIGGER {_POSTGRES_UPDATE_TRIGGER}
            BEFORE UPDATE ON {_TABLE}
            FOR EACH ROW EXECUTE FUNCTION {_POSTGRES_FUNCTION}()
        """)
        op.execute(f"""
            CREATE TRIGGER {_POSTGRES_DELETE_TRIGGER}
            BEFORE DELETE ON {_TABLE}
            FOR EACH ROW EXECUTE FUNCTION {_POSTGRES_FUNCTION}()
        """)


def _drop_append_only_triggers(bind) -> None:
    if bind.dialect.name == "sqlite":
        op.execute(f"DROP TRIGGER IF EXISTS {_SQLITE_UPDATE_TRIGGER}")
        op.execute(f"DROP TRIGGER IF EXISTS {_SQLITE_DELETE_TRIGGER}")
    elif bind.dialect.name == "postgresql":
        op.execute(
            f"DROP TRIGGER IF EXISTS {_POSTGRES_UPDATE_TRIGGER} ON {_TABLE}"
        )
        op.execute(
            f"DROP TRIGGER IF EXISTS {_POSTGRES_DELETE_TRIGGER} ON {_TABLE}"
        )
        op.execute(f"DROP FUNCTION IF EXISTS {_POSTGRES_FUNCTION}()")


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
    op.create_index(
        _STATUS_LOOKUP_INDEX,
        _TABLE,
        ["environment", "event_type", "status", "completed_at", "id"],
        unique=False,
    )
    _create_append_only_triggers(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, _TABLE):
        return
    _drop_append_only_triggers(bind)
    op.drop_index(_STATUS_LOOKUP_INDEX, table_name=_TABLE)
    for column in reversed(_INDEX_COLUMNS):
        op.drop_index(f"ix_{_TABLE}_{column}", table_name=_TABLE)
    op.drop_table(_TABLE)
