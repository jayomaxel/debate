"""
Profile service.
"""
from typing import Any, Dict, Optional
import uuid

from sqlalchemy.orm import Session

from models.user import User
from services.avatar_service import AvatarService
from utils.user_email import build_placeholder_email, to_public_email


class ProfileService:
    """User profile service."""

    @staticmethod
    def _get_user(db: Session, user_id: str) -> User:
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if not user:
            raise ValueError("用户不存在")
        return user

    @staticmethod
    def serialize_profile(user: User) -> Dict[str, Any]:
        avatar_payload = AvatarService.build_avatar_payload(user)
        return {
            "id": str(user.id),
            "account": user.account,
            "name": user.name,
            "email": to_public_email(user.email),
            "phone": user.phone,
            "student_id": user.student_id,
            "class_id": str(user.class_id) if user.class_id else None,
            "user_type": user.user_type,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            **avatar_payload,
        }

    @staticmethod
    def get_profile(db: Session, user_id: str) -> Dict[str, Any]:
        user = ProfileService._get_user(db, user_id)
        return ProfileService.serialize_profile(user)

    @staticmethod
    def update_profile(
        db: Session,
        user_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        student_id: Optional[str] = None,
        class_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        user = ProfileService._get_user(db, user_id)
        normalized_email = email.strip() if email is not None else None
        normalized_class_id = class_id.strip() if class_id is not None else None
        current_public_email = to_public_email(user.email)

        if normalized_email and normalized_email != current_public_email:
            existing = db.query(User).filter(
                User.email == normalized_email,
                User.id != uuid.UUID(user_id),
            ).first()
            if existing:
                raise ValueError("邮箱已被使用")

        if class_id is not None:
            if user.user_type != "student":
                raise ValueError("仅学生可以设置班级")

            current_class_id = str(user.class_id) if user.class_id else None
            if current_class_id:
                if not normalized_class_id or normalized_class_id != current_class_id:
                    raise ValueError("学生选择班级后不可修改，请联系管理员处理")
            elif normalized_class_id:
                from models.class_model import Class

                cls = db.query(Class).filter(
                    Class.id == uuid.UUID(normalized_class_id)
                ).first()
                if not cls:
                    raise ValueError("班级不存在")
                user.class_id = uuid.UUID(normalized_class_id)
            else:
                user.class_id = None

        if name is not None:
            cleaned_name = name.strip()
            if not cleaned_name:
                raise ValueError("姓名不能为空")
            user.name = cleaned_name

        if email is not None:
            if normalized_email:
                user.email = normalized_email
            elif user.user_type == "student":
                user.email = build_placeholder_email(user.account)
            else:
                raise ValueError("邮箱不能为空")

        if phone is not None:
            user.phone = phone.strip() or None

        if student_id is not None:
            user.student_id = student_id.strip() or None

        db.commit()
        db.refresh(user)
        return ProfileService.serialize_profile(user)
