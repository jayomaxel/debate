'''add support document tags and summary fields

Revision ID: 017
Revises: 016
Create Date: 2026-07-17
'''

from alembic import op
import sqlalchemy as sa


revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('purpose_tag', sa.String(length=32), nullable=False, server_default='optional'))
    op.add_column('documents', sa.Column('processing_status', sa.String(length=32), nullable=False, server_default='pending'))
    op.add_column('documents', sa.Column('summary_status', sa.String(length=32), nullable=False, server_default='pending'))
    op.add_column('documents', sa.Column('summary_payload', sa.JSON(), nullable=True))
    op.add_column('documents', sa.Column('summary_quality', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'summary_quality')
    op.drop_column('documents', 'summary_payload')
    op.drop_column('documents', 'summary_status')
    op.drop_column('documents', 'processing_status')
    op.drop_column('documents', 'purpose_tag')
