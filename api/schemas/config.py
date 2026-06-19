"""
Configuration schemas for API request/response validation
"""
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class AuthSessionUserContract(BaseModel):
    """Minimal user payload frozen for auth session responses."""

    id: str
    username: str
    role: Literal["student", "teacher", "admin"]


class AuthSessionContract(BaseModel):
    """Frozen auth-session contract for frontend integration."""

    access_token: str
    access_token_expires_in: int = Field(
        ge=0, description="Access token lifetime in seconds"
    )
    session_id: str
    user: AuthSessionUserContract
    refresh_strategy: Literal["http_only_cookie", "server_session"]
    requires_reauth: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock",
                "access_token_expires_in": 3600,
                "session_id": "0f97bc37-5396-438c-98ae-64b4b1b5f5c8",
                "user": {
                    "id": "8e137f6f-15f6-4554-91fa-ef46563d9807",
                    "username": "teacher_demo",
                    "role": "teacher",
                },
                "refresh_strategy": "server_session",
                "requires_reauth": False,
            }
        }


class AuthSessionCompatibleUserResponse(AuthSessionUserContract):
    """Runtime auth user payload during the compatibility window."""

    account: str
    name: str
    user_type: Literal["teacher", "student", "administrator"]
    email: Optional[str] = None
    phone: Optional[str] = None
    student_id: Optional[str] = None
    class_id: Optional[str] = None
    avatar: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_mode: Optional[str] = None
    avatar_default_key: Optional[str] = None
    created_at: Optional[datetime] = None


class AuthSessionRuntimeResponse(AuthSessionContract):
    """Actual login/refresh response while legacy frontend fields are preserved."""

    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(
        ge=0,
        description="Legacy alias for access_token_expires_in kept for compatibility",
    )
    user: AuthSessionCompatibleUserResponse

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh",
                "token_type": "bearer",
                "expires_in": 3600,
                "access_token_expires_in": 3600,
                "session_id": "0f97bc37-5396-438c-98ae-64b4b1b5f5c8",
                "user": {
                    "id": "8e137f6f-15f6-4554-91fa-ef46563d9807",
                    "username": "teacher_demo",
                    "role": "teacher",
                    "account": "teacher_demo",
                    "name": "Teacher Demo",
                    "user_type": "teacher",
                    "email": "teacher_demo@example.local",
                },
                "refresh_strategy": "server_session",
                "requires_reauth": False,
            }
        }


class AuthSessionApiResponse(BaseModel):
    """Standard success envelope for login/refresh auth responses."""

    code: int = 200
    message: str
    data: AuthSessionRuntimeResponse


class ModelConfigResponse(BaseModel):
    """Model configuration response schema"""
    id: str
    model_name: str
    api_endpoint: str
    api_key: str
    temperature: float = Field(ge=0.0, le=2.0, description="Temperature for model sampling")
    max_tokens: int = Field(gt=0, description="Maximum tokens for model output")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "model_name": "gpt-3.5-turbo",
                "api_endpoint": "https://api.openai.com/v1/chat/completions",
                "api_key": "sk-...",
                "temperature": 0.7,
                "max_tokens": 2000,
                "parameters": {},
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00"
            }
        }


class ModelConfigUpdate(BaseModel):
    """Model configuration update request schema"""
    model_name: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature for model sampling")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens for model output")
    parameters: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "model_name": "gpt-4",
                "api_endpoint": "https://api.openai.com/v1/chat/completions",
                "temperature": 0.8,
                "max_tokens": 3000
            }
        }


