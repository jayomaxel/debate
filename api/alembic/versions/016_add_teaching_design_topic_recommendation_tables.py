"""add teaching design and topic recommendation tables

Revision ID: 016
Revises: 015
Create Date: 2026-07-07

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def _uuid_type():
    bind = op.get_bind()
    return postgresql.UUID(as_uuid=True) if bind.dialect.name == "postgresql" else sa.String(length=36)


def upgrade() -> None:
    uuid_type = _uuid_type()

    op.create_table(
        "class_teaching_design_versions",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("class_id", uuid_type, nullable=False),
        sa.Column("created_by", uuid_type, nullable=True),
        sa.Column("derived_from_version_id", uuid_type, nullable=True),
        sa.Column("version_name", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("source_file_type", sa.String(length=64), nullable=True),
        sa.Column("source_file_size", sa.Integer(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("extracted_payload", sa.JSON(), nullable=True),
        sa.Column("extraction_status", sa.String(length=32), nullable=False, server_default="partial"),
        sa.Column("correction_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["derived_from_version_id"], ["class_teaching_design_versions.id"]),
    )
    op.create_index(
        "idx_teaching_design_class_active",
        "class_teaching_design_versions",
        ["class_id", "is_active", "created_at"],
    )
    op.create_index(
        "idx_teaching_design_class_version",
        "class_teaching_design_versions",
        ["class_id", "version_name"],
    )

    op.create_table(
        "topic_recommendation_runs",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("parent_run_id", uuid_type, nullable=True),
        sa.Column("class_id", uuid_type, nullable=False),
        sa.Column("teaching_design_version_id", uuid_type, nullable=True),
        sa.Column("created_by", uuid_type, nullable=True),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="competition"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column("teaching_design_status", sa.String(length=32), nullable=False, server_default="partial"),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="fallback"),
        sa.Column("generation_quality", sa.String(length=32), nullable=False, server_default="fallback"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("preferred_count", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("difficulty_preference", sa.String(length=16), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["parent_run_id"], ["topic_recommendation_runs.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["teaching_design_version_id"], ["class_teaching_design_versions.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index(
        "idx_topic_recommendation_runs_class_created",
        "topic_recommendation_runs",
        ["class_id", "created_at"],
    )
    op.create_index(
        "idx_topic_recommendation_runs_design_created",
        "topic_recommendation_runs",
        ["teaching_design_version_id", "created_at"],
    )
    op.create_index(
        "idx_topic_recommendation_runs_creator_created",
        "topic_recommendation_runs",
        ["created_by", "created_at"],
    )

    op.create_table(
        "topic_recommendation_items",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("candidate_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("topic_text", sa.Text(), nullable=False),
        sa.Column("course_objectives", sa.JSON(), nullable=True),
        sa.Column("knowledge_points", sa.JSON(), nullable=True),
        sa.Column("classroom_scene", sa.String(length=255), nullable=True),
        sa.Column("debatability_reason", sa.Text(), nullable=True),
        sa.Column("difficulty_level", sa.String(length=16), nullable=True),
        sa.Column("recommendation_reason", sa.Text(), nullable=True),
        sa.Column("source_basis", sa.JSON(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("quality_flags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["run_id"], ["topic_recommendation_runs.id"]),
    )
    op.create_index(
        "idx_topic_recommendation_items_run_order",
        "topic_recommendation_items",
        ["run_id", "candidate_order"],
    )


def downgrade() -> None:
    op.drop_index("idx_topic_recommendation_items_run_order", table_name="topic_recommendation_items")
    op.drop_table("topic_recommendation_items")

    op.drop_index("idx_topic_recommendation_runs_creator_created", table_name="topic_recommendation_runs")
    op.drop_index("idx_topic_recommendation_runs_design_created", table_name="topic_recommendation_runs")
    op.drop_index("idx_topic_recommendation_runs_class_created", table_name="topic_recommendation_runs")
    op.drop_table("topic_recommendation_runs")

    op.drop_index("idx_teaching_design_class_version", table_name="class_teaching_design_versions")
    op.drop_index("idx_teaching_design_class_active", table_name="class_teaching_design_versions")
    op.drop_table("class_teaching_design_versions")
