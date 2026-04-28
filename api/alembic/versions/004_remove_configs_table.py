"""remove configs table

Revision ID: 004
Revises: 003
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    删除旧的 configs 表
    配置管理已迁移至 model_config 和 coze_config 表
    """
    # 删除 configs 表
    op.drop_table('configs')


def downgrade() -> None:
    """
    恢复 configs 表（如果需要回滚）
    """
    op.create_table(
        'configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )
