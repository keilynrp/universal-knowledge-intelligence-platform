"""US-072 authority record links

Revision ID: d4e5f6a7b8c9
Revises: a0b1c2d3e4f5
Create Date: 2026-05-08 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "authority_record_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("source_authority_record_id", sa.Integer(), nullable=False),
        sa.Column("target_authority_record_id", sa.Integer(), nullable=False),
        sa.Column("link_type", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_authority_record_id"], ["authority_records.id"]),
        sa.ForeignKeyConstraint(["target_authority_record_id"], ["authority_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_authority_record_links_id"), "authority_record_links", ["id"], unique=False)
    op.create_index(op.f("ix_authority_record_links_org_id"), "authority_record_links", ["org_id"], unique=False)
    op.create_index(
        op.f("ix_authority_record_links_source_authority_record_id"),
        "authority_record_links",
        ["source_authority_record_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_authority_record_links_target_authority_record_id"),
        "authority_record_links",
        ["target_authority_record_id"],
        unique=False,
    )
    op.create_index(op.f("ix_authority_record_links_link_type"), "authority_record_links", ["link_type"], unique=False)
    op.create_index(op.f("ix_authority_record_links_status"), "authority_record_links", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_authority_record_links_status"), table_name="authority_record_links")
    op.drop_index(op.f("ix_authority_record_links_link_type"), table_name="authority_record_links")
    op.drop_index(op.f("ix_authority_record_links_target_authority_record_id"), table_name="authority_record_links")
    op.drop_index(op.f("ix_authority_record_links_source_authority_record_id"), table_name="authority_record_links")
    op.drop_index(op.f("ix_authority_record_links_org_id"), table_name="authority_record_links")
    op.drop_index(op.f("ix_authority_record_links_id"), table_name="authority_record_links")
    op.drop_table("authority_record_links")
