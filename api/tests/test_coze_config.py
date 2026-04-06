"""
Test CozeConfig model - verify Coze agent configuration storage
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.config import CozeConfig
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


def test_coze_config_creation(db_session):
    """Test that CozeConfig can be created with all required fields"""
    config = CozeConfig(
        id=uuid.uuid4(),
        agent_id="coze_agent_123",
        api_token="test_token_abc",
        parameters={"temperature": 0.8, "max_length": 1000}
    )
    
    db_session.add(config)
    db_session.commit()
    
    # Query back and verify
    retrieved_config = db_session.query(CozeConfig).filter(
        CozeConfig.agent_id == "coze_agent_123"
    ).first()
    
    assert retrieved_config is not None
    assert retrieved_config.agent_id == "coze_agent_123"
    assert retrieved_config.api_token == "test_token_abc"
    assert retrieved_config.parameters == {"temperature": 0.8, "max_length": 1000}
    assert retrieved_config.created_at is not None
    assert retrieved_config.updated_at is not None


def test_coze_config_default_parameters(db_session):
    """Test that CozeConfig uses default empty dict for parameters"""
    config = CozeConfig(
        id=uuid.uuid4(),
        agent_id="coze_agent_456",
        api_token="test_token_def"
    )
    
    db_session.add(config)
    db_session.commit()
    
    retrieved_config = db_session.query(CozeConfig).filter(
        CozeConfig.agent_id == "coze_agent_456"
    ).first()
    
    assert retrieved_config.parameters == {}  # Default empty dict


def test_coze_config_get_default_method(db_session):
    """Test that get_default() class method returns default configuration"""
    default_config = CozeConfig.get_default()
    
    assert default_config.agent_id == ""
    assert default_config.api_token == ""
    assert default_config.parameters == {}


def test_coze_config_update(db_session):
    """Test that CozeConfig can be updated"""
    config = CozeConfig(
        id=uuid.uuid4(),
        agent_id="coze_agent_789",
        api_token="old_token",
        parameters={"setting1": "value1"}
    )
    
    db_session.add(config)
    db_session.commit()
    
    # Update the configuration
    config.api_token = "new_token"
    config.parameters = {"setting1": "value1", "setting2": "value2"}
    db_session.commit()
    
    # Query back and verify updates
    retrieved_config = db_session.query(CozeConfig).filter(
        CozeConfig.id == config.id
    ).first()
    
    assert retrieved_config.api_token == "new_token"
    assert retrieved_config.parameters == {"setting1": "value1", "setting2": "value2"}


def test_coze_config_parameters_json(db_session):
    """Test that parameters field correctly stores JSON data"""
    complex_params = {
        "temperature": 0.9,
        "max_length": 2000,
        "stop_sequences": ["END", "STOP"],
        "nested": {
            "key1": "value1",
            "key2": 456
        },
        "list_param": [1, 2, 3, 4, 5]
    }
    
    config = CozeConfig(
        id=uuid.uuid4(),
        agent_id="coze_agent_complex",
        api_token="test_token",
        parameters=complex_params
    )
    
    db_session.add(config)
    db_session.commit()
    
    retrieved_config = db_session.query(CozeConfig).filter(
        CozeConfig.agent_id == "coze_agent_complex"
    ).first()
    
    assert retrieved_config.parameters == complex_params
    assert retrieved_config.parameters["temperature"] == 0.9
    assert retrieved_config.parameters["nested"]["key1"] == "value1"
    assert retrieved_config.parameters["list_param"] == [1, 2, 3, 4, 5]


def test_coze_config_repr(db_session):
    """Test that __repr__ method returns expected string"""
    config = CozeConfig(
        id=uuid.uuid4(),
        agent_id="test-agent",
        api_token="test_token"
    )
    
    repr_str = repr(config)
    assert "CozeConfig" in repr_str
    assert "test-agent" in repr_str


def test_coze_config_required_fields(db_session):
    """Test that CozeConfig requires agent_id and api_token"""
    # Missing agent_id
    with pytest.raises(Exception):
        config = CozeConfig(
            id=uuid.uuid4(),
            api_token="test_token"
        )
        db_session.add(config)
        db_session.commit()
    
    db_session.rollback()
    
    # Missing api_token
    with pytest.raises(Exception):
        config = CozeConfig(
            id=uuid.uuid4(),
            agent_id="test_agent"
        )
        db_session.add(config)
        db_session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
