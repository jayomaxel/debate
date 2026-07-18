"""
管理员端API路由
提供系统级管理功能，包括班级管理、配置管理、用户管理等
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid

from database import get_db
from models.class_model import Class
from models.user import User
from services.audit_service import AuditService
from services.avatar_service import AvatarService
from services.class_service import ClassService
from services.config_service import ConfigService
from services.auth_service import AuthService
from middleware.auth_middleware import require_role
from logging_config import get_logger
from schemas.config import (
    AuditLogEventContract,
    ModelConfigResponse,
    ModelConfigUpdate,
    CozeConfigResponse,
    CozeConfigUpdate,
    AsrConfigResponse,
    AsrConfigUpdate,
    TtsConfigResponse,
    TtsConfigUpdate,
    VectorConfigResponse,
    VectorConfigUpdate,
    EmailConfigResponse,
    EmailConfigUpdate,
    MaskedConfigResponse,
)
from schemas.auth import PasswordChangeRequest
from utils.email_service import EmailService
from utils.error_contract import public_exception_detail

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["管理员端"])


# ==================== Pydantic模型 ====================

class ClassCreateRequest(BaseModel):
    """创建班级请求"""
    name: str
    teacher_id: str


class ClassUpdateRequest(BaseModel):
    """更新班级请求"""
    name: Optional[str] = None
    teacher_id: Optional[str] = None


class ClassResponse(BaseModel):
    """班级响应"""
    id: str
    name: str
    code: str
    teacher_id: str
    teacher_name: str
    student_count: int
    created_at: str


# ==================== 班级管理端点 ====================

@router.get(
    "/classes",
    summary="获取所有班级",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def get_all_classes(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    获取系统中所有班级的列表（管理员专用）
    
    返回所有教师创建的班级，包含：
    - 班级基本信息
    - 所属教师名称
    - 学生数量
    - 创建时间
    """
    try:
        classes = ClassService.get_all_classes(db=db)
        return {
            "code": 200,
            "message": "获取成功",
            "data": classes
        }
    except Exception as e:
        logger.error(f"Failed to get all classes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取班级列表失败"
        )


