"""
Test ModelConfig model - verify AI model configuration storage
"""
import pytest
from sqlalchemy.orm import sessionmaker
from models.config import ModelConfig
from database import Base
from testing_db import create_test_engine, create_test_schema, drop_test_schema
import uuid

# Create in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_test_engine(TEST_DATABASE_URL)
    create_test_schema(engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        drop_test_schema(engine)


def test_model_config_creation(db_session):
    """Test that ModelConfig can be created with all required fields"""
    config = ModelConfig(
        id=uuid.uuid4(),
        model_name="gpt-4",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_api_key_123",
        temperature=0.8,
        max_tokens=4000,
        parameters={"top_p": 0.9, "frequency_penalty": 0.5}
    )
    
    db_session.add(config)
    db_session.commit()
    
    # Query back and verify
    retrieved_config = db_session.query(ModelConfig).filter(
        ModelConfig.model_name == "gpt-4"
    ).first()
    
    assert retrieved_config is not None
    assert retrieved_config.model_name == "gpt-4"
    assert retrieved_config.api_endpoint == "https://api.openai.com/v1/chat/completions"
    assert retrieved_config.api_key == "test_api_key_123"
    assert retrieved_config.temperature == 0.8
    assert retrieved_config.max_tokens == 4000
    assert retrieved_config.parameters == {"top_p": 0.9, "frequency_penalty": 0.5}
    assert retrieved_config.created_at is not None
    assert retrieved_config.updated_at is not None


def test_model_config_default_values(db_session):
    """Test that ModelConfig uses default values for temperature and max_tokens"""
    config = ModelConfig(
        id=uuid.uuid4(),
        model_name="gpt-3.5-turbo",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_key"
    )
    
    db_session.add(config)
    db_session.commit()
    
    retrieved_config = db_session.query(ModelConfig).filter(
        ModelConfig.model_name == "gpt-3.5-turbo"
    ).first()
    
    assert retrieved_config.temperature == 0.7  # Default value
    assert retrieved_config.max_tokens == 2000  # Default value
    assert retrieved_config.parameters == {}  # Default empty dict


def test_model_config_get_default_method(db_session):
    """Test that get_default() class method returns default configuration"""
    default_config = ModelConfig.get_default()
    
    assert default_config.model_name == "gpt-3.5-turbo"
    assert default_config.api_endpoint == "https://api.openai.com/v1/chat/completions"
    assert default_config.api_key == ""
    assert default_config.temperature == 0.7
    assert default_config.max_tokens == 2000
    assert default_config.parameters == {}


def test_model_config_update(db_session):
    """Test that ModelConfig can be updated"""
    config = ModelConfig(
        id=uuid.uuid4(),
        model_name="gpt-3.5-turbo",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="old_key",
        temperature=0.7,
        max_tokens=2000
    )
    
    db_session.add(config)
    db_session.commit()
    
    # Update the configuration
    config.api_key = "new_key"
    config.temperature = 0.9
    config.max_tokens = 3000
    db_session.commit()
    
    # Query back and verify updates
    retrieved_config = db_session.query(ModelConfig).filter(
        ModelConfig.id == config.id
    ).first()
    
    assert retrieved_config.api_key == "new_key"
    assert retrieved_config.temperature == 0.9
    assert retrieved_config.max_tokens == 3000


def test_model_config_parameters_json(db_session):
    """Test that parameters field correctly stores JSON data"""
    complex_params = {
        "top_p": 0.95,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.1,
        "stop_sequences": ["END", "STOP"],
        "nested": {
            "key1": "value1",
            "key2": 123
        }
    }
    
    config = ModelConfig(
        id=uuid.uuid4(),
        model_name="gpt-4",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_key",
        parameters=complex_params
    )
    
    db_session.add(config)
    db_session.commit()
    
    retrieved_config = db_session.query(ModelConfig).filter(
        ModelConfig.model_name == "gpt-4"
    ).first()
    
    assert retrieved_config.parameters == complex_params
    assert retrieved_config.parameters["top_p"] == 0.95
    assert retrieved_config.parameters["nested"]["key1"] == "value1"


def test_model_config_repr(db_session):
    """Test that __repr__ method returns expected string"""
    config = ModelConfig(
        id=uuid.uuid4(),
        model_name="test-model",
        api_endpoint="https://test.com",
        api_key="test_key"
    )
    
    repr_str = repr(config)
    assert "ModelConfig" in repr_str
    assert "test-model" in repr_str


def test_model_config_required_fields(db_session):
    """Test that ModelConfig requires model_name, api_endpoint, and api_key"""
    # Missing model_name
    with pytest.raises(Exception):
        config = ModelConfig(
            id=uuid.uuid4(),
            api_endpoint="https://test.com",
            api_key="test_key"
        )
        db_session.add(config)
        db_session.commit()
    
    db_session.rollback()
    
    # Missing api_endpoint
    with pytest.raises(Exception):
        config = ModelConfig(
            id=uuid.uuid4(),
            model_name="test-model",
            api_key="test_key"
        )
        db_session.add(config)
        db_session.commit()
    
    db_session.rollback()
    
    # Missing api_key
    with pytest.raises(Exception):
        config = ModelConfig(
            id=uuid.uuid4(),
            model_name="test-model",
            api_endpoint="https://test.com"
        )
        db_session.add(config)
        db_session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
