"""Single-use codes for the SSO redirect.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-27

#408. The SSO callback redirected to ``/login?token=<access>&refresh=<refresh>``,
which put a 7-day refresh token in browser history, in ``Referer`` and in any
proxy access log. It now redirects with a code that is valid for 60 seconds and
spent on first use; this table holds its hash until the browser exchanges it.
"""

import sqlalchemy as sa
from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sso_login_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sso_login_codes_id", "sso_login_codes", ["id"])
    op.create_index("ix_sso_login_codes_user_id", "sso_login_codes", ["user_id"])
    op.create_index("ix_sso_login_codes_code_hash", "sso_login_codes", ["code_hash"], unique=True)
    op.create_index("ix_sso_login_codes_expires_at", "sso_login_codes", ["expires_at"])


def downgrade() -> None:
    op.drop_table("sso_login_codes")
