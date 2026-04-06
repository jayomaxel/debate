"""
创建离线迁移脚本
当数据库未运行时使用此脚本生成迁移
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alembic.config import Config
from alembic import command

# 创建Alembic配置
alembic_cfg = Config("alembic.ini")

# 生成迁移脚本
try:
    command.revision(
        alembic_cfg,
        message="Initial migration - create all tables",
        autogenerate=False  # 手动模式，不需要连接数据库
    )
    print("✓ Migration script created successfully!")
    print("  Please edit the migration file in alembic/versions/")
except Exception as e:
    print(f"✗ Error creating migration: {e}")
