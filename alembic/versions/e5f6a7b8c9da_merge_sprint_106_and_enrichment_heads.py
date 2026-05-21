"""merge sprint_106 and enrichment-scheduler heads

When the enrichment-scheduler migration (c2d3e4f5a6b8) was created, it was
chained from b1c2d3e4f5a7 (password_reset_tokens) — but a parallel branch
existed for sprint 106 (ending at d3e4f5a6b7c8). This left two heads, which
broke `alembic upgrade head` in production:

    head 1: d3e4f5a6b7c8 (sprint_106_llm_query_reformulation)
    head 2: d3e4f5a6b7c9 (enrichment_failure_reason)

This migration is a no-op merge that re-unifies the graph into a single head.

Revision ID: e5f6a7b8c9da
Revises: d3e4f5a6b7c8, d3e4f5a6b7c9
Create Date: 2026-05-21
"""
from alembic import op  # noqa: F401

revision = "e5f6a7b8c9da"
down_revision = ("d3e4f5a6b7c8", "d3e4f5a6b7c9")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op merge."""
    pass


def downgrade() -> None:
    """No-op merge — branches cannot be cleanly split again."""
    pass
