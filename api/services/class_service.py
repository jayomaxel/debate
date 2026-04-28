"""
班级管理服务
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.class_model import Class
from models.user import User
import uuid
import random
import string


class ClassService:
    """班级管理服务类"""
    
    @staticmethod
    def generate_class_code() -> str:
        """
        生成唯一的6位班级代码
        
        Returns:
            6位字母数字组合的班级代码
        """
        # 生成6位大写字母和数字的组合
        characters = string.ascii_uppercase + string.digits
        return ''.join(random.choices(characters, k=6))
    
    @staticmethod
    def create_class(
        db: Session,
        teacher_id: str,
        name: str
    ) -> Dict[str, Any]:
        """
        创建班级
        
        Args:
            db: 数据库会话
            teacher_id: 教师ID
            name: 班级名称
            
        Returns:
            包含班级信息的字典
            
        Raises:
            ValueError: 如果教师不存在或班级代码生成失败
        """
        # 验证教师是否存在
        teacher = db.query(User).filter(
            User.id == uuid.UUID(teacher_id),
            User.user_type == 'teacher'
        ).first()
        
        if not teacher:
            raise ValueError("教师不存在")
        
        # 生成唯一的班级代码（最多尝试10次）
        max_attempts = 10
        class_code = None
        
        for _ in range(max_attempts):
            code = ClassService.generate_class_code()
            existing = db.query(Class).filter(Class.code == code).first()
            if not existing:
                class_code = code
                break
        
        if not class_code:
            raise ValueError("生成班级代码失败，请重试")
        
        # 创建班级
        new_class = Class(
            id=uuid.uuid4(),
            name=name,
            code=class_code,
            teacher_id=uuid.UUID(teacher_id)
        )
        
        try:
            db.add(new_class)
            db.commit()
            db.refresh(new_class)
        except IntegrityError:
            db.rollback()
            raise ValueError("创建班级失败")
        
        return {
            "id": str(new_class.id),
            "name": new_class.name,
            "code": new_class.code,
            "teacher_id": str(new_class.teacher_id),
            "created_at": new_class.created_at.isoformat()
        }
    
    @staticmethod
    def get_classes(
        db: Session,
        teacher_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取教师的所有班级
        
        Args:
            db: 数据库会话
            teacher_id: 教师ID
            
        Returns:
            班级列表
        """
        classes = db.query(Class).filter(
            Class.teacher_id == uuid.UUID(teacher_id)
        ).all()
        
        result = []
        for cls in classes:
            # 统计学生数量
            student_count = db.query(User).filter(
                User.class_id == cls.id
            ).count()
            
            result.append({
                "id": str(cls.id),
                "name": cls.name,
                "code": cls.code,
                "student_count": student_count,
                "created_at": cls.created_at.isoformat()
            })
        
        return result
    
    @staticmethod
    def get_class_by_id(
        db: Session,
        class_id: str,
        teacher_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        根据ID获取班级信息
        
        Args:
            db: 数据库会话
            class_id: 班级ID
            teacher_id: 教师ID（可选，用于权限验证）
            
        Returns:
            班级信息字典，如果不存在则返回None
        """
        query = db.query(Class).filter(Class.id == uuid.UUID(class_id))
        
        if teacher_id:
            query = query.filter(Class.teacher_id == uuid.UUID(teacher_id))
        
        cls = query.first()
        
        if not cls:
            return None
        
        # 统计学生数量
        student_count = db.query(User).filter(
            User.class_id == cls.id
        ).count()
        
        return {
            "id": str(cls.id),
            "name": cls.name,
            "code": cls.code,
            "teacher_id": str(cls.teacher_id),
            "student_count": student_count,
            "created_at": cls.created_at.isoformat()
        }
    
    # Administrator-specific methods
    
    @staticmethod
    def get_all_classes(db: Session) -> List[Dict[str, Any]]:
        """
        获取所有班级（管理员专用）
        
        Args:
            db: 数据库会话
            
        Returns:
            所有班级的列表，包含教师名称和学生数量
        """
        classes = db.query(Class).all()
        
        result = []
        for cls in classes:
            # 获取教师信息
            teacher = db.query(User).filter(User.id == cls.teacher_id).first()
            teacher_name = teacher.name if teacher else "Unknown"
            
            # 统计学生数量
            student_count = db.query(User).filter(
                User.class_id == cls.id
            ).count()
            
            result.append({
                "id": str(cls.id),
                "name": cls.name,
                "code": cls.code,
                "teacher_id": str(cls.teacher_id),
                "teacher_name": teacher_name,
                "student_count": student_count,
                "created_at": cls.created_at.isoformat()
            })
        
        return result
    
    @staticmethod
    def create_class_for_teacher(
        db: Session,
        teacher_id: str,
        name: str
    ) -> Dict[str, Any]:
        """
        为指定教师创建班级（管理员专用）
        
        Args:
            db: 数据库会话
            teacher_id: 教师ID
            name: 班级名称
            
        Returns:
            包含班级信息的字典
            
        Raises:
            ValueError: 如果教师不存在或班级代码生成失败
        """
        # 验证教师是否存在
        teacher = db.query(User).filter(
            User.id == uuid.UUID(teacher_id),
            User.user_type == 'teacher'
        ).first()
        
        if not teacher:
            raise ValueError("教师不存在")
        
        # 生成唯一的班级代码（最多尝试10次）
        max_attempts = 10
        class_code = None
        
        for _ in range(max_attempts):
            code = ClassService.generate_class_code()
            existing = db.query(Class).filter(Class.code == code).first()
            if not existing:
                class_code = code
                break
        
        if not class_code:
            raise ValueError("生成班级代码失败，请重试")
        
        # 创建班级
        new_class = Class(
            id=uuid.uuid4(),
            name=name,
            code=class_code,
            teacher_id=uuid.UUID(teacher_id)
        )
        
        try:
            db.add(new_class)
            db.commit()
            db.refresh(new_class)
        except IntegrityError:
            db.rollback()
            raise ValueError("创建班级失败")
        
        return {
            "id": str(new_class.id),
            "name": new_class.name,
            "code": new_class.code,
            "teacher_id": str(new_class.teacher_id),
            "teacher_name": teacher.name,
            "student_count": 0,
            "created_at": new_class.created_at.isoformat()
        }
    
    @staticmethod
    def update_any_class(
        db: Session,
        class_id: str,
        name: Optional[str] = None,
        teacher_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更新任意班级（管理员专用）
        
        Args:
            db: 数据库会话
            class_id: 班级ID
            name: 新的班级名称（可选）
            teacher_id: 新的教师ID（可选）
            
        Returns:
            更新后的班级信息字典
            
        Raises:
            ValueError: 如果班级不存在或教师不存在
        """
        # 查找班级
        cls = db.query(Class).filter(Class.id == uuid.UUID(class_id)).first()
        
        if not cls:
            raise ValueError("班级不存在")
        
        # 更新班级名称
        if name is not None:
            cls.name = name
        
        # 更新教师
        if teacher_id is not None:
            # 验证新教师是否存在
            teacher = db.query(User).filter(
                User.id == uuid.UUID(teacher_id),
                User.user_type == 'teacher'
            ).first()
            
            if not teacher:
                raise ValueError("教师不存在")
            
            cls.teacher_id = uuid.UUID(teacher_id)
        
        try:
            db.commit()
            db.refresh(cls)
        except IntegrityError:
            db.rollback()
            raise ValueError("更新班级失败")
        
        # 获取教师信息
        teacher = db.query(User).filter(User.id == cls.teacher_id).first()
        teacher_name = teacher.name if teacher else "Unknown"
        
        # 统计学生数量
        student_count = db.query(User).filter(
            User.class_id == cls.id
        ).count()
        
        return {
            "id": str(cls.id),
            "name": cls.name,
            "code": cls.code,
            "teacher_id": str(cls.teacher_id),
            "teacher_name": teacher_name,
            "student_count": student_count,
            "created_at": cls.created_at.isoformat()
        }
    
    @staticmethod
    def delete_any_class(
        db: Session,
        class_id: str
    ) -> bool:
        """
        删除任意班级并处理学生注册（管理员专用）
        
        Args:
            db: 数据库会话
            class_id: 班级ID
            
        Returns:
            True 如果删除成功
            
        Raises:
            ValueError: 如果班级不存在
        """
        # 查找班级
        cls = db.query(Class).filter(Class.id == uuid.UUID(class_id)).first()
        
        if not cls:
            raise ValueError("班级不存在")
        
        try:
            # 将所有学生的 class_id 设置为 None（取消注册）
            db.query(User).filter(User.class_id == cls.id).update(
                {"class_id": None},
                synchronize_session=False
            )
            
            # 删除班级
            db.delete(cls)
            db.commit()
            
            return True
        except Exception as e:
            db.rollback()
            raise ValueError(f"删除班级失败: {str(e)}")
