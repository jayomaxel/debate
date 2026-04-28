"""
Test migration 003 - ModelConfig and CozeConfig tables
"""
import pytest
from sqlalchemy import inspect
from database import engine, init_engine
from models.config import ModelConfig, CozeConfig


def test_model_config_table_exists():
    """Test that model_config table was created"""
    init_engine()
    from database import engine as db_engine
    inspector = inspect(db_engine)
    tables = inspector.get_table_names()
    assert 'model_config' in tables, "model_config table should exist"


def test_coze_config_table_exists():
    """Test that coze_config table was created"""
    init_engine()
    from database import engine as db_engine
    inspector = inspect(db_engine)
    tables = inspector.get_table_names()
    assert 'coze_config' in tables, "coze_config table should exist"


def test_model_config_columns():
    """Test that model_config table has correct columns"""
    init_engine()
    from database import engine as db_engine
    inspector = inspect(db_engine)
    columns = {col['name']: col for col in inspector.get_columns('model_config')}
    
    # Check required columns exist
    required_columns = ['id', 'model_name', 'api_endpoint', 'api_key', 
                       'temperature', 'max_tokens', 'parameters', 
                       'created_at', 'updated_at']
    
    for col_name in required_columns:
        assert col_name in columns, f"Column {col_name} should exist in model_config"
    
    # Check column types
    assert columns['model_name']['type'].__class__.__name__ == 'VARCHAR'
    assert columns['api_endpoint']['type'].__class__.__name__ == 'VARCHAR'
    assert columns['api_key']['type'].__class__.__name__ == 'VARCHAR'
    assert columns['temperature']['type'].__class__.__name__ == 'DOUBLE_PRECISION'
    assert columns['max_tokens']['type'].__class__.__name__ == 'INTEGER'
    assert columns['parameters']['type'].__class__.__name__ == 'JSON'


def test_coze_config_columns():
    """Test that coze_config table has correct columns"""
    init_engine()
    from database import engine as db_engine
    inspector = inspect(db_engine)
    columns = {col['name']: col for col in inspector.get_columns('coze_config')}
    
    # Check required columns exist
    required_columns = ['id', 'agent_id', 'api_token', 'parameters', 
                       'created_at', 'updated_at']
    
    for col_name in required_columns:
        assert col_name in columns, f"Column {col_name} should exist in coze_config"
    
    # Check column types
    assert columns['agent_id']['type'].__class__.__name__ == 'VARCHAR'
    assert columns['api_token']['type'].__class__.__name__ == 'VARCHAR'
    assert columns['parameters']['type'].__class__.__name__ == 'JSON'


def test_model_config_default_values():
    """Test that ModelConfig.get_default() returns valid default configuration"""
    default_config = ModelConfig.get_default()
    
    assert default_config.model_name == "gpt-3.5-turbo"
    assert default_config.api_endpoint == "https://api.openai.com/v1/chat/completions"
    assert default_config.api_key == ""
    assert default_config.temperature == 0.7
    assert default_config.max_tokens == 2000
    assert default_config.parameters == {}


def test_coze_config_default_values():
    """Test that CozeConfig.get_default() returns valid default configuration"""
    default_config = CozeConfig.get_default()
    
    assert default_config.agent_id == ""
    assert default_config.api_token == ""
    assert default_config.parameters == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
