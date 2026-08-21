"""Allow AI debate participations without a user account.

Revision ID: 025
Revises: 024
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Human participants reference users, while generated AI participants are
    # represented by role + stance and intentionally have no user account.
    op.alter_column(
        "debate_participations",
        "user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    # AI-only rows cannot satisfy the historical NOT NULL contract.
    op.execute("DELETE FROM debate_participations WHERE user_id IS NULL")
    op.alter_column(
        "debate_participations",
        "user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
