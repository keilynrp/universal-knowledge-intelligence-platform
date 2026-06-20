"""raw_entities.enrichment_issn_l for per-journal works count

Revision ID: c5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "c5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None

_TABLE = "raw_entities"
_COL = "enrichment_issn_l"
_IX = "ix_raw_entities_enrichment_issn_l"


def _has_column(bind, table: str, col: str) -> bool:
    return any(c["name"] == col for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, _TABLE, _COL):
        op.add_column(_TABLE, sa.Column(_COL, sa.String(), nullable=True))
        op.create_index(_IX, _TABLE, [_COL])

    rows = bind.execute(sa.text(
        "SELECT id, attributes_json FROM raw_entities "
        "WHERE attributes_json LIKE '%issn_l%'"
    )).fetchall()
    for row_id, raw in rows:
        if not raw:
            continue
        try:
            issn = json.loads(raw).get("issn_l")
        except (ValueError, TypeError):
            continue
        if issn:
            bind.execute(
                sa.text("UPDATE raw_entities SET enrichment_issn_l = :v WHERE id = :id"),
                {"v": issn, "id": row_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, _TABLE, _COL):
        op.drop_index(_IX, table_name=_TABLE)
        op.drop_column(_TABLE, _COL)
