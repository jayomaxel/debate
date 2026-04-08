"""
教师端API路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List

from logging_config import get_logger
from database import get_db
from models.user import User
from services.class_service import ClassService
from services.student_service import StudentService
from services.debate_service import DebateService
from services.analytics_service import AnalyticsService
from middleware.auth_middleware import require_teacher, PermissionChecker

logger = get_logger(__name__)

router = APIRouter(prefix="/api/teacher", tags=["教师端"])


# Pydantic模型
class CreateClassRequest(BaseModel):
    name: str


class AddStudentRequest(BaseModel):
    account: str
    password: str
    name: str
    class_id: str
    email: Optional[EmailStr] = None
    student_id: Optional[str] = None


class CreateDebateRequest(BaseModel):
    class_id: str
    topic: str
    duration: int
    description: Optional[str] = None
    student_ids: Optional[List[str]] = None
    status: Optional[str] = None


# ==================== 班级管理 ====================

@router.post("/classes", summary="创建班级")
async def create_class(
    request: CreateClassRequest,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """创建班级"""
    try:
        result = ClassService.create_class(
            db=db,
            teacher_id=str(current_user.id),
            name=request.name
        )
        return {
            "code": 200,
            "message": "创建成功",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/classes", summary="获取班级列表")
async def get_classes(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """获取教师的所有班级"""
    try:
        classes = ClassService.get_classes(
            db=db,
            teacher_id=str(current_user.id)
        )
        return {
            "code": 200,
            "message": "获取成功",
            "data": classes
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/dashboard", summary="鑾峰彇鏁欏笀鎺у埗鍙扮粺璁?")
async def get_teacher_dashboard(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """鑾峰彇鏁欏笀鎺у埗鍙扮粺璁版嵁"""
    try:
        analytics = AnalyticsService(db)
        return {
            "code": 200,
            "message": "鑾峰彇鎴愬姛",
            "data": analytics.get_teacher_dashboard(str(current_user.id))
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 学生管理 ====================

@router.post("/students", summary="添加学生")
async def add_student(
    request: AddStudentRequest,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """添加学生"""
    checker = PermissionChecker(db)
    if not checker.can_access_class(current_user, request.class_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该班级"
        )
    
    try:
        result = StudentService.add_student(
            db=db,
            account=request.account,
            password=request.password,
            name=request.name,
            class_id=request.class_id,
            email=request.email,
            student_id=request.student_id
        )
        return {
            "code": 200,
            "message": "添加成功",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/students", summary="获取学生列表")
async def get_students(
    class_id: Optional[str] = None,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """获取学生列表"""
    if class_id:
        checker = PermissionChecker(db)
        if not checker.can_access_class(current_user, class_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该班级"
            )
    
    try:
        students = StudentService.get_students(
            db=db,
            teacher_id=str(current_user.id),
            class_id=class_id
        )
        return {
            "code": 200,
            "message": "获取成功",
            "data": students
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 辩论管理 ====================

@router.post("/debates", summary="创建辩论")
async def create_debate(
    request: CreateDebateRequest,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """创建辩论任务"""
    checker = PermissionChecker(db)
    if not checker.can_access_class(current_user, request.class_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该班级"
        )
    
    try:
        result = await DebateService.create_debate(
            db=db,
            teacher_id=str(current_user.id),
            class_id=request.class_id,
            topic=request.topic,
            duration=request.duration,
            description=request.description,
            student_ids=request.student_ids,
            status=request.status,
        )
        return {
            "code": 200,
            "message": "创建成功",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/debates/{debate_id}", summary="更新辩论")
async def update_debate(
    debate_id: str,
    request: CreateDebateRequest,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """更新辩论任务"""
    checker = PermissionChecker(db)
    if not checker.can_access_class(current_user, request.class_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该班级"
        )
    
    try:
        result = await DebateService.update_debate(
            db=db,
            teacher_id=str(current_user.id),
            debate_id=debate_id,
            class_id=request.class_id,
            topic=request.topic,
            duration=request.duration,
            description=request.description,
            student_ids=request.student_ids,
            status=request.status,
        )
        return {
            "code": 200,
            "message": "更新成功",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/debates/{debate_id}", summary="获取辩论详情")
async def get_debate(
    debate_id: str,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """获取单个辩论详情"""
    try:
        # 先检查辩论是否存在及归属
        debate = DebateService.get_debate(db, debate_id)
        if not debate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="辩论不存在"
            )
            
        # 检查权限（是否是该教师的班级）
        if debate["teacher_id"] != str(current_user.id):
             # 也可以检查 class_id 是否属于该教师，双重保险
             pass
        
        # 实际上 get_debate 没有检查 teacher_id，所以这里需要检查
        if debate["teacher_id"] != str(current_user.id):
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该辩论"
            )

        return {
            "code": 200,
            "message": "获取成功",
            "data": debate
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/debates", summary="获取辩论列表")
async def get_debates(
    class_id: Optional[str] = None,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """获取辩论列表"""
    if class_id:
        checker = PermissionChecker(db)
        if not checker.can_access_class(current_user, class_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该班级"
            )
    
    try:
        debates = DebateService.get_debates(
            db=db,
            teacher_id=str(current_user.id),
            class_id=class_id
        )
        return {
            "code": 200,
            "message": "获取成功",
            "data": debates
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 配置管理已迁移至管理员端 ====================
# 配置管理功能已移至 /api/admin/config 路由
# 使用 model_config 和 coze_config 表
