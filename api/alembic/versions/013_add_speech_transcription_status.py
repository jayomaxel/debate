"""add speech transcription status fields

Revision ID: 013
Revises: 012
Create Date: 2026-05-02

"""

from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("speeches", sa.Column("transcription_status", sa.String(20), nullable=True))
    op.add_column("speeches", sa.Column("transcription_error", sa.Text(), nullable=True))
    op.add_column(
        "speeches",
        sa.Column("is_valid_for_scoring", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.execute(
        "UPDATE speeches "
        "SET transcription_status = 'failed', is_valid_for_scoring = false "
        "WHERE (content IS NULL OR trim(content) = '') AND audio_url IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("speeches", "is_valid_for_scoring")
    op.drop_column("speeches", "transcription_error")
    op.drop_column("speeches", "transcription_status")
