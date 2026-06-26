"""journal NIF bayesian columns

Revision ID: d6e7f8a9b0c1
Revises: c5e6f7a8b9c0
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d6e7f8a9b0c1"
down_revision = "c5e6f7a8b9c0"
branch_labels = None
depends_on = None

_COLS = [
    ("works_2yr", sa.Integer()),
    ("nif_bayes", sa.Float()),
    ("nif_ci_low", sa.Float()),
    ("nif_ci_high", sa.Float()),
    ("nif_bayes_updated_at", sa.DateTime()),
]


def _has_column(bind, table: str, col: str) -> bool:
    return col in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    for name, type_ in _COLS:
        if not _has_column(bind, "journal_metrics", name):
            op.add_column("journal_metrics", sa.Column(name, type_, nullable=True))
    existing_idx = {i["name"] for i in sa.inspect(bind).get_indexes("journal_metrics")}
    if "ix_journal_metrics_nif_bayes" not in existing_idx:
        op.create_index("ix_journal_metrics_nif_bayes", "journal_metrics", ["nif_bayes"])


def downgrade() -> None:
    bind = op.get_bind()
    existing_idx = {i["name"] for i in sa.inspect(bind).get_indexes("journal_metrics")}
    if "ix_journal_metrics_nif_bayes" in existing_idx:
        op.drop_index("ix_journal_metrics_nif_bayes", table_name="journal_metrics")
    for name, _ in _COLS:
        if _has_column(bind, "journal_metrics", name):
            op.drop_column("journal_metrics", name)
