import sys
from pathlib import Path
import pytest
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# 添加api目录到Python路径
root = Path(__file__).resolve().parents[1]
root_str = str(root)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

# 导入模型
from models.user import User
from models.kb_document import KBDocument
from models.kb_conversation import KBConversation

# 测试数据库配置
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    # 只创建我们需要的表（不创建chunks表，因为SQLite不支持ARRAY/vector类型）
    User.__table__.create(bind=engine, checkfirst=True)
    KBDocument.__table__.create(bind=engine, checkfirst=True)
    KBConversation.__table__.create(bind=engine, checkfirst=True)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    # 创建测试用户
    test_user = User(
        id=uuid.uuid4(),
        account="test_admin",
        name="Test Admin",
        email="admin@test.com",
        password_hash="hashed_password",
        user_type="administrator",
        created_at=datetime.utcnow()
    )
    session.add(test_user)
    session.commit()
    
    yield session
    
    session.close()
    # 清理表
    KBConversation.__table__.drop(bind=engine, checkfirst=True)
    KBDocument.__table__.drop(bind=engine, checkfirst=True)
    User.__table__.drop(bind=engine, checkfirst=True)

