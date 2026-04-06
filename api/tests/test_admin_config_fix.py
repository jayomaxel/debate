"""
测试管理员配置修复
验证配置服务能够正确处理空数据库的情况
"""
import pytest
import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, '.')

from database import Base
from models.config import ModelConfig, CozeConfig
from services.config_service import ConfigService


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    # 使用内存数据库进行测试
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


@pytest.mark.asyncio
async def test_get_model_config_creates_default_when_empty(db_session):
    """测试：当数据库为空时，get_model_config应该创建默认配置"""
    config_service = ConfigService(db_session)
    
    # 确认数据库中没有配置
    existing_config = db_session.execute(
        select(ModelConfig).limit(1)
    ).scalar_one_or_none()
    assert existing_config is None, "数据库应该为空"
    
    # 调用get_model_config
    config = await config_service.get_model_config()
    
    # 验证返回了配置
    assert config is not None, "应该返回配置对象"
    assert config.model_name == "gpt-3.5-turbo"
    assert config.api_endpoint == "https://api.openai.com/v1/chat/completions"
    assert config.temperature == 0.7
    assert config.max_tokens == 2000
    
    # 验证配置已保存到数据库
    saved_config = db_session.execute(
        select(ModelConfig).limit(1)
    ).scalar_one_or_none()
    assert saved_config is not None, "配置应该已保存到数据库"
    assert saved_config.id is not None, "配置应该有ID"
    assert saved_config.created_at is not None, "配置应该有创建时间"


@pytest.mark.asyncio
async def test_get_coze_config_creates_default_when_empty(db_session):
    """测试：当数据库为空时，get_coze_config应该创建默认配置"""
    config_service = ConfigService(db_session)
    
    # 确认数据库中没有配置
    existing_config = db_session.execute(
        select(CozeConfig).limit(1)
    ).scalar_one_or_none()
    assert existing_config is None, "数据库应该为空"
    
    # 调用get_coze_config
    config = await config_service.get_coze_config()
    
    # 验证返回了配置
    assert config is not None, "应该返回配置对象"
    assert config.agent_id == ""
    assert config.api_token == ""
    assert config.parameters == {}
    
    # 验证配置已保存到数据库
    saved_config = db_session.execute(
        select(CozeConfig).limit(1)
    ).scalar_one_or_none()
    assert saved_config is not None, "配置应该已保存到数据库"
    assert saved_config.id is not None, "配置应该有ID"
    assert saved_config.created_at is not None, "配置应该有创建时间"


@pytest.mark.asyncio
async def test_get_model_config_returns_existing(db_session):
    """测试：当数据库中有配置时，get_model_config应该返回现有配置"""
    config_service = ConfigService(db_session)
    
    # 创建一个配置
    existing_config = ModelConfig(
        model_name="gpt-4",
        api_endpoint="https://custom.api.com/v1",
        api_key="test-key",
        temperature=0.5,
        max_tokens=1000,
        parameters={"custom": "value"}
    )
    db_session.add(existing_config)
    db_session.commit()
    db_session.refresh(existing_config)
    
    # 调用get_model_config
    config = await config_service.get_model_config()
    
    # 验证返回了现有配置
    assert config.id == existing_config.id
    assert config.model_name == "gpt-4"
    assert config.api_endpoint == "https://custom.api.com/v1"
    assert config.api_key == "test-key"
    assert config.temperature == 0.5
    assert config.max_tokens == 1000


@pytest.mark.asyncio
async def test_update_model_config_creates_when_empty(db_session):
    """测试：当数据库为空时，update_model_config应该创建新配置"""
    config_service = ConfigService(db_session)
    
    # 调用update_model_config
    config = await config_service.update_model_config(
        model_name="claude-3",
        api_endpoint="https://api.anthropic.com/v1",
        api_key="test-key",
        temperature=0.8,
        max_tokens=3000
    )
    
    # 验证返回了配置
    assert config is not None
    assert config.model_name == "claude-3"
    assert config.api_endpoint == "https://api.anthropic.com/v1"
    assert config.api_key == "test-key"
    assert config.temperature == 0.8
    assert config.max_tokens == 3000
    
    # 验证配置已保存到数据库
    saved_config = db_session.execute(
        select(ModelConfig).limit(1)
    ).scalar_one_or_none()
    assert saved_config is not None
    assert saved_config.model_name == "claude-3"


@pytest.mark.asyncio
async def test_update_model_config_updates_existing(db_session):
    """测试：当数据库中有配置时，update_model_config应该更新现有配置"""
    config_service = ConfigService(db_session)
    
    # 创建一个配置
    existing_config = ModelConfig(
        model_name="gpt-3.5-turbo",
        api_endpoint="https://api.openai.com/v1",
        api_key="old-key",
        temperature=0.7,
        max_tokens=2000,
        parameters={}
    )
    db_session.add(existing_config)
    db_session.commit()
    db_session.refresh(existing_config)
    original_id = existing_config.id
    
    # 更新配置
    config = await config_service.update_model_config(
        model_name="gpt-4",
        api_key="new-key"
    )
    
    # 验证返回了更新后的配置
    assert config.id == original_id, "应该更新现有配置，而不是创建新配置"
    assert config.model_name == "gpt-4"
    assert config.api_key == "new-key"
    assert config.api_endpoint == "https://api.openai.com/v1", "未更新的字段应该保持不变"
    
    # 验证数据库中只有一个配置
    all_configs = db_session.execute(select(ModelConfig)).scalars().all()
    assert len(all_configs) == 1, "应该只有一个配置记录"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
