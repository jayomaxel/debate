"""
管理员端API路由
提供系统级管理功能，包括班级管理、配置管理、用户管理等
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional, List
import uuid

from database import get_db
from models.user import User
from services.class_service import ClassService
from services.config_service import ConfigService
from services.auth_service import AuthService
from middleware.auth_middleware import require_role
from logging_config import get_logger
from schemas.config import (
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
)
from schemas.auth import PasswordChangeRequest
from utils.email_service import EmailService

logger = get_logger(__name__)
print("LOADING ADMIN ROUTER MODULE")

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
            detail=str(e)
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
            detail=str(e)
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
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete class {class_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除班级失败"
        )


# ==================== 配置管理端点 ====================

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
        
        # Convert to response format
        response_data = ModelConfigResponse(
            id=str(config.id),
            model_name=config.model_name,
            api_endpoint=config.api_endpoint,
            api_key=config.api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            parameters=config.parameters,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
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
        
        # Convert to response format
        response_data = ModelConfigResponse(
            id=str(config.id),
            model_name=config.model_name,
            api_endpoint=config.api_endpoint,
            api_key=config.api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            parameters=config.parameters,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
        return {
            "code": 200,
            "message": "更新成功",
            "data": response_data
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
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

        response_data = AsrConfigResponse(
            id=str(config.id),
            model_name=config.model_name,
            api_endpoint=config.api_endpoint,
            api_key=config.api_key,
            parameters=config.parameters,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
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

        response_data = AsrConfigResponse(
            id=str(config.id),
            model_name=config.model_name,
            api_endpoint=config.api_endpoint,
            api_key=config.api_key,
            parameters=config.parameters,
            created_at=config.created_at,
            updated_at=config.updated_at,
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

        response_data = TtsConfigResponse(
            id=str(config.id),
            model_name=config.model_name,
            api_endpoint=config.api_endpoint,
            api_key=config.api_key,
            parameters=config.parameters,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
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

        response_data = TtsConfigResponse(
            id=str(config.id),
            model_name=config.model_name,
            api_endpoint=config.api_endpoint,
            api_key=config.api_key,
            parameters=config.parameters,
            created_at=config.created_at,
            updated_at=config.updated_at,
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
        
        # Convert to response format
        response_data = CozeConfigResponse(
            id=str(config.id),
            debater_1_bot_id=config.debater_1_bot_id,
            debater_2_bot_id=config.debater_2_bot_id,
            debater_3_bot_id=config.debater_3_bot_id,
            debater_4_bot_id=config.debater_4_bot_id,
            judge_bot_id=config.judge_bot_id,
            mentor_bot_id=config.mentor_bot_id,
            api_token=config.api_token,
            parameters=config.parameters,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
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
        
        # Convert to response format
        response_data = CozeConfigResponse(
            id=str(config.id),
            debater_1_bot_id=config.debater_1_bot_id,
            debater_2_bot_id=config.debater_2_bot_id,
            debater_3_bot_id=config.debater_3_bot_id,
            debater_4_bot_id=config.debater_4_bot_id,
            judge_bot_id=config.judge_bot_id,
            mentor_bot_id=config.mentor_bot_id,
            api_token=config.api_token,
            parameters=config.parameters,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
        return {
            "code": 200,
            "message": "更新成功",
            "data": response_data
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
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
        
        response_data = VectorConfigResponse(
            id=str(config.id),
            model_name=config.model_name,
            api_endpoint=config.api_endpoint,
            api_key=config.api_key,
            embedding_dimension=config.embedding_dimension,
            parameters=config.parameters,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
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
        
        response_data = VectorConfigResponse(
            id=str(config.id),
            model_name=config.model_name,
            api_endpoint=config.api_endpoint,
            api_key=config.api_key,
            embedding_dimension=config.embedding_dimension,
            parameters=config.parameters,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
        return {
            "code": 200,
            "message": "更新成功",
            "data": response_data
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
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
    # dependencies=[Depends(require_role(["administrator"]))]
)
async def get_email_config(
    # current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    print("INSIDE GET_EMAIL_CONFIG")
    try:
        config_service = ConfigService(db)
        config = await config_service.get_email_config()
        
        response_data = EmailConfigResponse(
            id=str(config.id),
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            smtp_user=config.smtp_user,
            smtp_password=config.smtp_password,
            from_email=config.from_email,
            auto_send_enabled=config.auto_send_enabled,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
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
        
        response_data = EmailConfigResponse(
            id=str(config.id),
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            smtp_user=config.smtp_user,
            smtp_password=config.smtp_password,
            from_email=config.from_email,
            auto_send_enabled=config.auto_send_enabled,
            created_at=config.created_at,
            updated_at=config.updated_at
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


# ==================== 用户管理端点 ====================

class UserListResponse(BaseModel):
    """用户列表响应"""
    id: str
    account: str
    name: str
    email: str
    user_type: str
    student_id: Optional[str] = None
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    created_at: str
    
    class Config:
        from_attributes = True


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
        query = db.query(User).options(joinedload(User.class_))
        
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
        user_list = [
            UserListResponse(
                id=str(user.id),
                account=user.account,
                name=user.name,
                email=user.email,
                user_type=user.user_type,
                student_id=user.student_id,
                class_id=str(user.class_id) if user.class_id else None,
                class_name=user.class_.name if user.class_ else None,
                created_at=user.created_at.isoformat()
            )
            for user in users
        ]
        
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
        user = db.query(User).options(joinedload(User.class_)).filter(User.id == uuid.UUID(user_id)).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用户ID {user_id} 不存在"
            )
        
        # Convert to response format
        user_data = UserListResponse(
            id=str(user.id),
            account=user.account,
            name=user.name,
            email=user.email,
            user_type=user.user_type,
            student_id=user.student_id,
            class_id=str(user.class_id) if user.class_id else None,
            class_name=user.class_.name if user.class_ else None,
            created_at=user.created_at.isoformat()
        )
        
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
        logger.error(f"Failed to change admin password: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码修改失败"
        )
