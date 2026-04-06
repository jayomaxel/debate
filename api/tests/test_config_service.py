"""
Test ConfigService - verify model and Coze configuration management
"""
import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.config import ModelConfig, CozeConfig
from services.config_service import ConfigService
from database import Base
import uuid

# Create in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def config_service(db_session):
    """Create a ConfigService instance"""
    return ConfigService(db_session)


# ============================================================================
# Model Configuration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_model_config_returns_default_if_none_exists(config_service):
    """Test that get_model_config returns default configuration when none exists in database"""
    config = await config_service.get_model_config()
    
    assert config is not None
    assert config.model_name == "gpt-3.5-turbo"
    assert config.api_endpoint == "https://api.openai.com/v1/chat/completions"
    assert config.api_key == ""
    assert config.temperature == 0.7
    assert config.max_tokens == 2000
    assert config.parameters == {}


@pytest.mark.asyncio
async def test_get_model_config_returns_existing_config(config_service, db_session):
    """Test that get_model_config returns existing configuration from database"""
    # Create a configuration in the database
    existing_config = ModelConfig(
        id=uuid.uuid4(),
        model_name="gpt-4",
        api_endpoint="https://custom.api.com/v1",
        api_key="test_key_123",
        temperature=0.8,
        max_tokens=3000,
        parameters={"top_p": 0.9}
    )
    db_session.add(existing_config)
    db_session.commit()
    
    # Retrieve the configuration
    config = await config_service.get_model_config()
    
    assert config is not None
    assert config.model_name == "gpt-4"
    assert config.api_endpoint == "https://custom.api.com/v1"
    assert config.api_key == "test_key_123"
    assert config.temperature == 0.8
    assert config.max_tokens == 3000
    assert config.parameters == {"top_p": 0.9}


@pytest.mark.asyncio
async def test_update_model_config_creates_new_config(config_service, db_session):
    """Test that update_model_config creates new configuration when none exists"""
    config = await config_service.update_model_config(
        model_name="gpt-4-turbo",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="new_api_key",
        temperature=0.9,
        max_tokens=4000,
        parameters={"top_p": 0.95}
    )
    
    assert config is not None
    assert config.model_name == "gpt-4-turbo"
    assert config.api_endpoint == "https://api.openai.com/v1/chat/completions"
    assert config.api_key == "new_api_key"
    assert config.temperature == 0.9
    assert config.max_tokens == 4000
    assert config.parameters == {"top_p": 0.95}
    
    # Verify it was saved to database
    retrieved_config = db_session.query(ModelConfig).first()
    assert retrieved_config is not None
    assert retrieved_config.model_name == "gpt-4-turbo"


@pytest.mark.asyncio
async def test_update_model_config_updates_existing_config(config_service, db_session):
    """Test that update_model_config updates existing configuration"""
    # Create initial configuration
    initial_config = ModelConfig(
        id=uuid.uuid4(),
        model_name="gpt-3.5-turbo",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="old_key",
        temperature=0.7,
        max_tokens=2000
    )
    db_session.add(initial_config)
    db_session.commit()
    
    # Update the configuration
    updated_config = await config_service.update_model_config(
        model_name="gpt-4",
        api_key="new_key",
        temperature=0.9
    )
    
    assert updated_config.model_name == "gpt-4"
    assert updated_config.api_key == "new_key"
    assert updated_config.temperature == 0.9
    # Unchanged fields should remain the same
    assert updated_config.api_endpoint == "https://api.openai.com/v1/chat/completions"
    assert updated_config.max_tokens == 2000
    
    # Verify only one config exists in database
    all_configs = db_session.query(ModelConfig).all()
    assert len(all_configs) == 1


@pytest.mark.asyncio
async def test_update_model_config_partial_update(config_service, db_session):
    """Test that update_model_config only updates provided fields"""
    # Create initial configuration
    initial_config = ModelConfig(
        id=uuid.uuid4(),
        model_name="gpt-3.5-turbo",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="original_key",
        temperature=0.7,
        max_tokens=2000,
        parameters={"top_p": 0.9}
    )
    db_session.add(initial_config)
    db_session.commit()
    
    # Update only the temperature
    updated_config = await config_service.update_model_config(temperature=0.5)
    
    # Only temperature should change
    assert updated_config.temperature == 0.5
    # Other fields should remain unchanged
    assert updated_config.model_name == "gpt-3.5-turbo"
    assert updated_config.api_endpoint == "https://api.openai.com/v1/chat/completions"
    assert updated_config.api_key == "original_key"
    assert updated_config.max_tokens == 2000
    assert updated_config.parameters == {"top_p": 0.9}


# ============================================================================
# Coze Configuration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_coze_config_returns_default_if_none_exists(config_service):
    """Test that get_coze_config returns default configuration when none exists in database"""
    config = await config_service.get_coze_config()
    
    assert config is not None
    assert config.agent_id == ""
    assert config.api_token == ""
    assert config.parameters == {}


@pytest.mark.asyncio
async def test_get_coze_config_returns_existing_config(config_service, db_session):
    """Test that get_coze_config returns existing configuration from database"""
    # Create a configuration in the database
    existing_config = CozeConfig(
        id=uuid.uuid4(),
        agent_id="agent_123",
        api_token="token_xyz",
        parameters={"timeout": 30, "retry": 3}
    )
    db_session.add(existing_config)
    db_session.commit()
    
    # Retrieve the configuration
    config = await config_service.get_coze_config()
    
    assert config is not None
    assert config.agent_id == "agent_123"
    assert config.api_token == "token_xyz"
    assert config.parameters == {"timeout": 30, "retry": 3}