class CozeConfigResponse(BaseModel):
    """Coze agent configuration response schema"""
    id: str
    # 4个AI辩手 Bot ID
    debater_1_bot_id: str
    debater_2_bot_id: str
    debater_3_bot_id: str
    debater_4_bot_id: str
    # 裁判 Bot ID
    judge_bot_id: str
    # 辅助/导师 Bot ID
    mentor_bot_id: str
    # API Token
    api_token: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "debater_1_bot_id": "7428xxxxxx",
                "debater_2_bot_id": "7428xxxxxx",
                "debater_3_bot_id": "7428xxxxxx",
                "debater_4_bot_id": "7428xxxxxx",
                "judge_bot_id": "7428xxxxxx",
                "mentor_bot_id": "7428xxxxxx",
                "api_token": "pat_...",
                "parameters": {
                    "timeout": 30,
                    "retry_count": 3,
                    "ai_turns": {
                        "default": {
                            "prethinking_mode": "reactive",
                            "response_delay_sec": 2,
                            "thinking_timeout_sec": 20,
                            "draft_ttl_sec": 120
                        },
                        "opening_negative_1": {
                            "prethinking_mode": "eager",
                            "response_delay_sec": 0
                        },
                        "questioning_1_ai2_ask": {
                            "prethinking_mode": "eager",
                            "response_delay_sec": 0
                        },
                        "questioning_3_ai3_ask": {
                            "prethinking_mode": "eager",
                            "response_delay_sec": 0
                        },
                        "questioning_2_neg_answer": {
                            "prethinking_mode": "reactive",
                            "response_delay_sec": 0,
                            "thinking_timeout_sec": 15
                        }
                    }
                },
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00"
            }
        }


class CozeConfigUpdate(BaseModel):
    """Coze agent configuration update request schema"""
    debater_1_bot_id: Optional[str] = None
    debater_2_bot_id: Optional[str] = None
    debater_3_bot_id: Optional[str] = None
    debater_4_bot_id: Optional[str] = None
    judge_bot_id: Optional[str] = None
    mentor_bot_id: Optional[str] = None
    api_token: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "debater_1_bot_id": "7428xxxxxx",
                "debater_2_bot_id": "7428xxxxxx",
                "debater_3_bot_id": "7428xxxxxx",
                "debater_4_bot_id": "7428xxxxxx",
                "judge_bot_id": "7428xxxxxx",
                "mentor_bot_id": "7428xxxxxx",
                "api_token": "pat_...",
                "parameters": {
                    "timeout": 60,
                    "retry_count": 5,
                    "ai_turns": {
                        "questioning_1_ai2_ask": {
                            "prethinking_mode": "eager",
                            "response_delay_sec": 0
                        },
                        "questioning_2_neg_answer": {
                            "prethinking_mode": "reactive",
                            "response_delay_sec": 0,
                            "thinking_timeout_sec": 15
                        },
                        "free_debate": {
                            "thinking_timeout_sec": 15,
                            "response_delay_sec": 0
                        }
                    }
                }
            }
        }


class AsrConfigResponse(BaseModel):
    id: str
    model_name: str
    api_endpoint: str
    api_key: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AsrConfigUpdate(BaseModel):
    model_name: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class TtsConfigResponse(BaseModel):
    id: str
    model_name: str
    api_endpoint: str
    api_key: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TtsConfigUpdate(BaseModel):
    model_name: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class GeneralConfigResponse(BaseModel):
    """General configuration response schema"""
    id: str
    key: str
    value: str
    description: Optional[str] = None
    updated_at: datetime
    
    class Config:
        from_attributes = True


class GeneralConfigUpdate(BaseModel):
    """General configuration update request schema"""
    value: str
    description: Optional[str] = None


class VectorConfigResponse(BaseModel):
    """向量模型配置响应"""
    id: str
    model_name: str
    api_endpoint: str
    api_key: str
    embedding_dimension: int = Field(gt=0, description="向量维度")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174003",
                "model_name": "text-embedding-ada-002",
                "api_endpoint": "https://api.openai.com/v1/embeddings",
                "api_key": "sk-...",
                "embedding_dimension": 1536,
                "parameters": {},
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00"
            }
        }


class VectorConfigUpdate(BaseModel):
    """向量模型配置更新请求"""
    model_name: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    embedding_dimension: Optional[int] = Field(None, gt=0, description="向量维度")
    parameters: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "model_name": "text-embedding-3-small",
                "api_endpoint": "https://api.openai.com/v1/embeddings",
                "embedding_dimension": 1536,
                "parameters": {}
            }
        }


class EmailConfigResponse(BaseModel):
    """邮件配置响应（安全版本，不包含明文密码）"""
    id: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password_configured: bool
    smtp_password_masked: Optional[str] = None
    from_email: str
    auto_send_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailConfigUpdate(BaseModel):
    """邮件配置更新请求"""
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: Optional[str] = None
    auto_send_enabled: Optional[bool] = None
