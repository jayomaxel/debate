"""add authoritative realtime debate states

Revision ID: 022
Revises: 021
Create Date: 2026-07-18

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def _uuid_type():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "debate_runtime_states" in inspector.get_table_names():
        return
    op.create_table(
        "debate_runtime_states",
        sa.Column("room_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "debate_id",
            _uuid_type(),
            sa.ForeignKey("debates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_debate_runtime_states_debate", "debate_runtime_states", ["debate_id"], unique=True)
    op.create_index("idx_debate_runtime_states_lease", "debate_runtime_states", ["lease_expires_at"], unique=False)


def downgrade() -> None:
    if "debate_runtime_states" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("debate_runtime_states")
