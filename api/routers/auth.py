"""
认证API路由
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from database import get_db
from models.user import User
from services.audit_service import AuditService
from services.auth_service import AuthService
from services.avatar_service import AvatarService
from middleware.auth_middleware import verify_token_middleware
from schemas.config import (
    AuditLogEventContract,
    AuthSessionApiResponse,
    AuthSessionContract,
    UploadGuardErrorContract,
    WsTicketContract,
)
from schemas.auth import SelectDefaultAvatarRequest
from utils.security import (
    build_audit_log_event_contract,
    build_upload_guard_error_contract,
    normalize_contract_role,
)
from utils.error_contract import public_exception_detail

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _record_auth_audit(
    *,
    actor_id: str,
    actor_role: str,
    target_type: str,
    target_id: str,
    result: str,
    metadata: Optional[dict] = None,
) -> None:
    AuditService.record_event(
        event_type="auth",
        actor_id=actor_id,
        actor_role=actor_role,
        target_type=target_type,
        target_id=target_id,
        result=result,
        metadata=metadata or {},
    )


def _normalize_requested_actor_role(user_type: str) -> str:
    normalized = normalize_contract_role(user_type)
    return normalized if normalized in {"student", "teacher", "admin"} else "system"


# Pydantic模型
class TeacherRegisterRequest(BaseModel):
    account: str  # 教工号
    email: EmailStr
    phone: str
    password: str
    name: str


class StudentRegisterRequest(BaseModel):
    account: str
    password: str
    name: str
    class_id: Optional[str] = None  # 班级ID（可选）
    email: Optional[EmailStr] = None
    student_id: Optional[str] = None


class LoginRequest(BaseModel):
    account: str
    password: str
    user_type: str  # teacher、student或administrator


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class WsTicketRequest(BaseModel):
    room_id: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    student_id: Optional[str] = None
    class_id: Optional[str] = None  # 新增：班级ID


# API端点
@router.get("/classes/public", summary="获取公开班级列表")
async def get_public_classes(db: Session = Depends(get_db)):
    """
    获取所有班级列表（用于注册时选择）
    返回班级ID、名称、教师姓名等信息
    """
    from models.class_model import Class
    from models.user import User
    
    try:
        student_counts = (
            db.query(
                User.class_id.label("class_id"),
                func.count(User.id).label("student_count"),
            )
            .filter(User.user_type == "student")
            .group_by(User.class_id)
            .subquery()
        )

        classes = (
            db.query(
                Class,
                User.name.label("teacher_name"),
                func.coalesce(student_counts.c.student_count, 0).label("student_count"),
            )
            .join(User, Class.teacher_id == User.id)
            .outerjoin(student_counts, student_counts.c.class_id == Class.id)
            .order_by(Class.created_at.desc())
            .all()
        )
        
        result = []
        for cls, teacher_name, student_count in classes:
            result.append({
                "id": str(cls.id),
                "name": cls.name,
                "code": cls.code,
                "teacher_name": teacher_name or "未知",
                "student_count": int(student_count or 0)
            })
        
        return {
            "code": 200,
            "message": "获取成功",
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取班级列表失败: {str(e)}"
        )
@router.post("/register/teacher", summary="教师注册")
async def register_teacher(
    request: TeacherRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    教师注册
    
    - **account**: 教工号
    - **email**: 邮箱
    - **phone**: 手机号
    - **password**: 密码
    - **name**: 姓名
    """
    try:
        user = AuthService.register_teacher(
            db=db,
            account=request.account,
            email=request.email,
            phone=request.phone,
            password=request.password,
            name=request.name
        )
        return {
            "code": 200,
            "message": "注册成功",
            "data": user
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )


