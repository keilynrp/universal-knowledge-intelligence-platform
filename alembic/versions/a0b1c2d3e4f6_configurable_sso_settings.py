"""configurable sso settings

Revision ID: a0b1c2d3e4f6
Revises: eng1prereq00001
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = "a0b1c2d3e4f6"
down_revision = "eng1prereq00001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "platform_auth_settings" not in insp.get_table_names():
        op.create_table(
            "platform_auth_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sso_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("sso_login_button_visible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("sso_provider_label", sa.String(), nullable=False, server_default="SSO"),
            sa.Column("sso_auto_provision", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("sso_default_role", sa.String(), nullable=False, server_default="viewer"),
            sa.Column("sso_allowed_domains", sa.Text(), nullable=False, server_default=""),
        )


def downgrade() -> None:
    op.drop_table("platform_auth_settings")
