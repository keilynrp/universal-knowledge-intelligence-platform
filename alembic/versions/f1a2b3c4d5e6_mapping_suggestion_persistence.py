"""Persist mapping suggestions and field correspondence rules

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9da
Create Date: 2026-05-26 02:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "e5f6a7b8c9da"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mapping_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("source_format", sa.String(), nullable=True),
        sa.Column("source_schema", sa.String(), nullable=True),
        sa.Column("source_field", sa.String(), nullable=False),
        sa.Column("canonical_target", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("evidence_samples", sa.Text(), nullable=True),
        sa.Column("semantic_concept", sa.String(), nullable=True),
        sa.Column("identifier_scheme", sa.String(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("requires_review", sa.Boolean(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "id", "org_id", "import_batch_id", "source_id", "source_format",
        "source_schema", "source_field", "canonical_target", "status",
        "semantic_concept", "identifier_scheme", "requires_review",
        "reviewer_id", "superseded_by", "created_at",
    ):
        op.create_index(f"ix_mapping_suggestions_{column}", "mapping_suggestions", [column], unique=False)

    op.create_table(
        "field_correspondence_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("source_schema", sa.String(), nullable=True),
        sa.Column("source_field", sa.String(), nullable=False),
        sa.Column("canonical_target", sa.String(), nullable=True),
        sa.Column("semantic_concept", sa.String(), nullable=True),
        sa.Column("identifier_scheme", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_from_suggestion_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_from_suggestion_id"], ["mapping_suggestions.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "source_schema", "source_field", name="uq_field_correspondence_rule_scope"),
    )
    for column in (
        "id", "org_id", "source_schema", "source_field", "canonical_target",
        "semantic_concept", "identifier_scheme", "is_active",
        "created_from_suggestion_id", "created_by_id", "created_at",
    ):
        op.create_index(
            f"ix_field_correspondence_rules_{column}",
            "field_correspondence_rules",
            [column],
            unique=False,
        )


def downgrade():
    for column in (
        "created_at", "created_by_id", "created_from_suggestion_id", "is_active",
        "identifier_scheme", "semantic_concept", "canonical_target",
        "source_field", "source_schema", "org_id", "id",
    ):
        op.drop_index(f"ix_field_correspondence_rules_{column}", table_name="field_correspondence_rules")
    op.drop_table("field_correspondence_rules")

    for column in (
        "created_at", "superseded_by", "reviewer_id", "requires_review",
        "identifier_scheme", "semantic_concept", "status", "canonical_target",
        "source_field", "source_schema", "source_format", "source_id",
        "import_batch_id", "org_id", "id",
    ):
        op.drop_index(f"ix_mapping_suggestions_{column}", table_name="mapping_suggestions")
    op.drop_table("mapping_suggestions")
