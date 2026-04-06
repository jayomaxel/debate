"""
Configuration schemas for API request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


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
                    "retry_count": 3
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
                    "retry_count": 5
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
    """邮件配置响应"""
    id: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
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
