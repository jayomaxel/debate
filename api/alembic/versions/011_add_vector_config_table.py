"""add vector_config table

Revision ID: 011
Revises: 010
Create Date: 2026-02-09

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vector_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("api_endpoint", sa.String(255), nullable=False),
        sa.Column("api_key", sa.String(255), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False, server_default="1536"),
        sa.Column("parameters", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("vector_config")
