"""enrichment failure reason column and composite index

Revision ID: d3e4f5a6b7c9
Revises: c2d3e4f5a6b8
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c9"
down_revision = "c2d3e4f5a6b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [c["name"] for c in insp.get_columns("raw_entities")]

    if "enrichment_failure_reason" not in columns:
        op.add_column(
            "raw_entities",
            sa.Column("enrichment_failure_reason", sa.String(length=30), nullable=True),
        )

    # Composite index on (enrichment_source, enrichment_status)
    existing_indexes = [i["name"] for i in insp.get_indexes("raw_entities")]
    if "ix_re_source_status" not in existing_indexes:
        op.create_index(
            "ix_re_source_status",
            "raw_entities",
            ["enrichment_source", "enrichment_status"],
        )


def downgrade() -> None:
    op.drop_index("ix_re_source_status", table_name="raw_entities")
    op.drop_column("raw_entities", "enrichment_failure_reason")
