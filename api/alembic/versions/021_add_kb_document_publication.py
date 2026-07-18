"""add explicit knowledge document publication state

Revision ID: 021
Revises: 020
Create Date: 2026-07-18

"""

from alembic import op
import sqlalchemy as sa


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "kb_documents" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("kb_documents")}
    if "is_published" not in columns:
        op.add_column(
            "kb_documents",
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index(
            "idx_kb_documents_published_status",
            "kb_documents",
            ["is_published", "upload_status"],
            unique=False,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "kb_documents" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("kb_documents")}
    indexes = {index["name"] for index in inspector.get_indexes("kb_documents")}
    if "idx_kb_documents_published_status" in indexes:
        op.drop_index("idx_kb_documents_published_status", table_name="kb_documents")
    if "is_published" in columns:
        op.drop_column("kb_documents", "is_published")