@router.post("/register/student", summary="学生注册")
async def register_student(
    request: StudentRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    学生注册
    
    - **account**: 账号
    - **password**: 密码
    - **name**: 姓名
    - **class_id**: 班级ID（可选）
    - **email**: 邮箱（可选）
    - **student_id**: 学号（可选）
    """
    try:
        user = AuthService.register_student(
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
            "message": "注册成功",
            "data": user
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )


@router.post(
    "/login",
    summary="用户登录",
    response_model=AuthSessionApiResponse,
)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    用户登录
    
    - **account**: 璐﹀彿
    - **password**: 密码
    - **user_type**: 用户类型（teacher、student或administrator）
    """
    try:
        result = AuthService.login(
            db=db,
            account=request.account,
            password=request.password,
            user_type=request.user_type
        )
        _record_auth_audit(
            actor_id=str(result["user"]["id"]),
            actor_role=str(result["user"]["user_type"]),
            target_type="session",
            target_id=str(result["session_id"]),
            result="success",
            metadata={"action": "login"},
        )
        return {
            "code": 200,
            "message": "登录成功",
            "data": result
        }
    except ValueError as e:
        _record_auth_audit(
            actor_id=(request.account or "").strip() or "anonymous",
            actor_role=_normalize_requested_actor_role(request.user_type),
            target_type="session",
            target_id="login",
            result="denied",
            metadata={"action": "login", "reason": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=public_exception_detail(e)
        )


@router.post(
    "/refresh",
    summary="刷新令牌",
    response_model=AuthSessionApiResponse,
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    刷新访问令牌
    
    - **refresh_token**: 刷新令牌
    """
    try:
        result = AuthService.refresh_token(
            db=db,
            refresh_token=request.refresh_token
        )
        _record_auth_audit(
            actor_id=str(result["user"]["id"]),
            actor_role=str(result["user"]["user_type"]),
            target_type="session",
            target_id=str(result["session_id"]),
            result="success",
            metadata={"action": "refresh"},
        )
        return {
            "code": 200,
            "message": "刷新成功",
            "data": result
        }
    except ValueError as e:
        _record_auth_audit(
            actor_id="unknown",
            actor_role="system",
            target_type="session",
            target_id="refresh",
            result="denied",
            metadata={"action": "refresh", "reason": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=public_exception_detail(e)
        )


@router.post("/logout", summary="当前设备登出")
async def logout(
    current_user: User = Depends(verify_token_middleware),
):
    """
    吊销当前访问令牌所属会话。
    """
    session_id = getattr(current_user, "_auth_session_id", None)
    result = AuthService.logout_session(
        session_id,
        user_id=str(current_user.id),
    )
    _record_auth_audit(
        actor_id=str(current_user.id),
        actor_role=str(current_user.user_type),
        target_type="session",
        target_id=str(session_id or current_user.id),
        result="success",
        metadata={"action": "logout", "revoked_session_count": result.get("revoked_session_count", 0)},
    )
    return {
        "code": 200,
        "message": "登出成功",
        "data": result,
    }


@router.post("/logout-all", summary="全设备登出")
async def logout_all(
    current_user: User = Depends(verify_token_middleware),
):
    """
    吊销当前用户的全部服务端会话。
    """
    result = AuthService.logout_all_sessions(str(current_user.id))
    _record_auth_audit(
        actor_id=str(current_user.id),
        actor_role=str(current_user.user_type),
        target_type="user_sessions",
        target_id=str(current_user.id),
        result="success",
        metadata={"action": "logout_all", "revoked_session_count": result.get("revoked_session_count", 0)},
    )
    return {
        "code": 200,
        "message": "已退出全部设备",
        "data": result,
    }


@router.get(
    "/contracts/session/mock",
    summary="获取 AuthSessionContract mock",
    response_model=AuthSessionContract,
)
async def get_auth_session_contract_mock(user_type: str = "teacher"):
    """
    提供给 D 的冻结登录态示例，不依赖真实会话改造。
    """
    return AuthService.build_auth_session_contract_preview(user_type=user_type)


@router.get(
    "/ws-ticket/mock",
    summary="获取 WsTicketContract mock",
    response_model=WsTicketContract,
)
async def get_ws_ticket_contract_mock(room_id: str = "room_demo_001"):
    """
    提供给 D 的 WebSocket ticket 示例，不暴露 access token query。
    """
    return AuthService.build_ws_ticket_contract_preview(room_id=room_id)


@router.get(
    "/ws-ticket",
    summary="获取真实 WebSocket ticket",
    response_model=WsTicketContract,
)
async def issue_ws_ticket(
    room_id: str,
    current_user: User = Depends(verify_token_middleware),
):
    """
    使用当前登录态签发短时单次可用的 WebSocket ticket。
    """
    token_payload = getattr(current_user, "_auth_token_payload", {}) or {}
    ticket_payload = AuthService.issue_ws_ticket(
        user=current_user,
        room_id=room_id,
        session_id=getattr(current_user, "_auth_session_id", None),
        auth_iat=token_payload.get("iat"),
    )
    _record_auth_audit(
        actor_id=str(current_user.id),
        actor_role=str(current_user.user_type),
        target_type="room",
        target_id=str(room_id),
        result="success",
        metadata={
            "action": "issue_ws_ticket",
            "session_id": getattr(current_user, "_auth_session_id", None),
            "ticket": ticket_payload.get("ticket"),
        },
    )
    return ticket_payload


@router.get(
    "/contracts/upload-error/mock",
    summary="获取 UploadGuardErrorContract mock",
    response_model=UploadGuardErrorContract,
)
async def get_upload_guard_error_contract_mock():
    """
    提供统一上传错误结构示例，供前端错误映射先接入。
    """
    return build_upload_guard_error_contract(
        code="mime_invalid",
        message="Only PDF and DOCX uploads are allowed for this object.",
        request_id="req_contract_upload_demo",
    )


@router.get(
    "/contracts/audit-event/mock",
    summary="获取 AuditLogEventContract mock",
    response_model=AuditLogEventContract,
)
async def get_audit_log_event_contract_mock():
    """
    提供统一审计事件结构示例，供后续联调对齐字段。
    """
    return build_audit_log_event_contract(
        event_type="auth",
        actor_id="teacher_demo_id",
        actor_role="teacher",
        target_type="session",
        target_id="session_demo_id",
        result="success",
        metadata={"action": "login"},
        event_id="audit_contract_demo",
    )


@router.post("/change-password", summary="修改密码")
async def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware)
):
    """
    修改密码（需要登录）
    
    - **old_password**: 旧密码
    - **new_password**: 新密码
    """
    try:
        AuthService.change_password(
            db=db,
            user_id=str(current_user.id),
            old_password=request.old_password,
            new_password=request.new_password
        )
        return {
            "code": 200,
            "message": "密码修改成功"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )


@router.get("/profile", summary="获取个人信息")
async def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware)
):
    """
    获取当前用户的个人信息（需要登录）
    """
    from services.profile_service import ProfileService
    
    try:
        profile = ProfileService.get_profile(db=db, user_id=str(current_user.id))
        return {
            "code": 200,
            "message": "获取成功",
            "data": profile
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=public_exception_detail(e)
        )


@router.put("/profile", summary="更新个人信息")
async def update_profile(
    request: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware)
):
    """
    更新个人信息（需要登录）
    
    - **name**: 姓名（可选）
    - **email**: 邮箱（可选）
    - **phone**: 手机号（可选）
    - **student_id**: 学号（可选，仅学生）
    - **class_id**: 班级ID（可选，仅学生）
    """
    from services.profile_service import ProfileService
    
    try:
        result = ProfileService.update_profile(
            db=db,
            user_id=str(current_user.id),
            name=request.name,
            email=request.email,
            phone=request.phone,
            student_id=request.student_id,
            class_id=request.class_id
        )
        return {
            "code": 200,
            "message": "更新成功",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )


@router.get("/avatars/defaults", summary="获取默认头像列表")
async def get_default_avatars():
    return {
        "code": 200,
        "message": "获取成功",
        "data": AvatarService.list_default_avatars(),
    }


@router.post("/profile/avatar/upload", summary="上传自定义头像")
async def upload_profile_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware),
):
    try:
        content = await file.read()
        avatar_payload = AvatarService.apply_custom_avatar(
            db=db,
            user=current_user,
            content=content,
            filename=file.filename,
        )
        return {
            "code": 200,
            "message": "头像上传成功",
            "data": avatar_payload,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e),
        )


@router.put("/profile/avatar/default", summary="切换默认头像")
async def select_default_avatar(
    request: SelectDefaultAvatarRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware),
):
    try:
        avatar_payload = AvatarService.apply_default_avatar(
            db=db,
            user=current_user,
            default_key=request.avatar_default_key,
        )
        return {
            "code": 200,
            "message": "默认头像已更新",
            "data": avatar_payload,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e),
        )


@router.delete("/profile/avatar", summary="清除头像")
async def clear_profile_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware),
):
    avatar_payload = AvatarService.clear_avatar(db=db, user=current_user)
    return {
        "code": 200,
        "message": "头像已清除",
        "data": avatar_payload,
    }



class DeleteAccountRequest(BaseModel):
    password: str


@router.post("/delete-account", summary="注销账户")
async def delete_account(
    request: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware),
):
    """
    注销账户
    
    - **password**: 密码（用于确认）
    
    注意：
    - 学生账户：软删除，保留匿名化的历史数据
    - 教师账户：需要先删除或转移所有班级
    """
    
    try:
        result = AuthService.delete_account(
            db=db,
            user_id=str(current_user.id),
            password=request.password
        )
        return {
            "code": 200,
            "message": result["message"],
            "data": {
                "data_retained": result["data_retained"],
                "note": result["note"]
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )
