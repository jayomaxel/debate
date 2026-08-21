"""add score provenance and analytics eligibility

Revision ID: 023
Revises: 022
Create Date: 2026-07-18

"""

from alembic import op
import sqlalchemy as sa


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "scores" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("scores")}
    additions = (
        ("status", sa.Column("status", sa.String(length=32), nullable=False, server_default="legacy_unknown")),
        ("scoring_source", sa.Column("scoring_source", sa.String(length=64), nullable=False, server_default="legacy_unknown")),
        ("scoring_quality", sa.Column("scoring_quality", sa.String(length=32), nullable=False, server_default="legacy_unknown")),
        ("retry_count", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0")),
        ("provider", sa.Column("provider", sa.String(length=64), nullable=True)),
        ("model", sa.Column("model", sa.String(length=128), nullable=True)),
        ("rubric_version", sa.Column("rubric_version", sa.String(length=64), nullable=True)),
        ("failure_code", sa.Column("failure_code", sa.String(length=64), nullable=True)),
        ("metadata", sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}")),
        ("eligible_for_analytics", sa.Column("eligible_for_analytics", sa.Boolean(), nullable=False, server_default=sa.false())),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("scores", column)

    op.execute(
        sa.text(
            """
            UPDATE scores
            SET status = CASE
                    WHEN lower(coalesce(feedback, '')) LIKE :fallback_en
                      OR coalesce(feedback, '') LIKE :fallback_zh
                    THEN 'fallback' ELSE 'legacy_unknown' END,
                scoring_source = CASE
                    WHEN lower(coalesce(feedback, '')) LIKE :fallback_en
                      OR coalesce(feedback, '') LIKE :fallback_zh
                    THEN 'fallback' ELSE 'legacy_unknown' END,
                scoring_quality = CASE
                    WHEN lower(coalesce(feedback, '')) LIKE :fallback_en
                      OR coalesce(feedback, '') LIKE :fallback_zh
                    THEN 'fallback' ELSE 'legacy_unknown' END,
                eligible_for_analytics = false
            """
        ).bindparams(
            fallback_en="%fallback score generated%",
            fallback_zh="%评分系统暂时不可用%",
        )
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                UPDATE scores AS score
                SET status = 'fallback',
                    scoring_source = 'fallback',
                    scoring_quality = 'fallback',
                    eligible_for_analytics = false
                FROM speeches AS speech
                JOIN debates AS debate ON debate.id = speech.debate_id
                WHERE score.speech_id = speech.id
                  AND (
                    lower(coalesce(debate.report -> 'report_meta' ->> 'scoring_quality', ''))
                        IN ('fallback', 'partial')
                    OR lower(coalesce(debate.report ->> 'score_fallback_generated', 'false')) = 'true'
                  )
                """
            )
        )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("scores")}
    if "idx_scores_analytics_eligible" not in indexes:
        op.create_index("idx_scores_analytics_eligible", "scores", ["eligible_for_analytics", "participation_id"], unique=False)
    if "idx_scores_status" not in indexes:
        op.create_index("idx_scores_status", "scores", ["status"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        constraints = {constraint["name"] for constraint in sa.inspect(op.get_bind()).get_check_constraints("scores")}
        if "ck_scores_status" not in constraints:
            op.create_check_constraint(
                "ck_scores_status",
                "scores",
                "status IN ('validated', 'repaired', 'fallback', 'failed', 'legacy_unknown')",
            )
        if "ck_scores_analytics_eligibility" not in constraints:
            op.create_check_constraint(
                "ck_scores_analytics_eligibility",
                "scores",
                "eligible_for_analytics = false OR status IN ('validated', 'repaired')",
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "scores" not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes("scores")}
    if op.get_bind().dialect.name == "postgresql":
        constraints = {constraint["name"] for constraint in inspector.get_check_constraints("scores")}
        for constraint_name in ("ck_scores_analytics_eligibility", "ck_scores_status"):
            if constraint_name in constraints:
                op.drop_constraint(constraint_name, "scores", type_="check")
    for index_name in ("idx_scores_analytics_eligible", "idx_scores_status"):
        if index_name in indexes:
            op.drop_index(index_name, table_name="scores")
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("scores")}
    for column_name in (
        "eligible_for_analytics", "metadata", "failure_code", "rubric_version",
        "model", "provider", "retry_count", "scoring_quality", "scoring_source", "status",
    ):
        if column_name in columns:
            op.drop_column("scores", column_name)
