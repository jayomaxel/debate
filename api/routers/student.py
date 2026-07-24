"""
学生端API路由
"""
import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Dict, Optional

from logging_config import get_logger
from database import get_db
from models.user import User
from services.profile_service import ProfileService
from services.assessment_service import AssessmentService
from services.audit_service import AuditService
from services.debate_service import DebateService
from services.report_file_storage_service import ReportFileStorageService
from services.report_orchestration_service import ReportOrchestrationService
from services.scoring_service import ScoringService
from middleware.auth_middleware import require_student, PermissionChecker, require_role
from utils.error_contract import public_exception_detail

from models import Debate,Speech


logger = get_logger(__name__)

router = APIRouter(prefix="/api/student", tags=["学生端"])


# Pydantic模型
class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    student_id: Optional[str] = None


class SubmitAssessmentRequest(BaseModel):
    personality_type: Optional[str] = None
    expression_willingness: int
    logical_thinking: int
    stablecoin_knowledge: int
    financial_knowledge: int
    critical_thinking: int


class JoinDebateRequest(BaseModel):
    invitation_code: str


class CreateLobbyRoomRequest(BaseModel):
    room_name: Optional[str] = None
    topic: str
    description: Optional[str] = None
    capacity: int = 4
    visibility: str = "public"
    password: Optional[str] = None
    allow_spectators: bool = False


class JoinLobbyRoomRequest(BaseModel):
    password: Optional[str] = None


class LeaveLobbyRoomRequest(BaseModel):
    permanent: bool = False


class RespondReservationRequest(BaseModel):
    action: str


