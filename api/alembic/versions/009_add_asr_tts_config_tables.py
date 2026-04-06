"""add asr_config and tts_config tables

Revision ID: 009
Revises: 008
Create Date: 2026-01-31

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asr_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("api_endpoint", sa.String(255), nullable=False),
        sa.Column("api_key", sa.String(255), nullable=False),
        sa.Column("parameters", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "tts_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("api_endpoint", sa.String(255), nullable=False),
        sa.Column("api_key", sa.String(255), nullable=False),
        sa.Column("parameters", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("tts_config")
    op.drop_table("asr_config")

