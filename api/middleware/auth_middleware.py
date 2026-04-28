"""
权限验证中间件
提供JWT令牌验证和角色权限控制
"""
import uuid
from typing import Optional
from functools import wraps
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from logging_config import get_logger
from database import get_db
from models.user import User
from utils.security import verify_token

logger = get_logger(__name__)

# HTTP Bearer认证方案
security = HTTPBearer()


async def verify_token_middleware(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    验证JWT令牌中间件
    
    Args:
        credentials: HTTP Bearer认证凭证
        db: 数据库会话
        
    Returns:
        当前用户对象
        
    Raises:
        HTTPException: 令牌无效或用户不存在
    """
    try:
        # 获取令牌
        token = credentials.credentials
        
        # 验证令牌
        payload = verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 获取用户ID - 支持多种字段名
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌中缺少用户信息",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 查询用户
        user_key = user_id
        try:
            user_key = uuid.UUID(str(user_id))
        except Exception:
            user_key = user_id
        user = db.query(User).filter(User.id == user_key).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 检查用户是否被删除（通过账号名判断）
        if user.account.startswith("deleted_"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账户已被删除"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌验证失败",
            headers={"WWW-Authenticate": "Bearer"}
        )


def require_teacher(current_user: User = Depends(verify_token_middleware)) -> User:
    """
    要求教师权限的装饰器依赖
    
    Args:
        current_user: 当前用户
        
    Returns:
        当前用户（如果是教师）
        
    Raises:
        HTTPException: 用户不是教师
    """
    if current_user.user_type != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要教师权限"
        )
    return current_user


def require_student(current_user: User = Depends(verify_token_middleware)) -> User:
    """
    要求学生权限的装饰器依赖
    
    Args:
        current_user: 当前用户
        
    Returns:
        当前用户（如果是学生）
        
    Raises:
        HTTPException: 用户不是学生
    """
    if current_user.user_type != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要学生权限"
        )
    return current_user


def require_role(allowed_roles: list[str]):
    """
    要求特定角色权限的装饰器依赖工厂函数
    
    Args:
        allowed_roles: 允许的角色列表，例如 ["administrator"] 或 ["teacher", "administrator"]
        
    Returns:
        依赖函数，用于验证用户角色
        
    Example:
        @router.get("/admin/classes", dependencies=[Depends(require_role(["administrator"]))])
        async def get_all_classes():
            ...
    """
    def role_checker(current_user: User = Depends(verify_token_middleware)) -> User:
        """
        检查当前用户是否具有所需角色
        
        Args:
            current_user: 当前用户
            
        Returns:
            当前用户（如果具有所需角色）
            
        Raises:
            HTTPException: 用户不具有所需角色
        """
        if current_user.user_type not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"访问被拒绝。需要以下角色之一: {', '.join(allowed_roles)}"
            )
        return current_user
    
    return role_checker


def check_class_access(
    teacher_id: str,
    class_id: str,
    db: Session
) -> bool:
    """
    检查教师是否有权访问指定班级
    
    Args:
        teacher_id: 教师ID
        class_id: 班级ID
        db: 数据库会话
        
    Returns:
        是否有权访问
    """
    from models.class_model import Class
    
    class_obj = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher_id
    ).first()
    
    return class_obj is not None


def check_student_access(
    student_id: str,
    target_student_id: str
) -> bool:
    """
    检查学生是否有权访问指定学生的数据
    
    Args:
        student_id: 当前学生ID
        target_student_id: 目标学生ID
        
    Returns:
        是否有权访问（只能访问自己的数据）
    """
    return student_id == target_student_id


def check_debate_access(
    user_id: str,
    debate_id: str,
    db: Session
) -> bool:
    """
    检查用户是否有权访问指定辩论
    
    Args:
        user_id: 用户ID
        debate_id: 辩论ID
        db: 数据库会话
        
    Returns:
        是否有权访问
    """
    from models.debate import Debate, DebateParticipation
    from models.class_model import Class
    
    # 查询用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    # 如果是教师，检查辩论是否属于其班级
    if user.user_type == "teacher":
        debate = db.query(Debate).join(
            Class, Debate.class_id == Class.id
        ).filter(
            Debate.id == debate_id,
            Class.teacher_id == user_id
        ).first()
        return debate is not None
    
    # 如果是学生，检查是否参与了该辩论
    elif user.user_type == "student":
        participation = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_id,
            DebateParticipation.user_id == user_id
        ).first()
        return participation is not None
    
    return False


def check_document_access(
    user_id: str,
    document_id: str,
    db: Session
) -> bool:
    """
    检查用户是否有权访问指定文档
    
    Args:
        user_id: 用户ID
        document_id: 文档ID
        db: 数据库会话
        
    Returns:
        是否有权访问
    """
    from models.document import Document
    from models.debate import Debate
    from models.class_model import Class
    
    # 查询文档
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return False
    
    # 检查辩论访问权限
    return check_debate_access(user_id, str(document.debate_id), db)


class PermissionChecker:
    """权限检查器类"""
    
    def __init__(self, db: Session):
        """
        初始化权限检查器
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    def can_access_class(self, user: User, class_id: str) -> bool:
        """
        检查用户是否可以访问班级
        
        Args:
            user: 用户对象
            class_id: 班级ID
            
        Returns:
            是否有权访问
        """
        if user.user_type == "teacher":
            return check_class_access(str(user.id), class_id, self.db)
        elif user.user_type == "student":
            return str(user.class_id) == class_id
        return False
    
    def can_access_student(self, user: User, student_id: str) -> bool:
        """
        检查用户是否可以访问学生数据
        
        Args:
            user: 用户对象
            student_id: 学生ID
            
        Returns:
            是否有权访问
        """
        if user.user_type == "teacher":
            # 教师可以访问其班级的学生
            student = self.db.query(User).filter(User.id == student_id).first()
            if not student:
                return False
            return check_class_access(str(user.id), str(student.class_id), self.db)
        elif user.user_type == "student":
            # 学生只能访问自己的数据
            return check_student_access(str(user.id), student_id)
        return False
    
    def can_access_debate(self, user: User, debate_id: str) -> bool:
        """
        检查用户是否可以访问辩论
        
        Args:
            user: 用户对象
            debate_id: 辩论ID
            
        Returns:
            是否有权访问
        """
        return check_debate_access(str(user.id), debate_id, self.db)
    
    def can_access_document(self, user: User, document_id: str) -> bool:
        """
        检查用户是否可以访问文档
        
        Args:
            user: 用户对象
            document_id: 文档ID
            
        Returns:
            是否有权访问
        """
        return check_document_access(str(user.id), document_id, self.db)
    
    def can_modify_debate(self, user: User, debate_id: str) -> bool:
        """
        检查用户是否可以修改辩论
        
        Args:
            user: 用户对象
            debate_id: 辩论ID
            
        Returns:
            是否有权修改（只有教师可以修改）
        """
        if user.user_type != "teacher":
            return False
        return self.can_access_debate(user, debate_id)
    
    def can_delete_student(self, user: User, student_id: str) -> bool:
        """
        检查用户是否可以删除学生
        
        Args:
            user: 用户对象
            student_id: 学生ID
            
        Returns:
            是否有权删除（只有教师可以删除其班级的学生）
        """
        if user.user_type != "teacher":
            return False
        return self.can_access_student(user, student_id)
