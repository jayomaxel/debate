"""add assessment score columns (0-100)

Revision ID: 006
Revises: 443e53534175
Create Date: 2026-01-31

"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "443e53534175"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ability_assessments", sa.Column("expression_willingness_score", sa.Integer(), nullable=True))
    op.add_column("ability_assessments", sa.Column("logical_thinking_score", sa.Integer(), nullable=True))
    op.add_column("ability_assessments", sa.Column("stablecoin_knowledge_score", sa.Integer(), nullable=True))
    op.add_column("ability_assessments", sa.Column("financial_knowledge_score", sa.Integer(), nullable=True))
    op.add_column("ability_assessments", sa.Column("critical_thinking_score", sa.Integer(), nullable=True))

    op.execute(
        "UPDATE ability_assessments "
        "SET logical_thinking_score = logical_thinking * 10 "
        "WHERE logical_thinking_score IS NULL"
    )
    op.execute(
        "UPDATE ability_assessments "
        "SET expression_willingness_score = expression_willingness * 10 "
        "WHERE expression_willingness_score IS NULL"
    )
    op.execute(
        "UPDATE ability_assessments "
        "SET stablecoin_knowledge_score = 50 "
        "WHERE stablecoin_knowledge_score IS NULL"
    )
    op.execute(
        "UPDATE ability_assessments "
        "SET financial_knowledge_score = 50 "
        "WHERE financial_knowledge_score IS NULL"
    )
    op.execute(
        "UPDATE ability_assessments "
        "SET critical_thinking_score = 50 "
        "WHERE critical_thinking_score IS NULL"
    )


def downgrade() -> None:
    op.drop_column("ability_assessments", "critical_thinking_score")
    op.drop_column("ability_assessments", "financial_knowledge_score")
    op.drop_column("ability_assessments", "stablecoin_knowledge_score")
    op.drop_column("ability_assessments", "logical_thinking_score")
    op.drop_column("ability_assessments", "expression_willingness_score")