@pytest.mark.asyncio
async def test_update_coze_config_creates_new_config(config_service, db_session):
    """Test that update_coze_config creates new configuration when none exists"""
    config = await config_service.update_coze_config(
        agent_id="new_agent_456",
        api_token="new_token_abc",
        parameters={"max_retries": 5}
    )
    
    assert config is not None
    assert config.agent_id == "new_agent_456"
    assert config.api_token == "new_token_abc"
    assert config.parameters == {"max_retries": 5}
    
    # Verify it was saved to database
    retrieved_config = db_session.query(CozeConfig).first()
    assert retrieved_config is not None
    assert retrieved_config.agent_id == "new_agent_456"


@pytest.mark.asyncio
async def test_update_coze_config_updates_existing_config(config_service, db_session):
    """Test that update_coze_config updates existing configuration"""
    # Create initial configuration
    initial_config = CozeConfig(
        id=uuid.uuid4(),
        agent_id="old_agent",
        api_token="old_token",
        parameters={"timeout": 10}
    )
    db_session.add(initial_config)
    db_session.commit()
    
    # Update the configuration
    updated_config = await config_service.update_coze_config(
        agent_id="new_agent",
        api_token="new_token"
    )
    
    assert updated_config.agent_id == "new_agent"
    assert updated_config.api_token == "new_token"
    # Unchanged fields should remain the same
    assert updated_config.parameters == {"timeout": 10}
    
    # Verify only one config exists in database
    all_configs = db_session.query(CozeConfig).all()
    assert len(all_configs) == 1


@pytest.mark.asyncio
async def test_update_coze_config_partial_update(config_service, db_session):
    """Test that update_coze_config only updates provided fields"""
    # Create initial configuration
    initial_config = CozeConfig(
        id=uuid.uuid4(),
        agent_id="agent_123",
        api_token="token_xyz",
        parameters={"timeout": 30, "retry": 3}
    )
    db_session.add(initial_config)
    db_session.commit()
    
    # Update only the parameters
    updated_config = await config_service.update_coze_config(
        parameters={"timeout": 60, "retry": 5, "new_param": "value"}
    )
    
    # Only parameters should change
    assert updated_config.parameters == {"timeout": 60, "retry": 5, "new_param": "value"}
    # Other fields should remain unchanged
    assert updated_config.agent_id == "agent_123"
    assert updated_config.api_token == "token_xyz"


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_update_model_config_with_none_values(config_service, db_session):
    """Test that update_model_config handles None values correctly (should not update)"""
    # Create initial configuration
    initial_config = ModelConfig(
        id=uuid.uuid4(),
        model_name="gpt-4",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_key",
        temperature=0.8,
        max_tokens=3000
    )
    db_session.add(initial_config)
    db_session.commit()
    
    # Update with None values (should not change anything)
    updated_config = await config_service.update_model_config(
        model_name=None,
        api_key=None,
        temperature=None
    )
    
    # All fields should remain unchanged
    assert updated_config.model_name == "gpt-4"
    assert updated_config.api_key == "test_key"
    assert updated_config.temperature == 0.8


@pytest.mark.asyncio
async def test_update_coze_config_with_none_values(config_service, db_session):
    """Test that update_coze_config handles None values correctly (should not update)"""
    # Create initial configuration
    initial_config = CozeConfig(
        id=uuid.uuid4(),
        agent_id="agent_123",
        api_token="token_xyz",
        parameters={"key": "value"}
    )
    db_session.add(initial_config)
    db_session.commit()
    
    # Update with None values (should not change anything)
    updated_config = await config_service.update_coze_config(
        agent_id=None,
        api_token=None,
        parameters=None
    )
    
    # All fields should remain unchanged
    assert updated_config.agent_id == "agent_123"
    assert updated_config.api_token == "token_xyz"
    assert updated_config.parameters == {"key": "value"}


@pytest.mark.asyncio
async def test_update_model_config_with_empty_strings(config_service, db_session):
    """Test that update_model_config accepts empty strings"""
    config = await config_service.update_model_config(
        model_name="test-model",
        api_endpoint="https://test.com",
        api_key=""  # Empty string should be accepted
    )
    
    assert config.api_key == ""


@pytest.mark.asyncio
async def test_multiple_updates_preserve_data(config_service, db_session):
    """Test that multiple sequential updates preserve data correctly"""
    # First update
    config1 = await config_service.update_model_config(
        model_name="gpt-3.5-turbo",
        api_key="key1"
    )
    assert config1.model_name == "gpt-3.5-turbo"
    assert config1.api_key == "key1"
    
    # Second update
    config2 = await config_service.update_model_config(
        temperature=0.9
    )
    assert config2.model_name == "gpt-3.5-turbo"  # Should be preserved
    assert config2.api_key == "key1"  # Should be preserved
    assert config2.temperature == 0.9
    
    # Third update
    config3 = await config_service.update_model_config(
        max_tokens=5000
    )
    assert config3.model_name == "gpt-3.5-turbo"  # Should be preserved
    assert config3.api_key == "key1"  # Should be preserved
    assert config3.temperature == 0.9  # Should be preserved
    assert config3.max_tokens == 5000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

