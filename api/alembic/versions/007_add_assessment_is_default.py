"""add assessment is_default flag

Revision ID: 007
Revises: 006
Create Date: 2026-01-31

"""

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ability_assessments",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("ability_assessments", "is_default")

