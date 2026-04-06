"""
测试管理员API响应格式
验证所有管理员端点返回统一的响应格式
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, '.')

from main import app
from models.user import User
from services.auth_service import AuthService

client = TestClient(app)


@pytest.fixture
def admin_token():
    """创建管理员token"""
    # 创建一个模拟的管理员用户
    admin_user = Mock(spec=User)
    admin_user.id = "test-admin-id"
    admin_user.account = "admin"
    admin_user.user_type = "administrator"
    
    # 生成token
    token = AuthService.create_access_token(
        data={"sub": admin_user.account, "user_type": admin_user.user_type}
    )
    return token


def test_get_users_response_format(admin_token):
    """测试获取用户列表的响应格式"""
    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    # 检查状态码
    assert response.status_code in [200, 401], f"Unexpected status code: {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        
        # 检查响应格式
        assert "code" in data, "Response should have 'code' field"
        assert "message" in data, "Response should have 'message' field"
        assert "data" in data, "Response should have 'data' field"
        
        # 检查code值
        assert data["code"] == 200, f"Expected code 200, got {data['code']}"
        
        # 检查data是列表
        assert isinstance(data["data"], list), "Data should be a list"


def test_get_classes_response_format(admin_token):
    """测试获取班级列表的响应格式"""
    response = client.get(
        "/api/admin/classes",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    # 检查状态码
    assert response.status_code in [200, 401], f"Unexpected status code: {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        
        # 检查响应格式
        assert "code" in data, "Response should have 'code' field"
        assert "message" in data, "Response should have 'message' field"
        assert "data" in data, "Response should have 'data' field"
        
        # 检查code值
        assert data["code"] == 200, f"Expected code 200, got {data['code']}"
        
        # 检查data是列表
        assert isinstance(data["data"], list), "Data should be a list"


def test_get_model_config_response_format(admin_token):
    """测试获取模型配置的响应格式"""
    response = client.get(
        "/api/admin/config/models",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    # 检查状态码
    assert response.status_code in [200, 401], f"Unexpected status code: {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        
        # 检查响应格式
        assert "code" in data, "Response should have 'code' field"
        assert "message" in data, "Response should have 'message' field"
        assert "data" in data, "Response should have 'data' field"
        
        # 检查code值
        assert data["code"] == 200, f"Expected code 200, got {data['code']}"
        
        # 检查data是对象
        assert isinstance(data["data"], dict), "Data should be a dict"
        
        # 检查配置字段
        config = data["data"]
        assert "id" in config, "Config should have 'id' field"
        assert "model_name" in config, "Config should have 'model_name' field"
        assert "api_endpoint" in config, "Config should have 'api_endpoint' field"


def test_get_coze_config_response_format(admin_token):
    """测试获取Coze配置的响应格式"""
    response = client.get(
        "/api/admin/config/coze",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    # 检查状态码
    assert response.status_code in [200, 401], f"Unexpected status code: {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        
        # 检查响应格式
        assert "code" in data, "Response should have 'code' field"
        assert "message" in data, "Response should have 'message' field"
        assert "data" in data, "Response should have 'data' field"
        
        # 检查code值
        assert data["code"] == 200, f"Expected code 200, got {data['code']}"
        
        # 检查data是对象
        assert isinstance(data["data"], dict), "Data should be a dict"
        
        # 检查配置字段
        config = data["data"]
        assert "id" in config, "Config should have 'id' field"
        assert "agent_id" in config, "Config should have 'agent_id' field"
        assert "api_token" in config, "Config should have 'api_token' field"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