@router.post(
    "/classes",
    summary="创建班级",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def create_class(
    request: ClassCreateRequest,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    为指定教师创建班级（管理员专用）
    
    参数:
    - name: 班级名称
    - teacher_id: 教师ID
    
    返回创建的班级信息
    """
    try:
        result = ClassService.create_class_for_teacher(
            db=db,
            teacher_id=request.teacher_id,
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
            detail=public_exception_detail(e)
        )
    except Exception as e:
        logger.error(f"Failed to create class: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建班级失败"
        )


@router.put(
    "/classes/{class_id}",
    summary="更新班级",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def update_class(
    class_id: str,
    request: ClassUpdateRequest,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    更新任意班级信息（管理员专用）
    
    参数:
    - class_id: 班级ID
    - name: 新的班级名称（可选）
    - teacher_id: 新的教师ID（可选）
    
    返回更新后的班级信息
    """
    try:
        result = ClassService.update_any_class(
            db=db,
            class_id=class_id,
            name=request.name,
            teacher_id=request.teacher_id
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
    except Exception as e:
        logger.error(f"Failed to update class {class_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新班级失败"
        )


@router.delete(
    "/classes/{class_id}",
    summary="删除班级",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def delete_class(
    class_id: str,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    删除任意班级（管理员专用）
    
    参数:
    - class_id: 班级ID
    
    删除班级时会自动处理：
    - 取消所有学生的班级注册
    - 删除班级记录
    
    返回删除成功的消息
    """
    try:
        ClassService.delete_any_class(db=db, class_id=class_id)
        return {
            "code": 200,
            "message": "班级删除成功",
            "data": None
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete class {class_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除班级失败"
        )


# ==================== 配置管理端点 ====================

@router.get(
    "/config/contracts/masked/mock",
    summary="获取 MaskedConfigResponse mock",
    response_model=dict[str, MaskedConfigResponse],
)
async def get_masked_config_contract_mock():
    """
    提供给 D 的配置脱敏合同示例，后续真实接口改造时保持同一结构。
    """
    return ConfigService.build_masked_config_contract_examples()


def _build_secret_contract(
    secret: Optional[str],
    *,
    updated_at,
    updated_by: str,
) -> dict:
    return ConfigService.build_masked_config_contract_preview(
        secret,
        updated_at=updated_at,
        updated_by=updated_by,
    )


def _record_config_audit(
    *,
    current_user: User,
    target_type: str,
    target_id: str,
    metadata: Optional[dict] = None,
) -> None:
    AuditService.record_event(
        event_type="config",
        actor_id=str(current_user.id),
        actor_role=str(current_user.user_type),
        target_type=target_type,
        target_id=target_id,
        result="success",
        metadata=metadata or {},
    )


def _record_admin_action_audit(
    *,
    current_user: User,
    target_type: str,
    target_id: str,
    result: str,
    metadata: Optional[dict] = None,
) -> None:
    AuditService.record_event(
        event_type="admin_action",
        actor_id=str(current_user.id),
        actor_role=str(current_user.user_type),
        target_type=target_type,
        target_id=target_id,
        result=result,
        metadata=metadata or {},
    )


def _build_model_config_response(config, *, updated_by: str) -> ModelConfigResponse:
    secret_contract = _build_secret_contract(
        config.api_key,
        updated_at=config.updated_at,
        updated_by=updated_by,
    )
    return ModelConfigResponse(
        id=str(config.id),
        model_name=config.model_name,
        api_endpoint=config.api_endpoint,
        api_key=secret_contract["masked"],
        secret=secret_contract,
        api_key_configured=secret_contract["configured"],
        api_key_masked=secret_contract["masked"] or None,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        parameters=config.parameters,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _build_asr_config_response(config, *, updated_by: str) -> AsrConfigResponse:
    secret_contract = _build_secret_contract(
        config.api_key,
        updated_at=config.updated_at,
        updated_by=updated_by,
    )
    return AsrConfigResponse(
        id=str(config.id),
        model_name=config.model_name,
        api_endpoint=config.api_endpoint,
        api_key=secret_contract["masked"],
        secret=secret_contract,
        api_key_configured=secret_contract["configured"],
        api_key_masked=secret_contract["masked"] or None,
        parameters=config.parameters,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _build_tts_config_response(config, *, updated_by: str) -> TtsConfigResponse:
    secret_contract = _build_secret_contract(
        config.api_key,
        updated_at=config.updated_at,
        updated_by=updated_by,
    )
    return TtsConfigResponse(
        id=str(config.id),
        model_name=config.model_name,
        api_endpoint=config.api_endpoint,
        api_key=secret_contract["masked"],
        secret=secret_contract,
        api_key_configured=secret_contract["configured"],
        api_key_masked=secret_contract["masked"] or None,
        parameters=config.parameters,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _build_coze_config_response(config, *, updated_by: str) -> CozeConfigResponse:
    secret_contract = _build_secret_contract(
        config.api_token,
        updated_at=config.updated_at,
        updated_by=updated_by,
    )
    return CozeConfigResponse(
        id=str(config.id),
        debater_1_bot_id=config.debater_1_bot_id,
        debater_2_bot_id=config.debater_2_bot_id,
        debater_3_bot_id=config.debater_3_bot_id,
        debater_4_bot_id=config.debater_4_bot_id,
        judge_bot_id=config.judge_bot_id,
        mentor_bot_id=config.mentor_bot_id,
        api_token=secret_contract["masked"],
        secret=secret_contract,
        api_token_configured=secret_contract["configured"],
        api_token_masked=secret_contract["masked"] or None,
        parameters=config.parameters,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _build_vector_config_response(config, *, updated_by: str) -> VectorConfigResponse:
    secret_contract = _build_secret_contract(
        config.api_key,
        updated_at=config.updated_at,
        updated_by=updated_by,
    )
    return VectorConfigResponse(
        id=str(config.id),
        model_name=config.model_name,
        api_endpoint=config.api_endpoint,
        api_key=secret_contract["masked"],
        secret=secret_contract,
        api_key_configured=secret_contract["configured"],
        api_key_masked=secret_contract["masked"] or None,
        embedding_dimension=config.embedding_dimension,
        parameters=config.parameters,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _build_email_config_response(config, *, updated_by: str) -> EmailConfigResponse:
    secret_contract = _build_secret_contract(
        config.smtp_password,
        updated_at=config.updated_at,
        updated_by=updated_by,
    )
    return EmailConfigResponse(
        id=str(config.id),
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_user=config.smtp_user,
        smtp_password_configured=secret_contract["configured"],
        smtp_password_masked=secret_contract["masked"] or None,
        secret=secret_contract,
        from_email=config.from_email,
        auto_send_enabled=config.auto_send_enabled,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get(
    "/config/models",
    summary="获取模型配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def get_model_config(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    获取当前AI模型配置（管理员专用）
    
    返回模型配置信息，包括：
    - 模型名称
    - API端点
    - API密钥
    - 温度参数
    - 最大令牌数
    - 其他参数
    """
    try:
        config_service = ConfigService(db)
        config = await config_service.get_model_config()

        response_data = _build_model_config_response(config, updated_by="system")
        return {
            "code": 200,
            "message": "获取成功",
            "data": response_data
        }
    except Exception as e:
        logger.error(f"Failed to get model config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取模型配置失败"
        )


@router.put(
    "/config/models",
    summary="更新模型配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
@router.post(
    "/config/models",
    summary="更新模型配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def update_model_config(
    request: ModelConfigUpdate,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    更新AI模型配置（管理员专用）
    
    参数:
    - model_name: 模型名称（可选）
    - api_endpoint: API端点（可选）
    - api_key: API密钥（可选）
    - temperature: 温度参数（可选，范围0.0-2.0）
    - max_tokens: 最大令牌数（可选）
    - parameters: 其他参数（可选）
    
    返回更新后的模型配置
    """
    try:
        config_service = ConfigService(db)
        config = await config_service.update_model_config(
            model_name=request.model_name,
            api_endpoint=request.api_endpoint,
            api_key=request.api_key,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            parameters=request.parameters
        )

        response_data = _build_model_config_response(
            config,
            updated_by=current_user.account,
        )
        _record_config_audit(
            current_user=current_user,
            target_type="model_config",
            target_id=str(config.id),
            metadata={"action": "update_model_config"},
        )
        return {
            "code": 200,
            "message": "更新成功",
            "data": response_data
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )
    except Exception as e:
        logger.error(f"Failed to update model config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新模型配置失败"
        )


@router.get(
    "/config/asr",
    summary="获取ASR配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def get_asr_config(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    try:
        config_service = ConfigService(db)
        config = await config_service.get_asr_config()

        response_data = _build_asr_config_response(config, updated_by="system")
        return {"code": 200, "message": "获取成功", "data": response_data}
    except Exception as e:
        logger.error(f"Failed to get ASR config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取ASR配置失败"
        )


@router.put(
    "/config/asr",
    summary="更新ASR配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
@router.post(
    "/config/asr",
    summary="更新ASR配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def update_asr_config(
    request: AsrConfigUpdate,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    try:
        config_service = ConfigService(db)
        config = await config_service.update_asr_config(
            model_name=request.model_name,
            api_endpoint=request.api_endpoint,
            api_key=request.api_key,
            parameters=request.parameters,
        )

        response_data = _build_asr_config_response(
            config,
            updated_by=current_user.account,
        )
        _record_config_audit(
            current_user=current_user,
            target_type="asr_config",
            target_id=str(config.id),
            metadata={"action": "update_asr_config"},
        )
        return {"code": 200, "message": "更新成功", "data": response_data}
    except Exception as e:
        logger.error(f"Failed to update ASR config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新ASR配置失败"
        )


@router.get(
    "/config/tts",
    summary="获取TTS配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def get_tts_config(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    try:
        config_service = ConfigService(db)
        config = await config_service.get_tts_config()

        response_data = _build_tts_config_response(config, updated_by="system")
        return {"code": 200, "message": "获取成功", "data": response_data}
    except Exception as e:
        logger.error(f"Failed to get TTS config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取TTS配置失败"
        )


@router.put(
    "/config/tts",
    summary="更新TTS配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
@router.post(
    "/config/tts",
    summary="更新TTS配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def update_tts_config(
    request: TtsConfigUpdate,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    try:
        config_service = ConfigService(db)
        config = await config_service.update_tts_config(
            model_name=request.model_name,
            api_endpoint=request.api_endpoint,
            api_key=request.api_key,
            parameters=request.parameters,
        )

        response_data = _build_tts_config_response(
            config,
            updated_by=current_user.account,
        )
        _record_config_audit(
            current_user=current_user,
            target_type="tts_config",
            target_id=str(config.id),
            metadata={"action": "update_tts_config"},
        )
        return {"code": 200, "message": "更新成功", "data": response_data}
    except Exception as e:
        logger.error(f"Failed to update TTS config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新TTS配置失败"
        )


@router.get(
    "/config/coze",
    summary="获取Coze配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def get_coze_config(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    获取当前Coze代理配置（管理员专用）
    
    返回Coze配置信息，包括：
    - 代理ID
    - API令牌
    - 其他参数
    """
    try:
        config_service = ConfigService(db)
        config = await config_service.get_coze_config()

        response_data = _build_coze_config_response(config, updated_by="system")
        return {
            "code": 200,
            "message": "获取成功",
            "data": response_data
        }
    except Exception as e:
        logger.error(f"Failed to get Coze config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取Coze配置失败"
        )


@router.put(
    "/config/coze",
    summary="更新Coze配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
@router.post(
    "/config/coze",
    summary="更新Coze配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def update_coze_config(
    request: CozeConfigUpdate,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    更新Coze代理配置（管理员专用）
    
    参数:
    - agent_id: 代理ID（可选）
    - api_token: API令牌（可选）
    - parameters: 其他参数（可选）
    
    返回更新后的Coze配置
    """
    try:
        config_service = ConfigService(db)
        config = await config_service.update_coze_config(
            debater_1_bot_id=request.debater_1_bot_id,
            debater_2_bot_id=request.debater_2_bot_id,
            debater_3_bot_id=request.debater_3_bot_id,
            debater_4_bot_id=request.debater_4_bot_id,
            judge_bot_id=request.judge_bot_id,
            mentor_bot_id=request.mentor_bot_id,
            api_token=request.api_token,
            parameters=request.parameters
        )

        response_data = _build_coze_config_response(
            config,
            updated_by=current_user.account,
        )
        _record_config_audit(
            current_user=current_user,
            target_type="coze_config",
            target_id=str(config.id),
            metadata={"action": "update_coze_config"},
        )
        return {
            "code": 200,
            "message": "更新成功",
            "data": response_data
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )
    except Exception as e:
        logger.error(f"Failed to update Coze config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新Coze配置失败"
        )


@router.get(
    "/config/vector",
    summary="获取向量配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def get_vector_config(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    获取当前向量模型配置（管理员专用）
    
    返回向量模型配置信息，包括：
    - 模型名称
    - API端点
    - API密钥
    - 向量维度
    - 其他参数
    """
    try:
        config_service = ConfigService(db)
        config = await config_service.get_vector_config()

        response_data = _build_vector_config_response(config, updated_by="system")
        return {
            "code": 200,
            "message": "获取成功",
            "data": response_data
        }
    except Exception as e:
        logger.error(f"Failed to get vector config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取向量配置失败"
        )


@router.put(
    "/config/vector",
    summary="更新向量配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
@router.post(
    "/config/vector",
    summary="更新向量配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def update_vector_config(
    request: VectorConfigUpdate,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    更新向量模型配置（管理员专用）
    
    参数:
    - model_name: 模型名称（可选）
    - api_endpoint: API端点（可选）
    - api_key: API密钥（可选）
    - embedding_dimension: 向量维度（可选）
    - parameters: 其他参数（可选）
    
    返回更新后的向量模型配置
    """
    try:
        config_service = ConfigService(db)
        config = await config_service.update_vector_config(
            model_name=request.model_name,
            api_endpoint=request.api_endpoint,
            api_key=request.api_key,
            embedding_dimension=request.embedding_dimension,
            parameters=request.parameters
        )

        response_data = _build_vector_config_response(
            config,
            updated_by=current_user.account,
        )
        _record_config_audit(
            current_user=current_user,
            target_type="vector_config",
            target_id=str(config.id),
            metadata={"action": "update_vector_config"},
        )
        return {
            "code": 200,
            "message": "更新成功",
            "data": response_data
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=public_exception_detail(e)
        )
    except Exception as e:
        logger.error(f"Failed to update vector config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新向量配置失败"
        )


@router.get(
    "/config/email",
    summary="获取邮件配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def get_email_config(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    try:
        config_service = ConfigService(db)
        config = await config_service.get_email_config()

        response_data = _build_email_config_response(config, updated_by="system")
        return {"code": 200, "message": "获取成功", "data": response_data}
    except Exception as e:
        logger.error(f"Failed to get email config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取邮件配置失败"
        )


@router.put(
    "/config/email",
    summary="更新邮件配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
@router.post(
    "/config/email",
    summary="更新邮件配置",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def update_email_config(
    request: EmailConfigUpdate,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    try:
        config_service = ConfigService(db)
        config = await config_service.update_email_config(
            smtp_host=request.smtp_host,
            smtp_port=request.smtp_port,
            smtp_user=request.smtp_user,
            smtp_password=request.smtp_password,
            from_email=request.from_email,
            auto_send_enabled=request.auto_send_enabled
        )

        response_data = _build_email_config_response(
            config,
            updated_by=current_user.account,
        )
        _record_config_audit(
            current_user=current_user,
            target_type="email_config",
            target_id=str(config.id),
            metadata={"action": "update_email_config"},
        )
        return {"code": 200, "message": "更新成功", "data": response_data}
    except Exception as e:
        logger.error(f"Failed to update email config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新邮件配置失败"
        )


@router.post(
    "/config/email/test",
    summary="测试邮件连接",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def test_email_connection(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    try:
        success, error_msg = await EmailService.test_email_connection(db)
        if success:
            return {"code": 200, "message": "连接测试成功", "data": None}
        else:
            return {"code": 400, "message": f"连接测试失败: {error_msg}", "data": None}
    except Exception as e:
        logger.error(f"Failed to test email connection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="测试邮件连接失败"
        )


@router.get(
    "/audit/events",
    summary="获取审计事件",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def list_audit_events(
    limit: int = 50,
    event_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    result: Optional[str] = None,
    target_type: Optional[str] = None,
    current_user: User = Depends(require_role(["administrator"])),
):
    events = AuditService.list_events(
        limit=limit,
        event_type=event_type,
        actor_id=actor_id,
        result=result,
        target_type=target_type,
    )
    return {
        "code": 200,
        "message": "获取成功",
        "data": [AuditLogEventContract(**event) for event in events],
    }


# ==================== 用户管理端点 ====================

class UserListResponse(BaseModel):
    """用户列表响应"""
    id: str
    account: str
    name: str
    email: str
    phone: Optional[str] = None
    user_type: str
    avatar: Optional[str] = None
    student_id: Optional[str] = None
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    managed_class_ids: List[str] = Field(default_factory=list)
    managed_classes: List[dict] = Field(default_factory=list)
    created_at: str
    
    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """更新用户请求"""
    account: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    student_id: Optional[str] = None
    class_id: Optional[str] = None
    managed_class_ids: Optional[List[str]] = None


def _build_user_response(user: User) -> UserListResponse:
    managed_classes = []
    if user.user_type == "teacher":
        managed_classes = [
            {
                "id": str(cls.id),
                "name": cls.name,
                "code": cls.code,
            }
            for cls in sorted(
                user.teaching_classes,
                key=lambda cls: (cls.name or "", str(cls.id)),
            )
        ]
    return UserListResponse(
        id=str(user.id),
        account=user.account,
        name=user.name,
        email=user.email,
        phone=user.phone,
        user_type=user.user_type,
        avatar=AvatarService.build_avatar_payload(user)["avatar"],
        student_id=user.student_id,
        class_id=str(user.class_id) if user.class_id else None,
        class_name=user.class_.name if user.class_ else None,
        managed_class_ids=[cls["id"] for cls in managed_classes],
        managed_classes=managed_classes,
        created_at=user.created_at.isoformat()
    )


@router.get(
    "/users",
    summary="获取用户列表",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def get_users(
    role: Optional[str] = None,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    获取系统中所有用户的列表（管理员专用）
    
    参数:
    - role: 可选的角色过滤器（teacher或student）
    
    返回用户列表，包含：
    - 用户基本信息
    - 账号、姓名、邮箱
    - 用户类型
    - 注册时间
    """
    try:
        # Build query
        query = db.query(User).options(
            joinedload(User.class_),
            selectinload(User.teaching_classes),
        )
        
        # Apply role filter if provided
        if role:
            if role not in ["teacher", "student"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="角色必须是teacher或student"
                )
            query = query.filter(User.user_type == role)
        else:
            # If no filter, exclude administrators from the list
            query = query.filter(User.user_type.in_(["teacher", "student"]))
        
        # Execute query
        users = query.order_by(User.created_at.desc()).all()
        
        # Convert to response format
        user_list = [_build_user_response(user) for user in users]
        
        return {
            "code": 200,
            "message": "获取成功",
            "data": user_list
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户列表失败"
        )


@router.get(
    "/users/{user_id}",
    summary="获取用户详情",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def get_user_by_id(
    user_id: str,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    获取指定用户的详细信息（管理员专用）
    
    参数:
    - user_id: 用户ID
    
    返回用户详细信息
    """
    try:
        # Query user by ID
        user = (
            db.query(User)
            .options(
                joinedload(User.class_),
                selectinload(User.teaching_classes),
            )
            .filter(User.id == uuid.UUID(user_id))
            .first()
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用户ID {user_id} 不存在"
            )
        
        user_data = _build_user_response(user)
        
        return {
            "code": 200,
            "message": "获取成功",
            "data": user_data
        }
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的用户ID格式"
        )
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户详情失败"
        )


@router.put(
    "/users/{user_id}",
    summary="更新用户信息",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    更新指定用户的资料（管理员专用）

    支持更新账号、姓名、邮箱、手机号，以及学生的学号和班级。
    """
    try:
        user_uuid = uuid.UUID(user_id)
        user = (
            db.query(User)
            .options(
                joinedload(User.class_),
                selectinload(User.teaching_classes),
            )
            .filter(User.id == user_uuid)
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用户ID {user_id} 不存在"
            )

        if user.user_type == "administrator":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="管理员账号请通过管理员专用入口维护"
            )

        provided_fields = getattr(request, "model_fields_set", getattr(request, "__fields_set__", set()))

        if "account" in provided_fields:
            account = (request.account or "").strip()
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="账号不能为空"
                )
            existing_account = (
                db.query(User)
                .filter(User.account == account, User.id != user.id)
                .first()
            )
            if existing_account:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="账号已存在"
                )
            user.account = account

        if "name" in provided_fields:
            name = (request.name or "").strip()
            if not name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="姓名不能为空"
                )
            user.name = name

        if "email" in provided_fields:
            email = (request.email or "").strip()
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱不能为空"
                )
            existing_email = (
                db.query(User)
                .filter(User.email == email, User.id != user.id)
                .first()
            )
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已存在"
                )
            user.email = email

        if "phone" in provided_fields:
            phone = (request.phone or "").strip()
            user.phone = phone or None

        if user.user_type == "student":
            if "student_id" in provided_fields:
                student_id = (request.student_id or "").strip()
                user.student_id = student_id or None

            if "class_id" in provided_fields:
                class_id = (request.class_id or "").strip()
                if not class_id:
                    user.class_id = None
                else:
                    try:
                        class_uuid = uuid.UUID(class_id)
                    except ValueError as exc:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="无效的班级ID格式"
                        ) from exc

                    class_record = db.query(Class).filter(Class.id == class_uuid).first()
                    if not class_record:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="班级不存在"
                        )
                    user.class_id = class_record.id
        elif user.user_type == "teacher" and "managed_class_ids" in provided_fields:
            requested_class_ids = list(dict.fromkeys(request.managed_class_ids or []))
            class_uuids = []
            for class_id in requested_class_ids:
                try:
                    class_uuids.append(uuid.UUID(class_id))
                except ValueError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="无效的班级ID格式"
                    ) from exc

            if class_uuids:
                class_records = db.query(Class).filter(Class.id.in_(class_uuids)).all()
                class_record_map = {cls.id: cls for cls in class_records}

                missing_ids = {
                    str(class_uuid)
                    for class_uuid in class_uuids
                    if class_uuid not in class_record_map
                }
                if missing_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"班级不存在: {', '.join(sorted(missing_ids))}"
                    )

                for class_uuid in class_uuids:
                    class_record_map[class_uuid].teacher_id = user.id

        db.commit()
        db.refresh(user)
        user = (
            db.query(User)
            .options(
                joinedload(User.class_),
                selectinload(User.teaching_classes),
            )
            .filter(User.id == user_uuid)
            .first()
        )

        return {
            "code": 200,
            "message": "更新成功",
            "data": _build_user_response(user)
        }
    except HTTPException:
        db.rollback()
        raise
    except ValueError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的用户ID格式"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户信息失败"
        )


# ==================== 密码管理端点 ====================

@router.put(
    "/password",
    summary="修改管理员密码",
    dependencies=[Depends(require_role(["administrator"]))]
)
async def change_admin_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """
    修改管理员密码（管理员专用）
    
    参数:
    - current_password: 当前密码
    - new_password: 新密码
    
    返回修改成功的消息
    
    注意：密码修改后需要重新登录
    """
    try:
        # Call AuthService to change admin password
        success = AuthService.change_admin_password(
            db=db,
            current_password=request.current_password,
            new_password=request.new_password
        )
        
        if success:
            _record_admin_action_audit(
                current_user=current_user,
                target_type="admin_password",
                target_id=str(current_user.id),
                result="success",
                metadata={"action": "change_admin_password"},
            )
            return {
                "code": 200,
                "message": "密码修改成功，请重新登录",
                "data": None
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="密码修改失败"
            )
    except ValueError as e:
        # Handle specific errors from AuthService
        error_msg = str(e)
        _record_admin_action_audit(
            current_user=current_user,
            target_type="admin_password",
            target_id=str(current_user.id),
            result="denied",
            metadata={"action": "change_admin_password", "reason": error_msg},
        )
        if "当前密码错误" in error_msg or "Current password is incorrect" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前密码错误"
            )
        elif "管理员账户不存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="管理员账户不存在"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
    except Exception as e:
        _record_admin_action_audit(
            current_user=current_user,
            target_type="admin_password",
            target_id=str(current_user.id),
            result="failed",
            metadata={"action": "change_admin_password", "reason": str(e)},
        )
        logger.error(f"Failed to change admin password: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码修改失败"
        )
