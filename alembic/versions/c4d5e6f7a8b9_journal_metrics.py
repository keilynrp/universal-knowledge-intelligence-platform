"""journal_metrics table for NIF + APC enrichment

Revision ID: c4d5e6f7a8b9
Revises: a8b9c0d1e2f3
Create Date: 2026-06-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None

_TABLE = "journal_metrics"


def _has_table(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, _TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("issn_l", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("two_yr_mean_citedness", sa.Float(), nullable=True),
        sa.Column("h_index", sa.Integer(), nullable=True),
        sa.Column("if_metric_kind", sa.String(), nullable=True),
        sa.Column("apc_usd", sa.Integer(), nullable=True),
        sa.Column("apc_currency", sa.String(), nullable=True),
        sa.Column("apc_source", sa.String(), nullable=True),
        sa.Column("is_in_doaj", sa.Boolean(), nullable=True),
        sa.Column("normalized_impact_factor", sa.Float(), nullable=True),
        sa.Column("nif_field", sa.String(), nullable=True),
        sa.Column("nif_updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("org_id", "issn_l", name="uq_journal_metric_org_issn"),
    )
    op.create_index("ix_journal_metrics_id", _TABLE, ["id"])
    op.create_index("ix_journal_metrics_issn_l", _TABLE, ["issn_l"])
    op.create_index("ix_journal_metrics_source_id", _TABLE, ["source_id"])
    op.create_index("ix_journal_metrics_org_id", _TABLE, ["org_id"])
    op.create_index(
        "ix_journal_metrics_normalized_impact_factor",
        _TABLE,
        ["normalized_impact_factor"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, _TABLE):
        return
    op.drop_index("ix_journal_metrics_normalized_impact_factor", table_name=_TABLE)
    op.drop_index("ix_journal_metrics_org_id", table_name=_TABLE)
    op.drop_index("ix_journal_metrics_source_id", table_name=_TABLE)
    op.drop_index("ix_journal_metrics_issn_l", table_name=_TABLE)
    op.drop_index("ix_journal_metrics_id", table_name=_TABLE)
    op.drop_table(_TABLE)