# API端点
@router.get("/profile", summary="获取个人信息")
async def get_profile(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    获取学生个人信息
    """
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
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    更新学生个人信息
    
    - **name**: 姓名（可选）
    - **email**: 邮箱（可选）
    - **phone**: 手机号（可选）
    - **student_id**: 学号（可选）
    """
    try:
        result = ProfileService.update_profile(
            db=db,
            user_id=str(current_user.id),
            name=request.name,
            email=request.email,
            phone=request.phone,
            student_id=request.student_id
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


@router.post("/assessment", summary="提交能力评估")
async def submit_assessment(
    request: SubmitAssessmentRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    提交能力评估问卷
    
    - **personality_type**: 性格类型（MBTI，可选）
    - **expression_willingness**: 语言表达（0-100）
    - **logical_thinking**: 逻辑思维（0-100）
    - **stablecoin_knowledge**: AI伦理与科技素养（0-100）
    - **financial_knowledge**: AI通识知识水平（0-100）
    - **critical_thinking**: 批判思维（0-100）
    """
    try:
        result = AssessmentService.submit_assessment(
            db=db,
            user_id=str(current_user.id),
            personality_type=request.personality_type,
            expression_willingness=request.expression_willingness,
            logical_thinking=request.logical_thinking,
            stablecoin_knowledge=request.stablecoin_knowledge,
            financial_knowledge=request.financial_knowledge,
            critical_thinking=request.critical_thinking
        )
        return {
            "code": 200,
            "message": "评估完成",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )


@router.get("/assessment", summary="获取能力评估结果")
async def get_assessment(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    获取学生的能力评估结果
    """
    result = AssessmentService.get_assessment(db=db, user_id=str(current_user.id))
    
    if result is None:
        return {
            "code": 200,
            "message": "尚未进行能力评估",
            "data": None
        }
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": result
    }


@router.get("/lobby/rooms", summary="获取匹配大厅房间列表")
async def list_lobby_rooms(
    keyword: Optional[str] = None,
    visibility: Optional[str] = None,
    room_status: Optional[str] = Query(None, alias="status"),
    sort: str = "latest",
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.list_lobby_rooms(
            db=db,
            student_id=str(current_user.id),
            keyword=keyword,
            visibility=visibility,
            status=room_status,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        return {"code": 200, "message": "获取成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=public_exception_detail(e))


@router.post("/lobby/rooms", summary="创建自发组队房间")
async def create_lobby_room(
    request: CreateLobbyRoomRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.create_lobby_room(
            db=db,
            student_id=str(current_user.id),
            room_name=request.room_name,
            topic=request.topic,
            description=request.description,
            capacity=request.capacity,
            visibility=request.visibility,
            password=request.password,
            allow_spectators=request.allow_spectators,
        )
        return {"code": 200, "message": "创建成功", "data": result}
    except ValueError as e:
        detail = str(e)
        http_status = status.HTTP_409_CONFLICT if "已有未结束" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=detail)


@router.get("/lobby/rooms/{room_id}", summary="获取匹配大厅房间详情")
async def get_lobby_room_detail(
    room_id: str,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.get_lobby_room_detail(
            db=db,
            student_id=str(current_user.id),
            room_id=room_id,
        )
        return {"code": 200, "message": "获取成功", "data": result}
    except ValueError as e:
        detail = str(e)
        http_status = status.HTTP_403_FORBIDDEN if "无权" in detail else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=http_status, detail=detail)


@router.post("/lobby/rooms/{room_id}/join", summary="加入匹配大厅房间")
async def join_lobby_room(
    room_id: str,
    request: JoinLobbyRoomRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.join_lobby_room(
            db=db,
            student_id=str(current_user.id),
            room_id=room_id,
            password=request.password,
        )
        return {"code": 200, "message": "加入成功", "data": result}
    except ValueError as e:
        detail = str(e)
        if "不存在" in detail:
            http_status = status.HTTP_404_NOT_FOUND
        elif "已满" in detail or "已开始" in detail or "已结束" in detail:
            http_status = status.HTTP_409_CONFLICT
        elif "密码" in detail:
            http_status = status.HTTP_403_FORBIDDEN
        else:
            http_status = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=detail)


@router.post("/lobby/rooms/{room_id}/leave", summary="离开匹配大厅房间")
async def leave_lobby_room(
    room_id: str,
    request: LeaveLobbyRoomRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.leave_lobby_room(
            db=db,
            student_id=str(current_user.id),
            room_id=room_id,
            permanent=request.permanent,
        )
        return {"code": 200, "message": "操作成功", "data": result}
    except ValueError as e:
        detail = str(e)
        if "不存在" in detail:
            http_status = status.HTTP_404_NOT_FOUND
        elif "无权" in detail:
            http_status = status.HTTP_403_FORBIDDEN
        elif "冲突" in detail or "已开始" in detail or "已结束" in detail:
            http_status = status.HTTP_409_CONFLICT
        else:
            http_status = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=detail)


@router.get("/reservations", summary="获取我的预约辩论赛")
async def list_my_reservations(
    reservation_status: Optional[str] = Query(None, alias="status"),
    include_cancelled: bool = True,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.list_student_reservations(
            db=db,
            student_id=str(current_user.id),
            status=reservation_status,
            include_cancelled=include_cancelled,
            page=page,
            page_size=page_size,
        )
        return {"code": 200, "message": "获取成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=public_exception_detail(e))


@router.post("/reservations/{reservation_id}/respond", summary="接受或拒绝预约邀请")
async def respond_reservation(
    reservation_id: str,
    request: RespondReservationRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.respond_reservation_invitation(
            db=db,
            student_id=str(current_user.id),
            reservation_id=reservation_id,
            action=request.action,
        )
        return {"code": 200, "message": "操作成功", "data": result}
    except ValueError as e:
        detail = str(e)
        http_status = status.HTTP_409_CONFLICT if "取消" in detail or "过期" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=detail)


@router.post("/reservations/{reservation_id}/check-in", summary="预约辩论赛签到")
async def check_in_reservation(
    reservation_id: str,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.check_in_reservation(
            db=db,
            student_id=str(current_user.id),
            reservation_id=reservation_id,
        )
        return {"code": 200, "message": "签到成功", "data": result}
    except ValueError as e:
        detail = str(e)
        http_status = status.HTTP_409_CONFLICT if "签到" in detail or "邀请" in detail or "取消" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=http_status, detail=detail)


@router.get("/reservation-reminders", summary="获取预约提醒")
async def list_reservation_reminders(
    unread_only: bool = False,
    limit: int = 20,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        result = DebateService.list_student_reservation_reminders(
            db=db,
            student_id=str(current_user.id),
            unread_only=unread_only,
            limit=limit,
        )
        return {"code": 200, "message": "获取成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=public_exception_detail(e))


@router.get("/debates", summary="获取可参与的辩论")
async def get_available_debates(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    获取学生可参与的辩论列表
    """
    try:
        debates = DebateService.get_available_debates(
            db=db,
            student_id=str(current_user.id)
        )
        return {
            "code": 200,
            "message": "获取成功",
            "data": debates
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=public_exception_detail(e)
        )


@router.get("/debates/{debate_id}/participants", summary="获取辩论参与者")
async def get_debate_participants(
    debate_id: str,
    current_user: User = Depends(require_role(["student", "teacher"])),
    db: Session = Depends(get_db)
):
    try:
        checker = PermissionChecker(db)
        if not checker.can_access_debate(current_user, debate_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该辩论参与者信息"
            )

        if current_user.user_type == "teacher":
            participants = DebateService.get_debate_participants_for_teacher(
                db=db,
                debate_id=debate_id,
            )
        else:
            participants = DebateService.get_debate_participants_for_student(
                db=db,
                debate_id=debate_id,
                student_id=str(current_user.id)
            )
        return {
            "code": 200,
            "message": "获取成功",
            "data": participants
        }
    except ValueError as e:
        detail = str(e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if detail == "您未参与该辩论" else status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


@router.post("/debates/join", summary="加入辩论")
async def join_debate(
    request: JoinDebateRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    通过邀请码加入辩论
    
    - **invitation_code**: 6位邀请码
    """
    try:
        result = DebateService.join_debate_by_code(
            db=db,
            student_id=str(current_user.id),
            invitation_code=request.invitation_code
        )
        return {
            "code": 200,
            "message": "加入成功",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )


# ==================== 报告相关 ====================

from services.report_service import ReportGenerator
from utils.markdown_to_pdf import MarkdownToPdfConverter
from fastapi.responses import Response
from utils.email_service import EmailService

def _uuid_value(value):
    if value is None or isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return value


def _report_score_revision(debate: Debate) -> int:
    report = debate.report if isinstance(debate.report, dict) else {}
    try:
        return int(report.get("score_revision") or 0)
    except (TypeError, ValueError):
        return 0


def _legacy_pdf_cache_allowed(debate: Debate, report_meta: Dict) -> bool:
    return (
        not report_meta.get("report_markdown_hash")
        and not report_meta.get("report_pdf_markdown_hash")
        and _report_score_revision(debate) == 0
    )


def _compute_markdown_hash(markdown_text: str, score_revision: int = 0) -> str:
    payload = f"score_revision:{int(score_revision or 0)}\n{markdown_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_cached_report_markdown(debate: Debate) -> Optional[str]:
    report = debate.report
    if isinstance(report, dict):
        markdown_text = report.get("report_markdown")
        markdown_hash = report.get("report_markdown_hash")
        expected_hash = (
            _compute_markdown_hash(markdown_text, _report_score_revision(debate))
            if isinstance(markdown_text, str)
            else None
        )
        if (
            isinstance(markdown_text, str)
            and markdown_text.strip()
            and markdown_hash == expected_hash
        ):
            return markdown_text
    return None


def _report_pdf_download_headers(debate: Debate) -> Dict[str, str]:
    filename = ReportFileStorageService.build_pdf_download_name()
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }


def _get_report_pdf_cache_response(
    db: Session,
    debate: Debate,
    debate_id: str,
) -> Optional[Response]:
    report_meta = debate.report if isinstance(debate.report, dict) else {}
    markdown_hash = report_meta.get("report_markdown_hash")
    cache_is_valid = (
        report_meta.get("report_pdf_renderer_version")
        == MarkdownToPdfConverter.RENDERER_VERSION
        and (
            (
                markdown_hash
                and report_meta.get("report_pdf_markdown_hash") == markdown_hash
            )
            or _legacy_pdf_cache_allowed(debate, report_meta)
        )
    )
    if not cache_is_valid:
        return None

    _, pdf_file, migrated = ReportFileStorageService.migrate_legacy_pdf_for_debate(
        debate, debate_id
    )
    if pdf_file and pdf_file.exists():
        if migrated:
            db.commit()
        return Response(
            content=pdf_file.read_bytes(),
            media_type="application/pdf",
            headers=_report_pdf_download_headers(debate),
        )

    return None


async def _ensure_report_ready(db: Session, debate_id: str) -> Dict[str, object]:
    return await ScoringService.ensure_debate_scored(db=db, debate_id=debate_id)


def _record_report_generation_audit(
    *,
    actor_id: str,
    actor_role: str,
    debate_id: str,
    action: str,
    result: str = "success",
    metadata: Optional[Dict[str, object]] = None,
) -> None:
    AuditService.record_event(
        event_type="report_regeneration",
        actor_id=actor_id,
        actor_role=actor_role,
        target_type="report",
        target_id=str(debate_id),
        result=result,
        metadata={"action": action, **dict(metadata or {})},
    )


async def _get_or_generate_report_markdown(
    db: Session,
    debate: Debate,
    content_str: str,
    viewer_id: str,
) -> str:
    cached = _get_cached_report_markdown(debate)
    if cached:
        report = debate.report if isinstance(debate.report, dict) else {}
        cached_hash = report.get("report_markdown_hash")
        computed_hash = _compute_markdown_hash(cached, _report_score_revision(debate))
        if cached_hash != computed_hash:
            debate.report = {**report, "report_markdown": cached, "report_markdown_hash": computed_hash}
            db.commit()
        return cached

    # PDF/email export must not make a second long-running LLM request. The
    # semantic judge result and per-speech scores are already persisted; build
    # a deterministic report from that reviewed data so downloads are fast and
    # remain available when the model provider is temporarily unavailable.
    structured_report = ReportGenerator.generate_student_report(
        db=db,
        debate_id=str(debate.id),
        student_id=viewer_id,
    )
    if not structured_report:
        existing = debate.report if isinstance(debate.report, dict) else {}
        debate.report = {
            **existing,
            "report_markdown_status": "failed",
            "report_markdown_error": "structured_report_unavailable",
            "report_markdown_failed_at": datetime.utcnow().isoformat(),
        }
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="报告生成失败",
        )

    markdown_text = ReportGenerator.build_structured_markdown(structured_report)
    existing = debate.report if isinstance(debate.report, dict) else {}
    debate.report = {
        **existing,
        "report_markdown": markdown_text,
        "report_markdown_hash": _compute_markdown_hash(markdown_text, _report_score_revision(debate)),
        "report_markdown_status": "ready",
        "report_markdown_error": None,
        "report_markdown_generated_at": datetime.utcnow().isoformat(),
    }
    db.commit()
    return markdown_text


@router.get("/reports/{debate_id}")
async def get_student_report(
    debate_id: str,
    current_user: User = Depends(require_role(["student", "teacher"])),
    db: Session = Depends(get_db)
):
    """
    获取学生辩论报告
    """
    # 检查权限
    checker = PermissionChecker(db)
    if not checker.can_access_debate(current_user, debate_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该辩论报告"
        )

    await _ensure_report_ready(db, debate_id)
    
    # 生成报告
    report = ReportGenerator.generate_student_report(
        db, debate_id, str(current_user.id)
    )
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在或您未参与该辩论"
        )
    _record_report_generation_audit(
        actor_id=str(current_user.id),
        actor_role=str(current_user.user_type),
        debate_id=debate_id,
        action="get_student_report",
        metadata={"generated_report": True},
    )
    
    debate_uuid = _uuid_value(debate_id)
    debate = db.query(Debate).filter(Debate.id == debate_uuid).first()
    report_payload = ReportOrchestrationService.attach_report_meta(
        db=db,
        debate=debate,
        report_payload=report.to_dict(),
        teacher_view=current_user.user_type == "teacher",
    ) if debate else report.to_dict()

    return {
        "code": 200,
        "message": "获取成功",
        "data": report_payload
    }


@router.get("/reports/{debate_id}/export/pdf")
async def export_report_pdf(
    debate_id: str,
    current_user: User = Depends(require_role(["student", "teacher"])),
    db: Session = Depends(get_db)
):
    """
    导出报告为PDF
    """
    actor_id = str(current_user.id)
    actor_role = str(current_user.user_type)
    # 检查权限
    checker = PermissionChecker(db)
    if not checker.can_access_debate(current_user, debate_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权导出该辩论报告"
        )

    debate_uuid = _uuid_value(debate_id)
    debate = db.execute(
        select(Debate).where(Debate.id == debate_uuid)
    ).scalar_one_or_none()
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该辩论不存在"
        )

    cached_pdf_response = _get_report_pdf_cache_response(db, debate, debate_id)
    if cached_pdf_response is not None:
        return cached_pdf_response

    await _ensure_report_ready(db, debate_id)
    db.refresh(debate)

    report_meta = debate.report if isinstance(debate.report, dict) else {}
    markdown_hash = report_meta.get("report_markdown_hash")
    _, cached_path, migrated = ReportFileStorageService.migrate_legacy_pdf_for_debate(
        debate, debate_id
    )
    if (
        cached_path
        and cached_path.exists()
        and (
            report_meta.get("report_pdf_renderer_version")
            == MarkdownToPdfConverter.RENDERER_VERSION
            and (
                (
                    markdown_hash
                    and report_meta.get("report_pdf_markdown_hash") == markdown_hash
                )
                or _legacy_pdf_cache_allowed(debate, report_meta)
            )
        )
    ):
        if migrated:
            db.commit()
        return Response(
            content=cached_path.read_bytes(),
            media_type="application/pdf",
            headers=_report_pdf_download_headers(debate),
        )

    cached_markdown = _get_cached_report_markdown(debate)
    markdown_was_cached = bool(cached_markdown)

    content = ""
    if not cached_markdown:
        speeches = (
            db.execute(
                select(Speech)
                .where(Speech.debate_id == debate_uuid)
                .where(Speech.is_valid_for_scoring.is_(True))
                .order_by(Speech.timestamp)
            )
            .scalars()
            .all()
        )
        if not speeches:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="该辩论没有发言"
            )
        for s in speeches:
            sepeaker_type = "【正方】" if s.speaker_type == 'human' else "[反方]"
            content += f"{sepeaker_type}【角色】{s.speaker_role}，发言内容：{s.content}"
            content += "\n"
    
    markdown_text = await _get_or_generate_report_markdown(
        db=db,
        debate=debate,
        content_str=content,
        viewer_id=actor_id,
    )

    report_meta = debate.report if isinstance(debate.report, dict) else {}
    markdown_hash = report_meta.get("report_markdown_hash")

    cached_pdf_response = _get_report_pdf_cache_response(db, debate, debate_id)
    if cached_pdf_response is not None:
        return cached_pdf_response

    start_time = debate.start_time.isoformat() if debate.start_time else None
    end_time = debate.end_time.isoformat() if debate.end_time else None

    pdf_data = await ReportGenerator.render_markdown_to_pdf_async(
        markdown_text=markdown_text,
        debate_topic=debate.topic,
        start_time=start_time,
        end_time=end_time,
        duration=debate.duration,
    )
    if not pdf_data:
        existing = debate.report if isinstance(debate.report, dict) else {}
        debate.report = {
            **existing,
            "report_pdf_status": "failed",
            "report_pdf_error": "empty_result",
            "report_pdf_failed_at": datetime.utcnow().isoformat(),
        }
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF生成失败"
        )

    pdf_storage_meta, target_pdf_path = ReportFileStorageService.persist_pdf_bytes_for_debate(
        debate,
        bytes(pdf_data),
    )

    updated_report = debate.report if isinstance(debate.report, dict) else {}
    if markdown_hash:
        updated_report = {**updated_report, "report_pdf_markdown_hash": markdown_hash}
    updated_report = {
        **updated_report,
        "report_pdf_status": "ready",
        "report_pdf_renderer_version": MarkdownToPdfConverter.RENDERER_VERSION,
        "report_pdf_error": None,
        "report_pdf_generated_at": datetime.utcnow().isoformat(),
    }
    if updated_report:
        debate.report = updated_report

    db.commit()
    _record_report_generation_audit(
        actor_id=actor_id,
        actor_role=actor_role,
        debate_id=debate_id,
        action="export_report_pdf",
        metadata={
            "generated_pdf": True,
            "generated_markdown": not markdown_was_cached,
            "pdf_file": target_pdf_path.name,
            "pdf_storage_backend": pdf_storage_meta.get("backend"),
            "pdf_storage_key": pdf_storage_meta.get("storage_key"),
        },
    )
    
    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers=_report_pdf_download_headers(debate),
    )


@router.get("/reports/{debate_id}/export/excel")
async def export_report_excel(
    debate_id: str,
    current_user: User = Depends(require_role(["student", "teacher"])),
    db: Session = Depends(get_db)
):
    """
    导出报告为Excel
    """
    # 检查权限
    checker = PermissionChecker(db)
    if not checker.can_access_debate(current_user, debate_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权导出该辩论报告"
        )

    await _ensure_report_ready(db, debate_id)
    
    # 生成报告
    report = ReportGenerator.generate_student_report(
        db, debate_id, str(current_user.id)
    )
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )
    
    # 导出Excel
    excel_data = ReportGenerator.export_to_excel(report)
    
    if not excel_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Excel生成失败"
        )
    _record_report_generation_audit(
        actor_id=str(current_user.id),
        actor_role=str(current_user.user_type),
        debate_id=debate_id,
        action="export_report_excel",
        metadata={"generated_report": True, "export_format": "excel"},
    )
    
    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=debate_report_{debate_id}.xlsx"
        }
    )


