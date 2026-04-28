"""
测试管理员认证功能
"""
import pytest
from sqlalchemy.orm import sessionmaker
from database import Base
from services.auth_service import AuthService
from models.user import User
from testing_db import create_test_engine, create_test_schema, drop_test_schema
from utils.security import verify_password


# 创建测试数据库
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_test_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    create_test_schema(engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        drop_test_schema(engine)


def test_admin_login_with_correct_credentials(db_session):
    """测试使用正确凭据登录管理员账户"""
    # 第一次登录应该自动创建管理员账户
    result = AuthService.login(
        db=db_session,
        account="admin",
        password="Admin123!",
        user_type="administrator"
    )
    
    # 验证返回结果
    assert result is not None
    assert "access_token" in result
    assert "refresh_token" in result
    assert "user" in result
    assert result["user"]["account"] == "admin"
    assert result["user"]["user_type"] == "administrator"
    assert result["user"]["name"] == "系统管理员"
    assert result["user"]["email"] == "admin@system.local"
    
    # 验证管理员用户已创建
    admin_user = db_session.query(User).filter(
        User.account == "admin",
        User.user_type == "administrator"
    ).first()
    
    assert admin_user is not None
    assert admin_user.account == "admin"
    assert admin_user.user_type == "administrator"
    assert verify_password("Admin123!", admin_user.password_hash)


def test_admin_login_with_incorrect_password(db_session):
    """测试使用错误密码登录管理员账户"""
    # 先创建管理员账户
    AuthService.login(
        db=db_session,
        account="admin",
        password="Admin123!",
        user_type="administrator"
    )
    
    # 尝试使用错误密码登录
    with pytest.raises(ValueError, match="无效的管理员凭据"):
        AuthService.login(
            db=db_session,
            account="admin",
            password="WrongPassword",
            user_type="administrator"
        )


def test_admin_login_with_incorrect_username(db_session):
    """测试使用错误用户名登录管理员账户"""
    with pytest.raises(ValueError, match="无效的管理员凭据"):
        AuthService.login(
            db=db_session,
            account="notadmin",
            password="Admin123!",
            user_type="administrator"
        )


def test_admin_auto_creation_on_first_login(db_session):
    """测试首次登录时自动创建管理员账户"""
    # 验证管理员账户不存在
    admin_user = db_session.query(User).filter(
        User.account == "admin",
        User.user_type == "administrator"
    ).first()
    assert admin_user is None
    
    # 首次登录
    result = AuthService.login(
        db=db_session,
        account="admin",
        password="Admin123!",
        user_type="administrator"
    )
    
    # 验证登录成功
    assert result is not None
    assert "access_token" in result
    
    # 验证管理员账户已自动创建
    admin_user = db_session.query(User).filter(
        User.account == "admin",
        User.user_type == "administrator"
    ).first()
    assert admin_user is not None


def test_admin_password_uses_same_hashing_mechanism(db_session):
    """测试管理员密码使用与其他用户相同的哈希机制"""
    # 创建管理员账户
    AuthService.login(
        db=db_session,
        account="admin",
        password="Admin123!",
        user_type="administrator"
    )
    
    # 获取管理员用户
    admin_user = db_session.query(User).filter(
        User.account == "admin",
        User.user_type == "administrator"
    ).first()
    
    # 验证密码哈希格式（bcrypt格式以$2b$开头）
    assert admin_user.password_hash.startswith("$2b$")
    
    # 验证可以使用相同的verify_password函数验证
    assert verify_password("Admin123!", admin_user.password_hash)
    assert not verify_password("WrongPassword", admin_user.password_hash)


def test_admin_token_contains_administrator_role(db_session):
    """测试管理员JWT令牌包含administrator角色"""
    from utils.security import verify_token
    
    # 登录管理员
    result = AuthService.login(
        db=db_session,
        account="admin",
        password="Admin123!",
        user_type="administrator"
    )
    
    # 验证令牌
    access_token = result["access_token"]
    payload = verify_token(access_token, token_type="access")
    
    assert payload is not None
    assert payload.get("user_type") == "administrator"
    assert payload.get("account") == "admin"


def test_teacher_login_still_works(db_session):
    """测试教师登录功能仍然正常工作（向后兼容性）"""
    # 注册教师
    AuthService.register_teacher(
        db=db_session,
        account="teacher001",
        email="teacher@test.com",
        phone="13800138000",
        password="Teacher123!",
        name="测试教师"
    )
    
    # 教师登录
    result = AuthService.login(
        db=db_session,
        account="teacher001",
        password="Teacher123!",
        user_type="teacher"
    )
    
    assert result is not None
    assert result["user"]["user_type"] == "teacher"
    assert result["user"]["account"] == "teacher001"


def test_teacher_login_accepts_email_identifier(db_session):
    """Teachers can sign in with email as well as account."""
    AuthService.register_teacher(
        db=db_session,
        account="teacher002",
        email="teacher002@test.com",
        phone="13800138001",
        password="Teacher123!",
        name="邮箱登录教师"
    )

    result = AuthService.login(
        db=db_session,
        account="teacher002@test.com",
        password="Teacher123!",
        user_type="teacher"
    )

    assert result is not None
    assert result["user"]["user_type"] == "teacher"
    assert result["user"]["account"] == "teacher002"


def test_student_login_still_works(db_session):
    """测试学生登录功能仍然正常工作（向后兼容性）"""
    # 注册学生
    AuthService.register_student(
        db=db_session,
        account="student001",
        password="Student123!",
        name="测试学生",
        email="student@test.com"
    )
    
    # 学生登录
    result = AuthService.login(
        db=db_session,
        account="student001",
        password="Student123!",
        user_type="student"
    )
    
    assert result is not None
    assert result["user"]["user_type"] == "student"
    assert result["user"]["account"] == "student001"


def test_refresh_token_returns_complete_token_bundle(db_session):
    """Refresh should return the fields the frontend stores."""
    AuthService.register_teacher(
        db=db_session,
        account="teacher_refresh",
        email="teacher_refresh@test.com",
        phone="13800138002",
        password="Teacher123!",
        name="刷新测试教师"
    )

    login_result = AuthService.login(
        db=db_session,
        account="teacher_refresh",
        password="Teacher123!",
        user_type="teacher"
    )

    refresh_result = AuthService.refresh_token(
        db=db_session,
        refresh_token=login_result["refresh_token"]
    )

    assert "access_token" in refresh_result
    assert "refresh_token" in refresh_result
    assert refresh_result["token_type"] == "bearer"
    assert refresh_result["expires_in"] > 0


def test_change_admin_password_with_valid_credentials(db_session):
    """测试使用有效凭据修改管理员密码"""
    # 先创建管理员账户
    AuthService.login(
        db=db_session,
        account="admin",
        password="Admin123!",
        user_type="administrator"
    )
    
    # 修改密码
    result = AuthService.change_admin_password(
        db=db_session,
        current_password="Admin123!",
        new_password="NewAdmin456!"
    )
    
    assert result is True
    
    # 验证新密码可以登录
    login_result = AuthService.login(
        db=db_session,
        account="admin",
        password="NewAdmin456!",
        user_type="administrator"
    )
    
    assert login_result is not None
    assert "access_token" in login_result
    
    # 验证旧密码不能登录
    with pytest.raises(ValueError, match="无效的管理员凭据"):
        AuthService.login(
            db=db_session,
            account="admin",
            password="Admin123!",
            user_type="administrator"
        )


def test_change_admin_password_with_incorrect_current_password(db_session):
    """测试使用错误的当前密码修改管理员密码"""
    # 先创建管理员账户
    AuthService.login(
        db=db_session,
        account="admin",
        password="Admin123!",
        user_type="administrator"
    )
    
    # 尝试使用错误的当前密码修改
    with pytest.raises(ValueError, match="当前密码错误"):
        AuthService.change_admin_password(
            db=db_session,
            current_password="WrongPassword",
            new_password="NewAdmin456!"
        )
    
    # 验证密码未被修改（旧密码仍然有效）
    login_result = AuthService.login(
        db=db_session,
        account="admin",
        password="Admin123!",
        user_type="administrator"
    )
    
    assert login_result is not None


def test_change_admin_password_without_admin_account(db_session):
    """测试在管理员账户不存在时修改密码"""
    # 不创建管理员账户，直接尝试修改密码
    with pytest.raises(ValueError, match="管理员账户不存在"):
        AuthService.change_admin_password(
            db=db_session,
            current_password="Admin123!",
            new_password="NewAdmin456!"
        )


def test_change_admin_password_uses_same_hashing_mechanism(db_session):
    """测试修改管理员密码使用相同的哈希机制"""
    # 创建管理员账户
    AuthService.login(
        db=db_session,
        account="admin",
        password="Admin123!",
        user_type="administrator"
    )
    
    # 修改密码
    AuthService.change_admin_password(
        db=db_session,
        current_password="Admin123!",
        new_password="NewAdmin456!"
    )
    
    # 获取管理员用户
    admin_user = db_session.query(User).filter(
        User.account == "admin",
        User.user_type == "administrator"
    ).first()
    
    # 验证新密码哈希格式（bcrypt格式以$2b$开头）
    assert admin_user.password_hash.startswith("$2b$")
    
    # 验证可以使用相同的verify_password函数验证新密码
    assert verify_password("NewAdmin456!", admin_user.password_hash)
    assert not verify_password("Admin123!", admin_user.password_hash)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
