"""Add notes column to entity relationships.

Revision ID: a0b1c2d3e4f5
Revises: 9b0c1d2e3f4a
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa


revision = "a0b1c2d3e4f5"
down_revision = "9b0c1d2e3f4a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entity_relationships", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("entity_relationships", "notes")

