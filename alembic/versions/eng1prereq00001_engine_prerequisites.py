"""Engine prerequisites: unique constraints + updated_at

Revision ID: eng1prereq00001
Revises: e5f6a7b8c9d0
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = 'eng1prereq00001'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('raw_entities', sa.Column('updated_at', sa.DateTime(), nullable=True))
    # Partial unique indexes — PostgreSQL only (SQLite ignores WHERE clause)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_entities_canonical
        ON raw_entities (org_id, domain, entity_type, canonical_id)
        WHERE org_id IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_entities_canonical_global
        ON raw_entities (domain, entity_type, canonical_id)
        WHERE org_id IS NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relationships_pair
        ON entity_relationships (org_id, source_id, target_id, relation_type)
        WHERE org_id IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relationships_pair_global
        ON entity_relationships (source_id, target_id, relation_type)
        WHERE org_id IS NULL
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_entity_relationships_pair_global")
    op.execute("DROP INDEX IF EXISTS uq_entity_relationships_pair")
    op.execute("DROP INDEX IF EXISTS uq_raw_entities_canonical_global")
    op.execute("DROP INDEX IF EXISTS uq_raw_entities_canonical")
    op.drop_column('raw_entities', 'updated_at')
