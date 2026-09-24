"""Index the audit log by client address.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-24

The first incident tabletop (2026-09-22) had one solid pivot, an unfamiliar
address in the container log, and no way to ask the audit log what else that
address had done (#378). ``GET /audit-log`` now filters on ``ip_address``, and
without an index that filter scans a table that only ever grows, at the moment
the answer is most urgent.
"""

from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_audit_logs_ip_address", "audit_logs", ["ip_address"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_ip_address", table_name="audit_logs")