@router.post("/reports/{debate_id}/send-email", summary="发送报告邮件")
async def send_report_email(
    debate_id: str,
    current_user: User = Depends(require_role(["student", "teacher"])),
    db: Session = Depends(get_db)
):
    """
    手动发送辩论报告邮件
    """
    actor_id = str(current_user.id)
    actor_role = str(current_user.user_type)
    # 检查权限
    checker = PermissionChecker(db)
    if not checker.can_access_debate(current_user, debate_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作该辩论"
        )
    
    # 获取辩论信息
    debate_uuid = _uuid_value(debate_id)
    debate = db.execute(select(Debate).where(Debate.id == debate_uuid)).scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail="辩论不存在")

    await _ensure_report_ready(db, debate_id)
    db.refresh(debate)
    
    # 确定接收者
    # 如果是学生，发送给自己
    # 如果是老师，发给当前调用者（老师自己）
    target_user = current_user

    if not target_user.email:
        raise HTTPException(status_code=400, detail="用户未设置邮箱")

    cached_markdown = _get_cached_report_markdown(debate)
    markdown_was_cached = bool(cached_markdown)
    content = ""
    if not cached_markdown:
        speeches = (
            db.execute(
                select(Speech)
                .where(Speech.debate_id == debate_uuid)
                .where(Speech.is_valid_for_scoring.is_(True))
                .order_by(Speech.timestamp)
            )
            .scalars()
            .all()
        )
        if not speeches:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="该辩论没有发言"
            )
        for s in speeches:
            sepeaker_type = "【正方】" if s.speaker_type == 'human' else "[反方]"
            content += f"{sepeaker_type}【角色】{s.speaker_role}，发言内容：{s.content}"
            content += "\n"

    markdown_text = await _get_or_generate_report_markdown(
        db=db,
        debate=debate,
        content_str=content,
        viewer_id=actor_id,
    )
    
    success = await EmailService.send_report_email(
        db=db,
        to_email=target_user.email,
        student_name=target_user.name,
        debate_topic=debate.topic,
        report_summary=markdown_text
    )
    
    if success:
        _record_report_generation_audit(
            actor_id=actor_id,
            actor_role=actor_role,
            debate_id=debate_id,
            action="send_report_email",
            metadata={
                "generated_markdown": not markdown_was_cached,
                "recipient_user_id": str(target_user.id),
            },
        )
        return {"code": 200, "message": "邮件发送成功", "data": None}
    else:
        raise HTTPException(status_code=500, detail="邮件发送失败")


