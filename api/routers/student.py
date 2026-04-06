"""
学生端API路由
"""
import os
import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from logging_config import get_logger
from database import get_db
from models.user import User
from services.profile_service import ProfileService
from services.assessment_service import AssessmentService
from services.debate_service import DebateService
from middleware.auth_middleware import require_student, PermissionChecker, require_role

from models import Debate,Speech
from config import settings,BASE_DIR


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
            detail=str(e)
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
            detail=str(e)
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
    - **stablecoin_knowledge**: 稳定币知识（0-100）
    - **financial_knowledge**: 金融知识（0-100）
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
            detail=str(e)
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
            detail=str(e)
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
            detail=str(e)
        )


# ==================== 报告相关 ====================

from services.report_service import ReportGenerator
from fastapi.responses import Response
from utils.email_service import EmailService

def _compute_markdown_hash(markdown_text: str) -> str:
    return hashlib.sha256(markdown_text.encode("utf-8")).hexdigest()


def _get_cached_report_markdown(debate: Debate) -> Optional[str]:
    report = debate.report
    if isinstance(report, dict):
        markdown_text = report.get("report_markdown")
        if isinstance(markdown_text, str) and markdown_text.strip():
            return markdown_text
    return None


async def _get_or_generate_report_markdown(
    db: Session,
    debate: Debate,
    content_str: str,
) -> str:
    cached = _get_cached_report_markdown(debate)
    if cached:
        report = debate.report if isinstance(debate.report, dict) else {}
        cached_hash = report.get("report_markdown_hash")
        computed_hash = _compute_markdown_hash(cached)
        if cached_hash != computed_hash:
            debate.report = {**report, "report_markdown": cached, "report_markdown_hash": computed_hash}
            db.commit()
        return cached

    markdown_text = await ReportGenerator.generate_markdown_report_async(
        db=db,
        debate_topic=debate.topic,
        content_str=content_str,
    )
    if not markdown_text:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="报告生成失败",
        )

    existing = debate.report if isinstance(debate.report, dict) else {}
    debate.report = {
        **existing,
        "report_markdown": markdown_text,
        "report_markdown_hash": _compute_markdown_hash(markdown_text),
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
    
    # 生成报告
    report = ReportGenerator.generate_student_report(
        db, debate_id, str(current_user.id)
    )
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在或您未参与该辩论"
        )
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": report.to_dict()
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
    # 检查权限
    checker = PermissionChecker(db)
    if not checker.can_access_debate(current_user, debate_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权导出该辩论报告"
        )

    debate = db.execute(
        select(Debate).where(Debate.id == debate_id)
    ).scalar_one_or_none()
    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该辩论不存在"
        )

    cached_markdown = _get_cached_report_markdown(debate)

    content = ""
    if not cached_markdown:
        speeches = (
            db.execute(
                select(Speech)
                .where(Speech.debate_id == debate_id)
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
    
    markdown_text = await _get_or_generate_report_markdown(db=db, debate=debate, content_str=content)

    report_meta = debate.report if isinstance(debate.report, dict) else {}
    markdown_hash = report_meta.get("report_markdown_hash")
    pdf_path = debate.report_pdf

    if (
        pdf_path
        and os.path.exists(pdf_path)
        and markdown_hash
        and report_meta.get("report_pdf_markdown_hash") == markdown_hash
    ):
        pdf_file = Path(pdf_path)
        pdf_data = pdf_file.read_bytes()
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=debate_report_{debate_id}.pdf"},
        )

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF生成失败"
        )

    target_pdf_path = (
        Path(pdf_path)
        if pdf_path
        else (BASE_DIR / settings.UPLOAD_DIR / "reports" / f"debate_report_{debate_id}.pdf")
    )
    target_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    target_pdf_path.write_bytes(pdf_data)

    updated_report = debate.report if isinstance(debate.report, dict) else {}
    if markdown_hash:
        updated_report = {**updated_report, "report_pdf_markdown_hash": markdown_hash}
        debate.report = updated_report

    debate.report_pdf = target_pdf_path.as_posix()
    db.commit()
    
    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=debate_report_{debate_id}.pdf"
        }
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
    # 检查权限
    checker = PermissionChecker(db)
    if not checker.can_access_debate(current_user, debate_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作该辩论"
        )
    
    # 获取辩论信息
    debate = db.execute(select(Debate).where(Debate.id == debate_id)).scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail="辩论不存在")
    
    # 确定接收者
    # 如果是学生，发送给自己
    # 如果是老师，发给当前调用者（老师自己）
    target_user = current_user

    if not target_user.email:
        raise HTTPException(status_code=400, detail="用户未设置邮箱")

    cached_markdown = _get_cached_report_markdown(debate)
    content = ""
    if not cached_markdown:
        speeches = (
            db.execute(
                select(Speech)
                .where(Speech.debate_id == debate_id)
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

    markdown_text = await _get_or_generate_report_markdown(db=db, debate=debate, content_str=content)
    
    success = await EmailService.send_report_email(
        db=db,
        to_email=target_user.email,
        student_name=target_user.name,
        debate_topic=debate.topic,
        report_summary=markdown_text
    )
    
    if success:
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
        raise HTTPException(status_code=400, detail=str(e))
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
        raise HTTPException(status_code=400, detail=str(e))
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
