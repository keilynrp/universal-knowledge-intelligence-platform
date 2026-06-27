"""add enrichment_work_type to raw_entities

Revision ID: e6f7a8b9c0d2
Revises: d6e7f8a9b0c1
Branch labels: None
Depends on: None
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, col: str) -> bool:
    return col in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "raw_entities", "enrichment_work_type"):
        with op.batch_alter_table("raw_entities") as batch:
            batch.add_column(sa.Column("enrichment_work_type", sa.String(), nullable=True))
    existing_idx = {i["name"] for i in sa.inspect(bind).get_indexes("raw_entities")}
    if "ix_raw_entities_enrichment_work_type" not in existing_idx:
        op.create_index("ix_raw_entities_enrichment_work_type", "raw_entities", ["enrichment_work_type"])


def downgrade() -> None:
    bind = op.get_bind()
    existing_idx = {i["name"] for i in sa.inspect(bind).get_indexes("raw_entities")}
    if "ix_raw_entities_enrichment_work_type" in existing_idx:
        op.drop_index("ix_raw_entities_enrichment_work_type", table_name="raw_entities")
    if _has_column(bind, "raw_entities", "enrichment_work_type"):
        with op.batch_alter_table("raw_entities") as batch:
            batch.drop_column("enrichment_work_type")
