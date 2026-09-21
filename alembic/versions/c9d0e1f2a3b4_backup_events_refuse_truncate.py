"""Refuse TRUNCATE on backup_assurance_events.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-21

The table is append-only by trigger, but both triggers are ``FOR EACH ROW``,
and row-level triggers never fire on TRUNCATE: one statement emptied the
evidence table on PostgreSQL 18 while the same table refused every UPDATE and
DELETE (#363). This adds a statement-level ``BEFORE TRUNCATE`` trigger calling
the same function, which raises.

No row is read or written. SQLite has no TRUNCATE, so this is a no-op there.

``CREATE OR REPLACE`` keeps the upgrade safe on a database whose table was
created by ``create_all`` with the new models, which registers this trigger
itself (backend/models.py).
"""

from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None

_TABLE = "backup_assurance_events"
_FUNCTION = "reject_backup_assurance_event_mutation"
_TRIGGER = "trg_backup_assurance_events_no_truncate"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        f"CREATE OR REPLACE TRIGGER {_TRIGGER} "
        f"BEFORE TRUNCATE ON {_TABLE} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {_FUNCTION}()"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER} ON {_TABLE}")
