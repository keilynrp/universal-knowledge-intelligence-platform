"""Record which session or API key an audit row acted through.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-24

Phase 3 of the openspec change ``attribute-and-audit-reads`` (#375, #376).
The audit middleware used to name the actor by decoding the bearer token as a
JWT, so a mutation made with an API key had no actor at all, and a token whose
session had been revoked still lent its user's name to a refused request. Rows
now carry the principal authentication accepted: ``user_id`` (an existing
column that only the assistant-action endpoint had been filling), and one of
these two.

``session_id`` is indexed: "everything this session did" is the pivot an
incident needs once a session is known to be hostile.

``api_key_id`` has no foreign key on purpose. ``audit_logs`` is retained
indefinitely; a row must neither block the deletion of the key it names nor
disappear with it.
"""

import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("session_id", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("api_key_id", sa.Integer(), nullable=True))
    op.create_index("ix_audit_logs_session_id", "audit_logs", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_session_id", table_name="audit_logs")
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_column("api_key_id")
        batch.drop_column("session_id")