# ==================== 历史记录 ====================

from services.history_service import HistoryService
from datetime import datetime as dt


@router.get("/history")
async def get_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    获取学生辩论历史记录
    
    Args:
        limit: 返回记录数量限制（默认20）
        offset: 偏移量，用于分页（默认0）
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        辩论历史记录列表
    """
    try:
        history_service = HistoryService(db)
        
        history = history_service.get_debate_history(
            student_id=str(current_user.id),
            limit=limit,
            offset=offset
        )
        
        return {
            "code": 200,
            "message": "获取成功",
            "data": history
        }
        
    except Exception as e:
        logger.error(f"Failed to get history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取历史记录失败")


@router.get("/history/filter")
async def filter_history(
    status: Optional[str] = None,
    role: Optional[str] = None,
    stance: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    筛选学生辩论历史记录
    
    Args:
        status: 辩论状态筛选（可选：draft/published/in_progress/completed）
        role: 角色筛选（可选：一辩/二辩/三辩/四辩）
        stance: 立场筛选（可选：affirmative/negative）
        start_date: 开始日期筛选（ISO格式，可选）
        end_date: 结束日期筛选（ISO格式，可选）
        limit: 返回记录数量限制（默认20）
        offset: 偏移量，用于分页（默认0）
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        筛选后的辩论历史记录
    """
    try:
        history_service = HistoryService(db)
        
        # 解析日期
        start_dt = dt.fromisoformat(start_date) if start_date else None
        end_dt = dt.fromisoformat(end_date) if end_date else None
        
        history = history_service.filter_history(
            student_id=str(current_user.id),
            status=status,
            role=role,
            stance=stance,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit,
            offset=offset
        )
        
        return history
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"日期格式错误: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to filter history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="筛选历史记录失败")


