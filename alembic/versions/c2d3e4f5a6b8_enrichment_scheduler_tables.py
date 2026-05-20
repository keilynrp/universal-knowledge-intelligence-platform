"""enrichment scheduler tables

Revision ID: c2d3e4f5a6b8
Revises: b1c2d3e4f5a7
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5a6b8"
down_revision = "b1c2d3e4f5a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = insp.get_table_names()

    if "domain_enrichment_policies" not in existing:
        op.create_table(
            "domain_enrichment_policies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("domain_id", sa.String(length=80), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("min_enrichment_pct", sa.Float(), nullable=False, server_default="80.0"),
            sa.Column("max_budget_per_run", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("staleness_threshold_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_domain_enrichment_policies_id", "domain_enrichment_policies", ["id"])
        op.create_index(
            "ix_domain_enrichment_policies_domain_id",
            "domain_enrichment_policies",
            ["domain_id"],
            unique=True,
        )

    if "enrichment_scheduler_runs" not in existing:
        op.create_table(
            "enrichment_scheduler_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("domain_id", sa.String(length=80), nullable=False),
            sa.Column("triggered_by", sa.String(length=20), nullable=False, server_default="scheduler"),
            sa.Column("queued_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )
        op.create_index("ix_enrichment_scheduler_runs_id", "enrichment_scheduler_runs", ["id"])
        op.create_index(
            "ix_enrichment_scheduler_runs_domain_id",
            "enrichment_scheduler_runs",
            ["domain_id"],
        )
        op.create_index(
            "ix_enrichment_scheduler_runs_started_at",
            "enrichment_scheduler_runs",
            ["started_at"],
        )


def downgrade() -> None:
    op.drop_table("enrichment_scheduler_runs")
    op.drop_table("domain_enrichment_policies")
