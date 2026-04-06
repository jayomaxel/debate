"""update coze config for multiple agents

Revision ID: 005
Revises: 004
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    更新 coze_config 表以支持多个 agent 配置
    - 将 agent_id 重命名为 debater_1_bot_id
    - 添加其他 5 个 bot ID 字段
    """
    # 重命名 agent_id 为 debater_1_bot_id
    op.alter_column('coze_config', 'agent_id', new_column_name='debater_1_bot_id')
    
    # 添加其他 bot ID 字段
    op.add_column('coze_config', sa.Column('debater_2_bot_id', sa.String(255), nullable=False, server_default=''))
    op.add_column('coze_config', sa.Column('debater_3_bot_id', sa.String(255), nullable=False, server_default=''))
    op.add_column('coze_config', sa.Column('debater_4_bot_id', sa.String(255), nullable=False, server_default=''))
    op.add_column('coze_config', sa.Column('judge_bot_id', sa.String(255), nullable=False, server_default=''))
    op.add_column('coze_config', sa.Column('mentor_bot_id', sa.String(255), nullable=False, server_default=''))


def downgrade() -> None:
    """
    回滚更改
    """
    # 删除新添加的字段
    op.drop_column('coze_config', 'mentor_bot_id')
    op.drop_column('coze_config', 'judge_bot_id')
    op.drop_column('coze_config', 'debater_4_bot_id')
    op.drop_column('coze_config', 'debater_3_bot_id')
    op.drop_column('coze_config', 'debater_2_bot_id')
    
    # 重命名回 agent_id
    op.alter_column('coze_config', 'debater_1_bot_id', new_column_name='agent_id')
