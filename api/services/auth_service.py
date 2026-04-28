"""
用户认证服务
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from models.user import User
from utils.security import hash_password, verify_password, create_access_token, create_refresh_token
from utils.user_email import build_placeholder_email, to_public_email
import uuid


class AuthService:
    """用户认证服务类"""
    
    # Administrator constants
    ADMIN_USERNAME = "admin"
    ADMIN_DEFAULT_PASSWORD = "Admin123!"
    
    @staticmethod
    def register_teacher(
        db: Session,
        account: str,
        email: str,
        phone: str,
        password: str,
        name: str,
        class_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        教师注册
        
        Args:
            db: 数据库会话
            account: 教工号
            email: 邮箱
            phone: 手机号
            password: 密码
            name: 姓名
            class_id: 班级ID（可选）
            
        Returns:
            包含用户信息的字典
            
        Raises:
            ValueError: 如果账号或邮箱已存在
        """
        # 检查账号是否已存在
        existing_account = db.query(User).filter(User.account == account).first()
        if existing_account:
            raise ValueError("教工号已被注册")
        
        # 检查邮箱是否已存在
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            raise ValueError("邮箱已被注册")
            
        # 如果提供了班级ID，验证班级是否存在
        if class_id:
            from models.class_model import Class
            cls = db.query(Class).filter(Class.id == uuid.UUID(class_id)).first()
            if not cls:
                raise ValueError("班级不存在")
        
        # 创建用户
        user = User(
            id=uuid.uuid4(),
            account=account,
            password_hash=hash_password(password),
            user_type='teacher',
            name=name,
            email=email,
            phone=phone,
            class_id=uuid.UUID(class_id) if class_id else None
        )
        
        try:
            db.add(user)
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            raise ValueError("账号或邮箱已被注册")
        
        return {
            "id": str(user.id),
            "account": user.account,
            "name": user.name,
            "email": user.email,
            "user_type": user.user_type,
            "class_id": str(user.class_id) if user.class_id else None
        }
    
    @staticmethod
    def register_student(
        db: Session,
        account: str,
        password: str,
        name: str,
        class_id: Optional[str] = None,
        email: Optional[str] = None,
        student_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        学生注册
        
        Args:
            db: 数据库会话
            account: 账号
            password: 密码
            name: 姓名
            class_id: 班级ID（可选）
            email: 邮箱（可选）
            student_id: 学号（可选）
            
        Returns:
            包含用户信息的字典
            
        Raises:
            ValueError: 如果账号已存在或班级不存在
        """
        # 检查账号是否已存在
        existing_user = db.query(User).filter(User.account == account).first()
        if existing_user:
            raise ValueError("账号已被注册")
        
        # 如果提供了邮箱，检查邮箱是否已存在
        if email:
            existing_email = db.query(User).filter(User.email == email).first()
            if existing_email:
                raise ValueError("邮箱已被注册")
        
        # 如果提供了班级ID，验证班级是否存在
        if class_id:
            from models.class_model import Class
            cls = db.query(Class).filter(Class.id == uuid.UUID(class_id)).first()
            if not cls:
                raise ValueError("班级不存在")
        
        # 创建用户
        user = User(
            id=uuid.uuid4(),
            account=account,
            password_hash=hash_password(password),
            user_type='student',
            name=name,
            email=email or f"{account}@temp.com",  # 临时邮箱
            student_id=student_id,
            class_id=uuid.UUID(class_id) if class_id else None
        )
        user.email = email or build_placeholder_email(account)
        
        try:
            db.add(user)
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            raise ValueError("账号或邮箱已被注册")
        
        return {
            "id": str(user.id),
            "account": user.account,
            "name": user.name,
            "email": to_public_email(user.email),
            "user_type": user.user_type,
            "student_id": user.student_id,
            "class_id": str(user.class_id) if user.class_id else None
        }
    
    @staticmethod
    def login(
        db: Session,
        account: str,
        password: str,
        user_type: str
    ) -> Dict[str, Any]:
        """
        用户登录
        
        Args:
            db: 数据库会话
            account: 账号
            password: 密码
            user_type: 用户类型（teacher、student或administrator）
            
        Returns:
            包含令牌和用户信息的字典
            
        Raises:
            ValueError: 如果账号不存在或密码错误
        """
        # Handle administrator authentication separately
        if user_type == "administrator":
            return AuthService._authenticate_admin(db, account, password)
        
        # 查找用户
        login_identifier = account.strip()
        user = db.query(User).filter(
            User.account == login_identifier,
            User.user_type == user_type
        ).first()

        if not user and "@" in login_identifier:
            user = db.query(User).filter(
                func.lower(User.email) == login_identifier.lower(),
                User.user_type == user_type
            ).first()
        
        if not user:
            raise ValueError("账号不存在或用户类型错误")
        
        # 验证密码
        if not verify_password(password, user.password_hash):
            raise ValueError("密码错误")
        
        # 生成令牌 - 包含完整的用户信息
        token_data = {
            "user_id": str(user.id),
            "account": user.account,
            "name": user.name,
            "email": to_public_email(user.email),
            "user_type": user.user_type
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"user_id": str(user.id)})
        
        # 从配置获取过期时间
        from config import settings
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 转换为秒
            "user": {
                "id": str(user.id),
                "account": user.account,
                "name": user.name,
                "email": to_public_email(user.email),
                "user_type": user.user_type
            }
        }
    
    @staticmethod
    def refresh_token(
        db: Session,
        refresh_token: str
    ) -> Dict[str, Any]:
        """
        刷新访问令牌
        
        Args:
            db: 数据库会话
            refresh_token: 刷新令牌
            
        Returns:
            新的访问令牌
            
        Raises:
            ValueError: 如果刷新令牌无效
        """
        from utils.security import verify_token
        
        # 验证刷新令牌
        payload = verify_token(refresh_token, token_type="refresh")
        if not payload:
            raise ValueError("刷新令牌无效或已过期")
        
        user_id = payload.get("user_id")
        if not user_id:
            raise ValueError("刷新令牌格式错误")
        
        # 查找用户
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if not user:
            raise ValueError("用户不存在")
        
        # 生成新的访问令牌
        token_data = {
            "user_id": str(user.id),
            "user_type": user.user_type
        }
        new_access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token({"user_id": str(user.id)})

        from config import settings

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    
    @staticmethod
    def change_password(
        db: Session,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        修改密码
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            是否修改成功
            
        Raises:
            ValueError: 如果用户不存在或旧密码错误
        """
        # 查找用户
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if not user:
            raise ValueError("用户不存在")
        
        # 验证旧密码
        if not verify_password(old_password, user.password_hash):
            raise ValueError("旧密码错误")
        
        # 更新密码
        user.password_hash = hash_password(new_password)
        db.commit()
        
        return True
    
    @staticmethod
    def change_admin_password(
        db: Session,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        修改管理员密码
        
        Args:
            db: 数据库会话
            current_password: 当前密码
            new_password: 新密码
            
        Returns:
            是否修改成功
            
        Raises:
            ValueError: 如果管理员不存在或当前密码错误
        """
        # 查找管理员用户
        admin_user = db.query(User).filter(
            User.account == AuthService.ADMIN_USERNAME,
            User.user_type == "administrator"
        ).first()
        
        if not admin_user:
            raise ValueError("管理员账户不存在")
        
        # 验证当前密码
        if not verify_password(current_password, admin_user.password_hash):
            raise ValueError("当前密码错误")
        
        # 更新密码 - 使用相同的哈希机制
        admin_user.password_hash = hash_password(new_password)
        db.commit()
        
        return True
    
    @staticmethod
    def _authenticate_admin(
        db: Session,
        account: str,
        password: str
    ) -> Dict[str, Any]:
        """
        管理员认证
        
        Args:
            db: 数据库会话
            account: 账号
            password: 密码
            
        Returns:
            包含令牌和用户信息的字典
            
        Raises:
            ValueError: 如果账号不是admin或密码错误
        """
        # Check if username matches admin username
        if account != AuthService.ADMIN_USERNAME:
            raise ValueError("无效的管理员凭据")
        
        # Query for admin user
        admin_user = db.query(User).filter(
            User.account == AuthService.ADMIN_USERNAME,
            User.user_type == "administrator"
        ).first()
        
        # Auto-create admin user if not exists
        if not admin_user:
            admin_user = AuthService._create_admin_user(db)
        
        # Verify password
        if not verify_password(password, admin_user.password_hash):
            raise ValueError("无效的管理员凭据")
        
        # Generate tokens with complete user information
        token_data = {
            "user_id": str(admin_user.id),
            "account": admin_user.account,
            "name": admin_user.name,
            "email": admin_user.email,
            "user_type": admin_user.user_type
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"user_id": str(admin_user.id)})
        
        # Get expiration time from config
        from config import settings
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": str(admin_user.id),
                "account": admin_user.account,
                "name": admin_user.name,
                "email": admin_user.email,
                "user_type": admin_user.user_type
            }
        }
    
    @staticmethod
    def _create_admin_user(db: Session) -> User:
        """
        创建管理员用户
        
        Args:
            db: 数据库会话
            
        Returns:
            创建的管理员用户对象
        """
        # Create admin user with default password
        admin_user = User(
            id=uuid.uuid4(),
            account=AuthService.ADMIN_USERNAME,
            password_hash=hash_password(AuthService.ADMIN_DEFAULT_PASSWORD),
            user_type="administrator",
            name="系统管理员",
            email="admin@system.local",
            phone=None
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        return admin_user

    
    @staticmethod
    def delete_account(
        db: Session,
        user_id: str,
        password: str
    ) -> Dict[str, Any]:
        """
        注销账户
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            password: 密码（用于确认）
            
        Returns:
            注销结果信息
            
        Raises:
            ValueError: 如果用户不存在或密码错误
        """
        # 查找用户
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if not user:
            raise ValueError("用户不存在")
        
        # 验证密码
        if not verify_password(password, user.password_hash):
            raise ValueError("密码错误")
        
        # 根据用户类型进行不同的处理
        if user.user_type == "student":
            # 学生账户：软删除，保留历史数据
            # 移除班级关联
            user.class_id = None
            # 匿名化个人信息
            user.name = f"已注销用户_{user.id}"
            user.email = f"deleted_{user.id}@deleted.com"
            user.phone = None
            user.student_id = None
            # 标记账户为已删除
            user.account = f"deleted_{user.id}"
            
            db.commit()
            
            return {
                "message": "学生账户已注销",
                "data_retained": True,
                "note": "历史辩论记录和统计数据已匿名化保留"
            }
        
        elif user.user_type == "teacher":
            # 教师账户：检查是否有关联的班级
            from models.class_model import Class
            
            classes = db.query(Class).filter(Class.teacher_id == user.id).all()
            
            if classes:
                # 如果有班级，不允许直接删除
                raise ValueError(
                    f"无法注销账户：您还有 {len(classes)} 个班级。"
                    "请先删除或转移所有班级后再注销账户。"
                )
            
            # 如果没有班级，可以删除
            # 匿名化个人信息
            user.name = f"已注销教师_{user.id}"
            user.email = f"deleted_{user.id}@deleted.com"
            user.phone = None
            user.account = f"deleted_{user.id}"
            
            db.commit()
            
            return {
                "message": "教师账户已注销",
                "data_retained": False,
                "note": "账户信息已删除"
            }
        
        else:
            raise ValueError("未知的用户类型")
