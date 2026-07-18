'''align teaching design storage with the frozen contract

Revision ID: 018
Revises: 017
Create Date: 2026-07-18
'''

from alembic import op
import sqlalchemy as sa


revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('class_teaching_design_versions', sa.Column('extraction_result', sa.JSON(), nullable=True))
    op.add_column('class_teaching_design_versions', sa.Column('confidence', sa.JSON(), nullable=True))
    op.add_column('class_teaching_design_versions', sa.Column('missing_fields', sa.JSON(), nullable=True))
    op.add_column('class_teaching_design_versions', sa.Column('source_excerpt_map', sa.JSON(), nullable=True))
    op.add_column(
        'class_teaching_design_versions',
        sa.Column('status', sa.String(length=32), nullable=False, server_default='needs_review'),
    )


def downgrade() -> None:
    op.drop_column('class_teaching_design_versions', 'status')
    op.drop_column('class_teaching_design_versions', 'source_excerpt_map')
    op.drop_column('class_teaching_design_versions', 'missing_fields')
    op.drop_column('class_teaching_design_versions', 'confidence')
    op.drop_column('class_teaching_design_versions', 'extraction_result')
