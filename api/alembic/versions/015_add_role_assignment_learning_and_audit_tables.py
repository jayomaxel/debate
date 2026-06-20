"""add role assignment learning and audit tables

Revision ID: 015
Revises: 014
Create Date: 2026-06-19

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    uuid_type = postgresql.UUID(as_uuid=True) if is_postgresql else sa.String(length=36)

    op.create_table(
        "debate_role_assignment_runs",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("parent_run_id", uuid_type, nullable=True),
        sa.Column("debate_id", uuid_type, nullable=True),
        sa.Column("reservation_id", uuid_type, nullable=True),
        sa.Column("class_id", uuid_type, nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("target_mode", sa.String(length=32), nullable=True),
        sa.Column("assignment_mode", sa.String(length=32), nullable=False),
        sa.Column("rotation_policy", sa.String(length=32), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("prompt_pack_version", sa.String(length=64), nullable=True),
        sa.Column("created_by", uuid_type, nullable=True),
        sa.Column("preview_token", sa.String(length=64), nullable=True),
        sa.Column("is_temporary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["parent_run_id"], ["debate_role_assignment_runs.id"]),
        sa.ForeignKeyConstraint(["debate_id"], ["debates.id"]),
        sa.ForeignKeyConstraint(["reservation_id"], ["debates.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("idx_role_assignment_runs_debate_created", "debate_role_assignment_runs", ["debate_id", "created_at"])
    op.create_index("idx_role_assignment_runs_reservation_created", "debate_role_assignment_runs", ["reservation_id", "created_at"])
    op.create_index("idx_role_assignment_runs_class_source_created", "debate_role_assignment_runs", ["class_id", "source", "created_at"])
    op.create_index("idx_role_assignment_runs_created_by", "debate_role_assignment_runs", ["created_by", "created_at"])
    op.create_index("idx_role_assignment_runs_preview", "debate_role_assignment_runs", ["preview_token"])

    op.create_table(
        "debate_role_assignment_items",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("assignment_source", sa.String(length=32), nullable=True),
        sa.Column("recommended_role", sa.String(length=32), nullable=True),
        sa.Column("assigned_role", sa.String(length=32), nullable=True),
        sa.Column("final_role", sa.String(length=32), nullable=True),
        sa.Column("teacher_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("fit_score", sa.Float(), nullable=True),
        sa.Column("rule_fit_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("fairness_penalty", sa.Float(), nullable=True),
        sa.Column("repeat_penalty", sa.Float(), nullable=True),
        sa.Column("imbalance_penalty", sa.Float(), nullable=True),
        sa.Column("growth_bonus", sa.Float(), nullable=True),
        sa.Column("model_score", sa.Float(), nullable=True),
        sa.Column("growth_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("dimension_contribution", sa.JSON(), nullable=True),
        sa.Column("feature_importance", sa.JSON(), nullable=True),
        sa.Column("model_basis", sa.JSON(), nullable=True),
        sa.Column("analysis_basis", sa.String(length=64), nullable=True),
        sa.Column("data_sources", sa.JSON(), nullable=True),
        sa.Column("standard_profile", sa.JSON(), nullable=True),
        sa.Column("historical_role_distribution", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["debate_role_assignment_runs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("idx_role_assignment_items_run_user", "debate_role_assignment_items", ["run_id", "user_id"])
    op.create_index("idx_role_assignment_items_run_final_role", "debate_role_assignment_items", ["run_id", "final_role"])

    op.create_table(
        "debate_role_assignment_audit_logs",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("run_id", uuid_type, nullable=True),
        sa.Column("debate_id", uuid_type, nullable=True),
        sa.Column("reservation_id", uuid_type, nullable=True),
        sa.Column("operator_id", uuid_type, nullable=True),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("from_role", sa.String(length=32), nullable=True),
        sa.Column("to_role", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["debate_role_assignment_runs.id"]),
        sa.ForeignKeyConstraint(["debate_id"], ["debates.id"]),
        sa.ForeignKeyConstraint(["reservation_id"], ["debates.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("idx_role_assignment_audit_run_created", "debate_role_assignment_audit_logs", ["run_id", "created_at"])
    op.create_index("idx_role_assignment_audit_debate_created", "debate_role_assignment_audit_logs", ["debate_id", "created_at"])
    op.create_index("idx_role_assignment_audit_reservation_created", "debate_role_assignment_audit_logs", ["reservation_id", "created_at"])
    op.create_index("idx_role_assignment_audit_user_created", "debate_role_assignment_audit_logs", ["user_id", "created_at"])

    op.create_table(
        "debate_role_performance_samples",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("debate_id", uuid_type, nullable=False),
        sa.Column("participation_id", uuid_type, nullable=True),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("class_id", uuid_type, nullable=True),
        sa.Column("assignment_run_id", uuid_type, nullable=True),
        sa.Column("assignment_item_id", uuid_type, nullable=True),
        sa.Column("sample_source", sa.String(length=32), nullable=False, server_default="completed_debate"),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("stance", sa.String(length=16), nullable=True),
        sa.Column("assignment_mode", sa.String(length=32), nullable=True),
        sa.Column("rotation_policy", sa.String(length=32), nullable=True),
        sa.Column("rule_fit_score", sa.Float(), nullable=True),
        sa.Column("model_score", sa.Float(), nullable=True),
        sa.Column("growth_score", sa.Float(), nullable=True),
        sa.Column("final_assignment_score", sa.Float(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("logic_score", sa.Float(), nullable=True),
        sa.Column("argument_score", sa.Float(), nullable=True),
        sa.Column("response_score", sa.Float(), nullable=True),
        sa.Column("persuasion_score", sa.Float(), nullable=True),
        sa.Column("teamwork_score", sa.Float(), nullable=True),
        sa.Column("speech_count", sa.Integer(), nullable=True),
        sa.Column("total_duration_sec", sa.Integer(), nullable=True),
        sa.Column("average_speech_length", sa.Float(), nullable=True),
        sa.Column("response_success_rate", sa.Float(), nullable=True),
        sa.Column("active_rounds", sa.Integer(), nullable=True),
        sa.Column("obvious_mistake_count", sa.Integer(), nullable=True),
        sa.Column("teacher_feedback", sa.Text(), nullable=True),
        sa.Column("student_reflection", sa.Text(), nullable=True),
        sa.Column("mentor_feedback", sa.Text(), nullable=True),
        sa.Column("report_summary", sa.Text(), nullable=True),
        sa.Column("standard_profile", sa.JSON(), nullable=True),
        sa.Column("historical_role_distribution", sa.JSON(), nullable=True),
        sa.Column("feature_vector", sa.JSON(), nullable=True),
        sa.Column("label_vector", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["debate_id"], ["debates.id"]),
        sa.ForeignKeyConstraint(["participation_id"], ["debate_participations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["assignment_run_id"], ["debate_role_assignment_runs.id"]),
        sa.ForeignKeyConstraint(["assignment_item_id"], ["debate_role_assignment_items.id"]),
    )
    op.create_index("idx_role_performance_samples_debate_user", "debate_role_performance_samples", ["debate_id", "user_id"])
    op.create_index("idx_role_performance_samples_role_created", "debate_role_performance_samples", ["role", "created_at"])
    op.create_index("idx_role_performance_samples_user_role", "debate_role_performance_samples", ["user_id", "role"])


def downgrade() -> None:
    op.drop_index("idx_role_performance_samples_user_role", table_name="debate_role_performance_samples")
    op.drop_index("idx_role_performance_samples_role_created", table_name="debate_role_performance_samples")
    op.drop_index("idx_role_performance_samples_debate_user", table_name="debate_role_performance_samples")
    op.drop_table("debate_role_performance_samples")

    op.drop_index("idx_role_assignment_audit_user_created", table_name="debate_role_assignment_audit_logs")
    op.drop_index("idx_role_assignment_audit_reservation_created", table_name="debate_role_assignment_audit_logs")
    op.drop_index("idx_role_assignment_audit_debate_created", table_name="debate_role_assignment_audit_logs")
    op.drop_index("idx_role_assignment_audit_run_created", table_name="debate_role_assignment_audit_logs")
    op.drop_table("debate_role_assignment_audit_logs")

    op.drop_index("idx_role_assignment_items_run_final_role", table_name="debate_role_assignment_items")
    op.drop_index("idx_role_assignment_items_run_user", table_name="debate_role_assignment_items")
    op.drop_table("debate_role_assignment_items")

    op.drop_index("idx_role_assignment_runs_preview", table_name="debate_role_assignment_runs")
    op.drop_index("idx_role_assignment_runs_created_by", table_name="debate_role_assignment_runs")
    op.drop_index("idx_role_assignment_runs_class_source_created", table_name="debate_role_assignment_runs")
    op.drop_index("idx_role_assignment_runs_reservation_created", table_name="debate_role_assignment_runs")
    op.drop_index("idx_role_assignment_runs_debate_created", table_name="debate_role_assignment_runs")
    op.drop_table("debate_role_assignment_runs")
