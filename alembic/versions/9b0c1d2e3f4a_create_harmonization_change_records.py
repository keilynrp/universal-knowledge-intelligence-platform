"""Create harmonization_change_records table

Revision ID: 9b0c1d2e3f4a
Revises: 827dfb574843
Create Date: 2026-05-03 23:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '9b0c1d2e3f4a'
down_revision = '827dfb574843'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'harmonization_change_records',
        sa.Column('id',        sa.Integer(),  nullable=False),
        sa.Column('log_id',    sa.Integer(),  nullable=True),
        sa.Column('record_id', sa.Integer(),  nullable=True),
        sa.Column('field',     sa.String(),   nullable=True),
        sa.Column('old_value', sa.Text(),     nullable=True),
        sa.Column('new_value', sa.Text(),     nullable=True),
        sa.ForeignKeyConstraint(['log_id'],    ['harmonization_logs.id']),
        sa.ForeignKeyConstraint(['record_id'], ['raw_entities.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_harmonization_change_records_id',        'harmonization_change_records', ['id'],        unique=False)
    op.create_index('ix_harmonization_change_records_log_id',    'harmonization_change_records', ['log_id'],    unique=False)
    op.create_index('ix_harmonization_change_records_record_id', 'harmonization_change_records', ['record_id'], unique=False)


def downgrade():
    op.drop_index('ix_harmonization_change_records_record_id', table_name='harmonization_change_records')
    op.drop_index('ix_harmonization_change_records_log_id',    table_name='harmonization_change_records')
    op.drop_index('ix_harmonization_change_records_id',        table_name='harmonization_change_records')
    op.drop_table('harmonization_change_records')
