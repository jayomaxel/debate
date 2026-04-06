"""
学生个人信息服务
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from models.user import User
import uuid


class ProfileService:
    """个人信息服务类"""
    
    @staticmethod
    def get_profile(
        db: Session,
        user_id: str
    ) -> Dict[str, Any]:
        """
        获取个人信息
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            用户信息字典
            
        Raises:
            ValueError: 如果用户不存在
        """
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        
        if not user:
            raise ValueError("用户不存在")
        
        return {
            "id": str(user.id),
            "account": user.account,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "student_id": user.student_id,
            "class_id": str(user.class_id) if user.class_id else None,
            "user_type": user.user_type,
            "created_at": user.created_at.isoformat()
        }
    
    @staticmethod
    def update_profile(
        db: Session,
        user_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        student_id: Optional[str] = None,
        class_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更新个人信息
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            name: 姓名（可选）
            email: 邮箱（可选）
            phone: 手机号（可选）
            student_id: 学号（可选）
            class_id: 班级ID（可选，仅学生）
            
        Returns:
            更新后的用户信息
            
        Raises:
            ValueError: 如果用户不存在或邮箱已被使用或班级不存在
        """
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        
        if not user:
            raise ValueError("用户不存在")
        
        # 检查邮箱是否已被其他用户使用
        if email and email != user.email:
            existing = db.query(User).filter(
                User.email == email,
                User.id != uuid.UUID(user_id)
            ).first()
            if existing:
                raise ValueError("邮箱已被使用")
        
        # 如果更新班级ID，验证班级是否存在
        if class_id is not None and class_id != '':
            from models.class_model import Class
            cls = db.query(Class).filter(Class.id == uuid.UUID(class_id)).first()
            if not cls:
                raise ValueError("班级不存在")
            user.class_id = uuid.UUID(class_id)
        elif class_id == '':
            # 空字符串表示退出班级
            user.class_id = None
        
        # 更新字段
        if name is not None:
            user.name = name
        if email is not None:
            user.email = email
        if phone is not None:
            user.phone = phone
        if student_id is not None:
            user.student_id = student_id
        
        db.commit()
        db.refresh(user)
        
        return {
            "id": str(user.id),
            "account": user.account,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "student_id": user.student_id,
            "class_id": str(user.class_id) if user.class_id else None,
            "message": "更新成功"
        }
