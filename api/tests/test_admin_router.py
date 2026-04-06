"""
管理员路由单元测试
测试管理员班级管理端点的功能
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from main import app
from database import Base, get_db
from models.user import User
from models.class_model import Class
from utils.security import hash_password, create_token

# 创建测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin_router.db"
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


@pytest.fixture
def student_token(student_user):
    """生成学生令牌"""
    return create_token({"sub": str(student_user.id), "user_type": "student"})


@pytest.fixture
def test_class(setup_database, teacher_user):
    """创建测试班级"""
    db = TestingSessionLocal()
    test_class = Class(
        id=uuid.uuid4(),
        name="Test Class",
        code="TEST01",
        teacher_id=teacher_user.id
    )
    db.add(test_class)
    db.commit()
    db.refresh(test_class)
    db.close()
    return test_class


# ==================== 测试获取所有班级 ====================

def test_get_all_classes_as_admin(admin_token, test_class):
    """测试管理员可以获取所有班级"""
    response = client.get(
        "/api/admin/classes",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    classes = response.json()
    assert isinstance(classes, list)
    assert len(classes) >= 1
    
    # 验证班级信息包含所有必需字段
    class_data = classes[0]
    assert "id" in class_data
    assert "name" in class_data
    assert "code" in class_data
    assert "teacher_id" in class_data
    assert "teacher_name" in class_data
    assert "student_count" in class_data
    assert "created_at" in class_data


def test_get_all_classes_as_teacher_fails(teacher_token, test_class):
    """测试教师无法访问管理员端点"""
    response = client.get(
        "/api/admin/classes",
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    
    assert response.status_code == 403
    assert "访问被拒绝" in response.json()["detail"]


def test_get_all_classes_as_student_fails(student_token, test_class):
    """测试学生无法访问管理员端点"""
    response = client.get(
        "/api/admin/classes",
        headers={"Authorization": f"Bearer {student_token}"}
    )
    
    assert response.status_code == 403
    assert "访问被拒绝" in response.json()["detail"]


def test_get_all_classes_without_token_fails(test_class):
    """测试未认证用户无法访问管理员端点"""
    response = client.get("/api/admin/classes")
    
    assert response.status_code == 403


# ==================== 测试创建班级 ====================

def test_create_class_as_admin(admin_token, teacher_user):
    """测试管理员可以为教师创建班级"""
    response = client.post(
        "/api/admin/classes",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "New Admin Class",
            "teacher_id": str(teacher_user.id)
        }
    )
    
    assert response.status_code == 200
    class_data = response.json()
    assert class_data["name"] == "New Admin Class"
    assert class_data["teacher_id"] == str(teacher_user.id)
    assert "code" in class_data
    assert "id" in class_data
    assert class_data["student_count"] == 0


def test_create_class_with_invalid_teacher(admin_token):
    """测试使用无效教师ID创建班级失败"""
    invalid_teacher_id = str(uuid.uuid4())
    response = client.post(
        "/api/admin/classes",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Invalid Class",
            "teacher_id": invalid_teacher_id
        }
    )
    
    assert response.status_code == 400
    assert "教师不存在" in response.json()["detail"]


def test_create_class_as_teacher_fails(teacher_token, teacher_user):
    """测试教师无法通过管理员端点创建班级"""
    response = client.post(
        "/api/admin/classes",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "name": "Unauthorized Class",
            "teacher_id": str(teacher_user.id)
        }
    )
    
    assert response.status_code == 403


# ==================== 测试更新班级 ====================

def test_update_class_name_as_admin(admin_token, test_class):
    """测试管理员可以更新班级名称"""
    response = client.put(
        f"/api/admin/classes/{test_class.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Updated Class Name"}
    )
    
    assert response.status_code == 200
    class_data = response.json()
    assert class_data["name"] == "Updated Class Name"
    assert class_data["id"] == str(test_class.id)


def test_update_class_teacher_as_admin(admin_token, test_class, teacher_user):
    """测试管理员可以更改班级的教师"""
    # 创建另一个教师
    db = TestingSessionLocal()
    new_teacher = User(
        id=uuid.uuid4(),
        account="teacher002",
        name="New Teacher",
        password_hash=hash_password("password123"),
        user_type="teacher",
        email="teacher2@test.com"
    )
    db.add(new_teacher)
    db.commit()
    db.refresh(new_teacher)
    new_teacher_id = str(new_teacher.id)
    db.close()
    
    response = client.put(
        f"/api/admin/classes/{test_class.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"teacher_id": new_teacher_id}
    )
    
    assert response.status_code == 200
    class_data = response.json()
    assert class_data["teacher_id"] == new_teacher_id


def test_update_nonexistent_class_fails(admin_token):
    """测试更新不存在的班级失败"""
    nonexistent_id = str(uuid.uuid4())
    response = client.put(
        f"/api/admin/classes/{nonexistent_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Updated Name"}
    )
    
    assert response.status_code == 400
    assert "班级不存在" in response.json()["detail"]


def test_update_class_as_teacher_fails(teacher_token, test_class):
    """测试教师无法通过管理员端点更新班级"""
    response = client.put(
        f"/api/admin/classes/{test_class.id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"name": "Unauthorized Update"}
    )
    
    assert response.status_code == 403


# ==================== 测试删除班级 ====================

def test_delete_class_as_admin(admin_token, test_class):
    """测试管理员可以删除班级"""
    response = client.delete(
        f"/api/admin/classes/{test_class.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    assert response.json()["code"] == 200
    assert "成功" in response.json()["message"]
    
    # 验证班级已被删除
    get_response = client.get(
        "/api/admin/classes",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    classes = get_response.json()
    class_ids = [c["id"] for c in classes]
    assert str(test_class.id) not in class_ids


def test_delete_class_removes_student_enrollments(admin_token, teacher_user):
    """测试删除班级时会取消学生注册"""
    db = TestingSessionLocal()
    
    # 创建班级
    test_class = Class(
        id=uuid.uuid4(),
        name="Class with Students",
        code="STUD01",
        teacher_id=teacher_user.id
    )
    db.add(test_class)
    db.commit()
    
    # 创建学生并注册到班级
    student = User(
        id=uuid.uuid4(),
        account="student_enrolled",
        name="Enrolled Student",
        password_hash=hash_password("password123"),
        user_type="student",
        email="enrolled@test.com",
        class_id=test_class.id
    )
    db.add(student)
    db.commit()
    student_id = student.id
    db.close()
    
    # 删除班级
    response = client.delete(
        f"/api/admin/classes/{test_class.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    
    # 验证学生的 class_id 已被清除
    db = TestingSessionLocal()
    student = db.query(User).filter(User.id == student_id).first()
    assert student.class_id is None
    db.close()


def test_delete_nonexistent_class_fails(admin_token):
    """测试删除不存在的班级失败"""
    nonexistent_id = str(uuid.uuid4())
    response = client.delete(
        f"/api/admin/classes/{nonexistent_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 400
    assert "班级不存在" in response.json()["detail"]


def test_delete_class_as_teacher_fails(teacher_token, test_class):
    """测试教师无法通过管理员端点删除班级"""
    response = client.delete(
        f"/api/admin/classes/{test_class.id}",
        headers={"Authorization": f"Bearer {teacher_token}"}
    )
    
    assert response.status_code == 403


# ==================== 测试班级信息完整性 ====================

def test_class_response_contains_all_required_fields(admin_token, test_class, teacher_user):
    """测试班级响应包含所有必需字段（验证需求3.5）"""
    # 添加学生到班级
    db = TestingSessionLocal()
    student = User(
        id=uuid.uuid4(),
        account="student_for_count",
        name="Count Student",
        password_hash=hash_password("password123"),
        user_type="student",
        email="count@test.com",
        class_id=test_class.id
    )
    db.add(student)
    db.commit()
    db.close()
    
    response = client.get(
        "/api/admin/classes",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    classes = response.json()
    
    # 找到测试班级
    test_class_data = None
    for cls in classes:
        if cls["id"] == str(test_class.id):
            test_class_data = cls
            break
    
    assert test_class_data is not None
    
    # 验证所有必需字段存在
    required_fields = [
        "id", "name", "code", "teacher_id", 
        "teacher_name", "student_count", "created_at"
    ]
    for field in required_fields:
        assert field in test_class_data, f"Missing required field: {field}"
    
    # 验证字段值正确
    assert test_class_data["name"] == test_class.name
    assert test_class_data["teacher_id"] == str(teacher_user.id)
    assert test_class_data["teacher_name"] == teacher_user.name
    assert test_class_data["student_count"] >= 1  # 至少有我们添加的学生


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