@router.get("/history/{debate_id}")
async def get_debate_detail(
    debate_id: str,
    current_user: User = Depends(require_role(["student", "teacher"])),
    db: Session = Depends(get_db)
):
    """
    获取辩论详细信息
    
    Args:
        debate_id: 辩论ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        辩论详细信息
    """
    try:
        history_service = HistoryService(db)

        checker = PermissionChecker(db)
        if not checker.can_access_debate(current_user, debate_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该辩论详情"
            )
        
        details = history_service.get_debate_details(
            debate_id=debate_id,
            student_id=str(current_user.id)
        )
        
        if not details:
            raise HTTPException(
                status_code=404,
                detail="辩论不存在或您未参与该辩论"
            )
        
        return {
            "code": 200,
            "message": "获取成功",
            "data": details
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get debate details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取辩论详情失败")


# ==================== 学生数据分析 ====================

from services.analytics_service import AnalyticsService


@router.get("/analytics")
async def get_student_analytics(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    获取学生个人数据分析
    
    Args:
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        学生数据分析
    """
    try:
        analytics = AnalyticsService(db)
        
        stats = analytics.get_student_statistics(str(current_user.id))
        
        return {
            "code": 200,
            "message": "获取成功",
            "data": stats
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=public_exception_detail(e))
    except Exception as e:
        logger.error(f"Failed to get student analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取数据分析失败")


@router.get("/analytics/growth")
async def get_growth_trend(
    limit: int = 10,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    获取学生成长趋势
    
    Args:
        limit: 返回最近N场辩论的数据（默认10）
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        成长趋势数据
    """
    try:
        analytics = AnalyticsService(db)
        
        trend = analytics.get_growth_trend(str(current_user.id), limit)
        
        return {
            "code": 200,
            "message": "获取成功",
            "data": trend
        }
        
    except Exception as e:
        logger.error(f"Failed to get growth trend: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取成长趋势失败")


# ==================== 对比分析 ====================

from services.comparison_service import ComparisonService


@router.get("/comparison/class")
async def get_class_comparison(
    metric: str = "overall",
    top: int = 10,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    try:
        comparison_service = ComparisonService(db)
        data = comparison_service.get_class_comparison(str(current_user.id), metric=metric, top=top)
        return {
            "code": 200,
            "message": "获取成功",
            "data": data
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=public_exception_detail(e))
    except Exception as e:
        logger.error(f"Failed to get class comparison: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取对比数据失败")


# ==================== 成就系统 ====================

from services.achievement_service import AchievementService


@router.get("/achievements")
async def get_achievements(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    获取学生成就列表
    
    Args:
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        成就列表（包含已解锁和未解锁）
    """
    try:
        achievement_service = AchievementService(db)
        
        achievements = achievement_service.get_achievements(str(current_user.id))
        
        return achievements
        
    except Exception as e:
        logger.error(f"Failed to get achievements: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取成就列表失败")


@router.get("/achievements/v2")
async def get_achievements_v2(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    try:
        achievement_service = AchievementService(db)

        achievements = achievement_service.get_achievements_v2(str(current_user.id))

        return {
            "code": 200,
            "message": "获取成功",
            "data": achievements
        }
    except Exception as e:
        logger.error(f"Failed to get achievements v2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取成就列表失败")


@router.post("/achievements/check")
async def check_achievements(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    检查并解锁新成就
    
    Args:
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        新解锁的成就列表
    """
    try:
        achievement_service = AchievementService(db)
        
        newly_unlocked = achievement_service.check_achievements(str(current_user.id))
        
        return {
            "newly_unlocked": newly_unlocked,
            "count": len(newly_unlocked)
        }
        
    except Exception as e:
        logger.error(f"Failed to check achievements: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="检查成就失败")


@router.post("/achievements/check/v2")
async def check_achievements_v2(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    try:
        achievement_service = AchievementService(db)

        newly_unlocked_types = achievement_service.check_achievements(str(current_user.id))
        newly_unlocked = achievement_service.get_newly_unlocked_items_v2(str(current_user.id), newly_unlocked_types)

        return {
            "code": 200,
            "message": "检查成功",
            "data": {
                "newly_unlocked": newly_unlocked,
                "count": len(newly_unlocked)
            }
        }
    except Exception as e:
        logger.error(f"Failed to check achievements v2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="检查成就失败")
