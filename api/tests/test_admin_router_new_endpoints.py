"""
管理员路由新端点测试
测试配置管理、用户管理和密码管理端点
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from main import app
from database import Base, get_db
from models.user import User
from models.config import ModelConfig, CozeConfig
from utils.security import hash_password, create_token

# 创建测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin_new_endpoints.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """覆盖数据库依赖"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    """设置测试数据库"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_user(setup_database):
    """创建管理员用户"""
    db = TestingSessionLocal()
    admin = User(
        id=uuid.uuid4(),
        account="admin",
        name="Administrator",
        password_hash=hash_password("Admin123!"),
        user_type="administrator",
        email="admin@system.local"
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.close()
    return admin


@pytest.fixture
def teacher_user(setup_database):
    """创建教师用户"""
    db = TestingSessionLocal()
    teacher = User(
        id=uuid.uuid4(),
        account="teacher001",
        name="Test Teacher",
        password_hash=hash_password("password123"),
        user_type="teacher",
        email="teacher@test.com"
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    db.close()
    return teacher


@pytest.fixture
def student_user(setup_database):
    """创建学生用户"""
    db = TestingSessionLocal()
    student = User(
        id=uuid.uuid4(),
        account="student001",
        name="Test Student",
        password_hash=hash_password("password123"),
        user_type="student",
        email="student@test.com"
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    db.close()
    return student


@pytest.fixture
def admin_token(admin_user):
    """生成管理员令牌"""
    return create_token({"sub": str(admin_user.id), "user_type": "administrator"})


@pytest.fixture
def teacher_token(teacher_user):
    """生成教师令牌"""
    return create_token({"sub": str(teacher_user.id), "user_type": "teacher"})


# ==================== 测试模型配置端点 ====================

def test_get_model_config_as_admin(admin_token):
    """测试管理员可以获取模型配置"""
    response = client.get(
        "/api/admin/config/models",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    config = response.json()
    assert "model_name" in config
    assert "api_endpoint" in config
    assert "api_key" in config
    assert "temperature" in config
    assert "max_tokens" in config
    assert "parameters" in config


def test_update_model_config_as_admin(admin_token):
    """测试管理员可以更新模型配置"""
    response = client.put(
        "/api/admin/config/models",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "model_name": "gpt-4",
            "temperature": 0.8,
            "max_tokens": 3000
        }
    )
    
    assert response.status_code == 200
    config = response.json()
    assert config["model_name"] == "gpt-4"
    assert config["temperature"] == 0.8
    assert config["max_tokens"] == 3000


def test_get_model_config_as_teacher_fails(teacher_token):
    """测试教师无法访问模型配置端点"""
    response = client.get(
        "/api/admin/config/models",
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    
    assert response.status_code == 403


# ==================== 测试Coze配置端点 ====================

def test_get_coze_config_as_admin(admin_token):
    """测试管理员可以获取Coze配置"""
    response = client.get(
        "/api/admin/config/coze",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    config = response.json()
    assert "agent_id" in config
    assert "api_token" in config
    assert "parameters" in config


def test_update_coze_config_as_admin(admin_token):
    """测试管理员可以更新Coze配置"""
    response = client.put(
        "/api/admin/config/coze",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "agent_id": "coze_agent_123",
            "api_token": "new_token_456",
            "parameters": {"timeout": 60}
        }
    )
    
    assert response.status_code == 200
    config = response.json()
    assert config["agent_id"] == "coze_agent_123"
    assert config["api_token"] == "new_token_456"
    assert config["parameters"]["timeout"] == 60


def test_get_coze_config_as_teacher_fails(teacher_token):
    """测试教师无法访问Coze配置端点"""
    response = client.get(
        "/api/admin/config/coze",
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    
    assert response.status_code == 403


# ==================== 测试用户管理端点 ====================

def test_get_all_users_as_admin(admin_token, teacher_user, student_user):
    """测试管理员可以获取所有用户列表"""
    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["code"] == 200
    users = result["data"]
    assert isinstance(users, list)
    assert len(users) >= 2  # 至少有教师和学生
    
    # 验证用户信息包含所有必需字段
    user_data = users[0]
    assert "id" in user_data
    assert "account" in user_data
    assert "name" in user_data
    assert "email" in user_data
    assert "user_type" in user_data
    assert "class_name" in user_data  # 验证包含班级名称
    assert "created_at" in user_data


def test_get_users_filtered_by_role(admin_token, teacher_user, student_user):
    """测试管理员可以按角色过滤用户"""
    # 获取教师
    response = client.get(
        "/api/admin/users?role=teacher",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["code"] == 200
    teachers = result["data"]
    assert all(user["user_type"] == "teacher" for user in teachers)
    
    # 获取学生
    response = client.get(
        "/api/admin/users?role=student",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["code"] == 200
    students = result["data"]
    assert all(user["user_type"] == "student" for user in students)


def test_get_users_with_invalid_role_fails(admin_token):
    """测试使用无效角色过滤失败"""
    response = client.get(
        "/api/admin/users?role=invalid",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 400
    assert "角色必须是teacher或student" in response.json()["detail"]


def test_get_user_by_id_as_admin(admin_token, teacher_user):
    """测试管理员可以获取指定用户详情"""
    response = client.get(
        f"/api/admin/users/{teacher_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["code"] == 200
    user_data = result["data"]
    assert user_data["id"] == str(teacher_user.id)
    assert user_data["account"] == teacher_user.account
    assert user_data["name"] == teacher_user.name
    assert user_data["email"] == teacher_user.email
    assert "class_name" in user_data  # 验证包含班级名称


def test_get_nonexistent_user_fails(admin_token):
    """测试获取不存在的用户失败"""
    nonexistent_id = str(uuid.uuid4())
    response = client.get(
        f"/api/admin/users/{nonexistent_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


def test_get_users_as_teacher_fails(teacher_token):
    """测试教师无法访问用户管理端点"""
    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    
    assert response.status_code == 403


# ==================== 测试密码管理端点 ====================

def test_change_admin_password_success(admin_token):
    """测试管理员可以修改密码"""
    response = client.put(
        "/api/admin/password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "current_password": "Admin123!",
            "new_password": "NewSecurePass123!"
        }
    )
    
    assert response.status_code == 200
    assert response.json()["code"] == 200
    assert "成功" in response.json()["message"]


def test_change_admin_password_with_wrong_current_password(admin_token):
    """测试使用错误的当前密码修改失败"""
    response = client.put(
        "/api/admin/password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "current_password": "WrongPassword",
            "new_password": "NewSecurePass123!"
        }
    )
    
    assert response.status_code == 400
    assert "当前密码错误" in response.json()["detail"]


def test_change_password_as_teacher_fails(teacher_token):
    """测试教师无法访问管理员密码修改端点"""
    response = client.put(
        "/api/admin/password",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "current_password": "password123",
            "new_password": "NewPassword123!"
        }
    )
    
    assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
