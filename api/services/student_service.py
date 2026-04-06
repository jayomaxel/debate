"""
学生管理服务
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from models.user import User
from models.class_model import Class
from models.debate import DebateParticipation, Debate
from models.score import Score
from utils.security import hash_password
import uuid
import csv
import io


class StudentService:
    """学生管理服务类"""
    
    @staticmethod
    def add_student(
        db: Session,
        account: str,
        password: str,
        name: str,
        class_id: str,
        email: Optional[str] = None,
        student_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        添加学生
        
        Args:
            db: 数据库会话
            account: 账号
            password: 密码
            name: 姓名
            class_id: 班级ID
            email: 邮箱（可选）
            student_id: 学号（可选）
            
        Returns:
            包含学生信息的字典
            
        Raises:
            ValueError: 如果账号已存在或班级不存在
        """
        # 验证班级是否存在
        cls = db.query(Class).filter(Class.id == uuid.UUID(class_id)).first()
        if not cls:
            raise ValueError("班级不存在")
        
        # 检查账号是否已存在
        existing_user = db.query(User).filter(User.account == account).first()
        if existing_user:
            raise ValueError("账号已存在")
        
        # 如果提供了邮箱，检查邮箱是否已存在
        if email:
            existing_email = db.query(User).filter(User.email == email).first()
            if existing_email:
                raise ValueError("邮箱已被注册")
        
        # 创建学生
        student = User(
            id=uuid.uuid4(),
            account=account,
            password_hash=hash_password(password),
            user_type='student',
            name=name,
            email=email or f"{account}@temp.com",
            student_id=student_id,
            class_id=uuid.UUID(class_id)
        )
        
        try:
            db.add(student)
            db.commit()
            db.refresh(student)
        except IntegrityError:
            db.rollback()
            raise ValueError("添加学生失败")
        
        return {
            "id": str(student.id),
            "account": student.account,
            "name": student.name,
            "email": student.email,
            "student_id": student.student_id,
            "class_id": str(student.class_id)
        }
    
    @staticmethod
    def batch_import_students(
        db: Session,
        csv_content: str,
        class_id: str
    ) -> Dict[str, Any]:
        """
        批量导入学生（从CSV内容）
        
        CSV格式：account,password,name,email,student_id
        
        Args:
            db: 数据库会话
            csv_content: CSV文件内容
            class_id: 班级ID
            
        Returns:
            导入结果统计
        """
        # 验证班级是否存在
        cls = db.query(Class).filter(Class.id == uuid.UUID(class_id)).first()
        if not cls:
            raise ValueError("班级不存在")
        
        # 解析CSV
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        success_count = 0
        failed_count = 0
        errors = []
        
        for row in reader:
            try:
                account = row.get('account', '').strip()
                password = row.get('password', '').strip()
                name = row.get('name', '').strip()
                email = row.get('email', '').strip() or None
                student_id = row.get('student_id', '').strip() or None
                
                if not account or not password or not name:
                    failed_count += 1
                    errors.append(f"行数据不完整: {row}")
                    continue
                
                StudentService.add_student(
                    db=db,
                    account=account,
                    password=password,
                    name=name,
                    class_id=class_id,
                    email=email,
                    student_id=student_id
                )
                success_count += 1
                
            except ValueError as e:
                failed_count += 1
                errors.append(f"{account}: {str(e)}")
            except Exception as e:
                failed_count += 1
                errors.append(f"{account}: 未知错误 - {str(e)}")
        
        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors
        }
    
    @staticmethod
    def get_students(
        db: Session,
        class_id: Optional[str] = None,
        teacher_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取学生列表
        
        Args:
            db: 数据库会话
            class_id: 班级ID（可选）
            teacher_id: 教师ID（可选，用于获取该教师所有班级的学生）
            
        Returns:
            学生列表
        """
        query = db.query(User).filter(User.user_type == 'student')
        
        if class_id:
            query = query.filter(User.class_id == uuid.UUID(class_id))
        elif teacher_id:
            # 获取该教师的所有班级
            class_ids = db.query(Class.id).filter(
                Class.teacher_id == uuid.UUID(teacher_id)
            ).all()
            class_ids = [cid[0] for cid in class_ids]
            query = query.filter(User.class_id.in_(class_ids))
        
        students = query.all()
        
        result = []
        for student in students:
            # 统计参与次数
            participation_count = db.query(DebateParticipation).filter(
                DebateParticipation.user_id == student.id
            ).count()
            
            # 计算平均分
            avg_score = db.query(func.avg(Score.overall_score)).join(
                DebateParticipation
            ).filter(
                DebateParticipation.user_id == student.id
            ).scalar()
            
            result.append({
                "id": str(student.id),
                "account": student.account,
                "name": student.name,
                "email": student.email,
                "student_id": student.student_id,
                "class_id": str(student.class_id) if student.class_id else None,
                "participation_count": participation_count,
                "average_score": round(float(avg_score), 2) if avg_score else 0.0
            })
        
        return result
    
    @staticmethod
    def delete_student(
        db: Session,
        student_id: str
    ) -> bool:
        """
        删除学生（软删除，保留历史数据）
        
        Args:
            db: 数据库会话
            student_id: 学生ID
            
        Returns:
            是否删除成功
            
        Raises:
            ValueError: 如果学生不存在
        """
        student = db.query(User).filter(
            User.id == uuid.UUID(student_id),
            User.user_type == 'student'
        ).first()
        
        if not student:
            raise ValueError("学生不存在")
        
        # 软删除：移除班级关联，但保留用户记录和历史数据
        student.class_id = None
        student.account = f"deleted_{student.account}"  # 标记为已删除
        
        db.commit()
        return True
