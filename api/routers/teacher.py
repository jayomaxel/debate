"""
教师端API路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Literal, Optional, List

from logging_config import get_logger
from database import get_db
from models.user import User
from models.document import Document
from services.class_service import ClassService
from services.student_service import StudentService
from services.debate_service import DebateService
from services.analytics_service import AnalyticsService
from services.knowledge_base import KnowledgeBase
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


class DebateActivityFocusRequest(BaseModel):
    chapter_focus: Optional[str] = None
    training_focus: Optional[str] = None
    classroom_scene: Optional[str] = None


class DebateConfigMetaRequest(BaseModel):
    mode: Optional[Literal["competition", "teaching"]] = None
    role_assignment_mode: Optional[Literal["strength_first", "growth_first"]] = None
    assignment_policy: Optional[Literal["ai_auto_assign", "ai_recommend_then_confirm"]] = None
    role_rotation_policy: Optional[Literal["balanced_rotation", "strength_priority", "growth_priority"]] = None
    fairness_window_size: Optional[int] = None
    same_role_max_streak: Optional[int] = None
    rounds: Optional[int] = None
    knowledge_points: Optional[List[str]] = None
    objective: Optional[List[str]] = None
    evaluation_focus: Optional[List[str]] = None
    forbidden_moves: Optional[List[str]] = None
    support_document_ids: Optional[List[str]] = None
    domain_pack_id: Optional[str] = None
    teaching_design_version_id: Optional[str] = None
    activity_focus: Optional[DebateActivityFocusRequest] = None


class RoleAssignmentRequest(BaseModel):
    user_id: str
    role: Literal["debater_1", "debater_2", "debater_3", "debater_4"]


class CreateDebateRequest(BaseModel):
    class_id: str
    topic: str
    duration: int
    description: Optional[str] = None
    config_meta: Optional[DebateConfigMetaRequest] = None
    student_ids: Optional[List[str]] = None
    role_assignments: Optional[List[RoleAssignmentRequest]] = None
    status: Optional[str] = None


class UpdateDebateRequest(BaseModel):
    class_id: Optional[str] = None
    topic: Optional[str] = None
    duration: Optional[int] = None
    description: Optional[str] = None
    config_meta: Optional[DebateConfigMetaRequest] = None
    student_ids: Optional[List[str]] = None
    role_assignments: Optional[List[RoleAssignmentRequest]] = None
    status: Optional[str] = None


class CreateReservationRequest(BaseModel):
    class_id: str
    topic: str
    duration: int
    description: Optional[str] = None
    config_meta: Optional[DebateConfigMetaRequest] = None
    scheduled_start_time: str
    checkin_open_time: Optional[str] = None
    checkin_close_time: Optional[str] = None
    student_ids: List[str]
    role_assignments: Optional[List[RoleAssignmentRequest]] = None
    visibility: str = "private"
    password: Optional[str] = None
    host_user_id: Optional[str] = None


class UpdateReservationRequest(BaseModel):
    topic: Optional[str] = None
    duration: Optional[int] = None
    description: Optional[str] = None
    config_meta: Optional[DebateConfigMetaRequest] = None
    scheduled_start_time: Optional[str] = None
    checkin_open_time: Optional[str] = None
    checkin_close_time: Optional[str] = None
    student_ids: Optional[List[str]] = None
    role_assignments: Optional[List[RoleAssignmentRequest]] = None
    visibility: Optional[str] = None
    password: Optional[str] = None
    host_user_id: Optional[str] = None


class CancelReservationRequest(BaseModel):
    cancel_reason: Optional[str] = None


class PreviewRoleAssignmentRequest(BaseModel):
    class_id: str
    student_ids: List[str]
    config_meta: Optional[DebateConfigMetaRequest] = None
    role_assignments: Optional[List[RoleAssignmentRequest]] = None


def _config_meta_payload(config_meta: Optional[DebateConfigMetaRequest]) -> Optional[dict]:
    return config_meta.model_dump(exclude_none=True) if config_meta is not None else None


def _role_assignments_payload(role_assignments: Optional[List[RoleAssignmentRequest]]) -> Optional[List[dict]]:
    if role_assignments is None:
        return None
    return [item.model_dump(exclude_none=True) for item in role_assignments]


def _serialize_support_document(document: Document) -> dict:
    return {
        "id": str(document.id),
        "filename": document.filename,
        "file_type": document.file_type,
        "embedding_status": document.embedding_status,
        "uploaded_at": document.uploaded_at.isoformat()
        if document.uploaded_at
        else None,
    }


def _ensure_teacher_can_modify_debate(
    db: Session,
    current_user: User,
    debate_id: str,
) -> None:
    checker = PermissionChecker(db)
    if not checker.can_modify_debate(current_user, debate_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该辩论",
        )


def _resolve_support_file_type(file: UploadFile) -> str:
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    if content_type == "application/pdf" or filename.endswith(".pdf"):
        return "application/pdf"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="教师端支撑材料仅支持 PDF 文件",
    )


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


@router.get("/dashboard", summary="获取教师控制台统计")
async def get_teacher_dashboard(
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """获取教师控制台统计数据"""
    try:
        analytics = AnalyticsService(db)
        return {
            "code": 200,
            "message": "获取成功",
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
            config_meta=_config_meta_payload(request.config_meta),
            student_ids=request.student_ids,
            role_assignments=_role_assignments_payload(request.role_assignments),
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
    request: UpdateDebateRequest,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    """更新辩论任务"""
    checker = PermissionChecker(db)
    if not checker.can_modify_debate(current_user, debate_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该辩论"
        )
    if request.class_id and not checker.can_access_class(current_user, request.class_id):
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
            config_meta=_config_meta_payload(request.config_meta),
            student_ids=request.student_ids,
            role_assignments=_role_assignments_payload(request.role_assignments),
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


@router.post("/debates/role-assignment-preview", summary="预览 AI 辩位分配")
async def preview_role_assignment(
    request: PreviewRoleAssignmentRequest,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db)
):
    checker = PermissionChecker(db)
    if not checker.can_access_class(current_user, request.class_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该班级"
        )

    try:
        result = DebateService.preview_role_assignment(
            db=db,
            teacher_id=str(current_user.id),
            class_id=request.class_id,
            student_ids=request.student_ids,
            config_meta=_config_meta_payload(request.config_meta),
            role_assignments=_role_assignments_payload(request.role_assignments),
        )
        return {
            "code": 200,
            "message": "获取成功",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==================== 预约制辩论管理 ====================

@router.post("/reservations", summary="创建预约辩论赛")
async def create_reservation(
    request: CreateReservationRequest,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    checker = PermissionChecker(db)
    if not checker.can_access_class(current_user, request.class_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该班级",
        )
    try:
        result = await DebateService.create_reservation(
            db=db,
            teacher_id=str(current_user.id),
            class_id=request.class_id,
            topic=request.topic,
            duration=request.duration,
            description=request.description,
            config_meta=_config_meta_payload(request.config_meta),
            scheduled_start_time=request.scheduled_start_time,
            checkin_open_time=request.checkin_open_time,
            checkin_close_time=request.checkin_close_time,
            student_ids=request.student_ids,
            role_assignments=_role_assignments_payload(request.role_assignments),
            visibility=request.visibility,
            password=request.password,
            host_user_id=request.host_user_id,
        )
        return {"code": 200, "message": "创建成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/reservations", summary="获取预约辩论赛列表")
async def list_reservations(
    class_id: Optional[str] = None,
    reservation_status: Optional[str] = Query(None, alias="status"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.list_teacher_reservations(
            db=db,
            teacher_id=str(current_user.id),
            class_id=class_id,
            status=reservation_status,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        return {"code": 200, "message": "获取成功", "data": result}
    except ValueError as e:
        detail = str(e)
        http_status = status.HTTP_403_FORBIDDEN if "无权限" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=detail)


@router.get("/reservations/{reservation_id}", summary="获取预约辩论赛详情")
async def get_reservation(
    reservation_id: str,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.get_teacher_reservation(
            db=db,
            teacher_id=str(current_user.id),
            reservation_id=reservation_id,
        )
        return {"code": 200, "message": "获取成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/reservations/{reservation_id}", summary="更新预约辩论赛")
async def update_reservation(
    reservation_id: str,
    request: UpdateReservationRequest,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    try:
        result = await DebateService.update_reservation(
            db=db,
            teacher_id=str(current_user.id),
            reservation_id=reservation_id,
            topic=request.topic,
            description=request.description,
            config_meta=_config_meta_payload(request.config_meta),
            duration=request.duration,
            scheduled_start_time=request.scheduled_start_time,
            checkin_open_time=request.checkin_open_time,
            checkin_close_time=request.checkin_close_time,
            student_ids=request.student_ids,
            role_assignments=_role_assignments_payload(request.role_assignments),
            visibility=request.visibility,
            password=request.password,
            host_user_id=request.host_user_id,
        )
        return {"code": 200, "message": "更新成功", "data": result}
    except ValueError as e:
        detail = str(e)
        http_status = status.HTTP_409_CONFLICT if "无法" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=detail)


@router.post("/reservations/{reservation_id}/cancel", summary="取消预约辩论赛")
async def cancel_reservation(
    reservation_id: str,
    request: CancelReservationRequest,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.cancel_reservation(
            db=db,
            teacher_id=str(current_user.id),
            reservation_id=reservation_id,
            cancel_reason=request.cancel_reason,
        )
        return {"code": 200, "message": "取消成功", "data": result}
    except ValueError as e:
        detail = str(e)
        http_status = status.HTTP_409_CONFLICT if "无法" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=detail)


@router.get(
    "/debates/{debate_id}/support-documents",
    summary="获取辩论支撑材料列表",
)
async def list_debate_support_documents(
    debate_id: str,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """获取某场辩论绑定的支撑材料列表"""
    _ensure_teacher_can_modify_debate(db, current_user, debate_id)
    knowledge_base = KnowledgeBase(db)
    documents = knowledge_base.get_documents(debate_id)
    return {
        "code": 200,
        "message": "获取成功",
        "data": [_serialize_support_document(document) for document in documents],
    }


@router.post(
    "/debates/{debate_id}/support-documents",
    summary="上传辩论支撑材料",
)
async def upload_debate_support_document(
    debate_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """上传某场辩论绑定的 PDF 支撑材料"""
    _ensure_teacher_can_modify_debate(db, current_user, debate_id)
    file_type = _resolve_support_file_type(file)
    file_data = await file.read()
    knowledge_base = KnowledgeBase(db)
    try:
        document = await knowledge_base.upload_document(
            file_data=file_data,
            filename=file.filename or "support-document",
            file_type=file_type,
            debate_id=debate_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return {
        "code": 200,
        "message": "上传成功",
        "data": _serialize_support_document(document),
    }


@router.delete(
    "/debates/{debate_id}/support-documents/{document_id}",
    summary="删除辩论支撑材料",
)
async def delete_debate_support_document(
    debate_id: str,
    document_id: str,
    current_user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """删除某场辩论绑定的支撑材料"""
    _ensure_teacher_can_modify_debate(db, current_user, debate_id)
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document or str(document.debate_id) != str(debate_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="支撑材料不存在",
        )
    knowledge_base = KnowledgeBase(db)
    ok = await knowledge_base.delete_document(document_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除支撑材料失败",
        )
    return {
        "code": 200,
        "message": "删除成功",
        "data": None,
    }


# ==================== 配置管理已迁移至管理员端 ====================
# 配置管理功能已移至 /api/admin/config 路由
# 使用 model_config 和 coze_config 表
