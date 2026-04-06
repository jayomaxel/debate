"""add debate participation role_reason

Revision ID: 008
Revises: 007
Create Date: 2026-01-31

"""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "debate_participations",
        sa.Column("role_reason", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("debate_participations", "role_reason")

