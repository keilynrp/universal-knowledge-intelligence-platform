"""Create link_dismissals table for Entity Linker

Revision ID: 827dfb574843
Revises: f9a0b1c2d3e4
Create Date: 2026-05-03 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '827dfb574843'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'link_dismissals',
        sa.Column('id',          sa.Integer(),  nullable=False),
        sa.Column('entity_a_id', sa.Integer(),  nullable=False),
        sa.Column('entity_b_id', sa.Integer(),  nullable=False),
        sa.Column('created_at',  sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_link_dismissals_id',          'link_dismissals', ['id'],          unique=False)
    op.create_index('ix_link_dismissals_entity_a_id', 'link_dismissals', ['entity_a_id'], unique=False)
    op.create_index('ix_link_dismissals_entity_b_id', 'link_dismissals', ['entity_b_id'], unique=False)


def downgrade():
    op.drop_index('ix_link_dismissals_entity_b_id', table_name='link_dismissals')
    op.drop_index('ix_link_dismissals_entity_a_id', table_name='link_dismissals')
    op.drop_index('ix_link_dismissals_id',          table_name='link_dismissals')
    op.drop_table('link_dismissals')
