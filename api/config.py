"""
配置管理模块
"""
import os
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    """系统配置"""
    
    # 应用配置
    APP_NAME: str = "辩论教学系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # 数据库配置
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://pgvector:pgvector@124.223.80.94:54333/debate_system"
    )
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    
    # Redis配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", "124.223.80.94")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6479"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "1"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", "tradingagents123")
    
    # JWT配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7天
    
    # OpenAI配置（优先从 model_config 表读取，这里仅作为 fallback）
    # 生产环境建议通过管理员端配置，而不是环境变量
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL_NAME: str = os.getenv("OPENAI_MODEL_NAME", "gpt-4")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    ENABLE_LLM_ROLE_ASSIGNMENT: bool = os.getenv(
        "ENABLE_LLM_ROLE_ASSIGNMENT", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}

    ASR_API_KEY: Optional[str] = os.getenv("ASR_API_KEY", None)
    ASR_BASE_URL: str = os.getenv("ASR_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
    ASR_MODEL_NAME: str = os.getenv("ASR_MODEL_NAME", "qwen3-asr-flash-filetrans")
    ASR_API_ENDPOINT: str = os.getenv("ASR_API_ENDPOINT", "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription")

    TTS_API_KEY: Optional[str] = os.getenv("TTS_API_KEY", None)
    TTS_BASE_URL: str = os.getenv("TTS_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
    TTS_MODEL_NAME: str = os.getenv("TTS_MODEL_NAME", "qwen3-tts-flash")
    TTS_API_ENDPOINT: str = os.getenv("TTS_API_ENDPOINT", "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation")
    # TTS 默认语速，后台配置未填写或值异常时统一回退到这里。
    TTS_DEFAULT_SPEED: float = float(os.getenv("TTS_DEFAULT_SPEED", "1.5"))
    
    # Coze配置（优先从 coze_config 表读取，这里仅作为 fallback）
    # 生产2环境建议通过管理员端配置，而不是环境变量
    COZE_API_KEY: Optional[str] = os.getenv("COZE_API_KEY", None)
    COZE_BASE_URL: str = os.getenv("COZE_BASE_URL", "https://api.coze.cn")

    DEBATE_AI_PROVIDER: str = os.getenv("DEBATE_AI_PROVIDER", "llm")
    
    # 文件上传配置
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".doc"}
    
    # 邮件配置
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER", None)
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD", None)
    SMTP_FROM_EMAIL: Optional[str] = os.getenv("SMTP_FROM_EMAIL", None)

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_flag(cls, value):
        if isinstance(value, bool):
            return value

        if value is None:
            return True

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "t", "yes", "y", "on", "debug", "dev", "development"}:
                return True
            if normalized in {"0", "false", "f", "no", "n", "off", "release", "prod", "production"}:
                return False

        raise ValueError(
            "DEBUG 必须是可解析的布尔值，例如 true/false、1/0、debug/dev 或 release/production。"
        )
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# 创建全局配置实例
settings = Settings()
