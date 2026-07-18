"""
配置管理模块
"""
import json
import os
from pathlib import Path
from typing import Annotated, Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PUBLIC_BASE_URL = "https://csidebate.xyz"
DEFAULT_E2E_HEALTH_PROBE_AUDIO_PATH = str(
    BASE_DIR / "health_fixtures" / "e2e_probe.wav"
)
DEFAULT_E2E_HEALTH_PROBE_EXPECTED_TEXT = "健康探针"
DEFAULT_ALLOWED_ORIGINS = [
    "https://csidebate.xyz",
    "http://csidebate.xyz",
    "http://8.137.182.23:8860",
]


def _parse_env_list(name: str, default: Optional[str] = None) -> list[str]:
    """从环境变量解析逗号分隔的字符串列表。"""
    raw = os.getenv(name, default)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _coerce_list_value(value: Any, default: Optional[list[str]] = None) -> list[str]:
    """Accept both JSON arrays and comma-separated strings for env-backed lists."""
    fallback = list(default or [])

    if value is None:
        return fallback

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return fallback
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in raw.split(",") if item.strip()]

    normalized = str(value).strip()
    return [normalized] if normalized else fallback


class Settings(BaseSettings):
    """系统配置"""

    # 环境分层
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    IS_PRODUCTION: bool = ENVIRONMENT.lower() in {"prod", "production"}

    # 应用配置
    APP_NAME: str = "辩论教学系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 数据库配置（移除生产公网默认地址，开发环境可本地启动）
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    PUBLIC_BASE_URL: str = os.getenv(
        "PUBLIC_BASE_URL", DEFAULT_PUBLIC_BASE_URL
    ).strip().rstrip("/")

    # Redis配置（默认本地，生产必须显式配置）
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    REALTIME_MULTI_INSTANCE: bool = os.getenv("REALTIME_MULTI_INSTANCE", "false").lower() in {
        "1", "true", "yes", "on"
    }
    INSTANCE_ID: str = os.getenv("INSTANCE_ID", "")

    # CORS 配置（生产环境禁止 allow_origins=["*"] 与 allow_credentials=True 同时出现）
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = DEFAULT_ALLOWED_ORIGINS.copy()

    # JWT配置（生产必须显式配置 SECRET_KEY）
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
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
    UPLOAD_QUARANTINE_DIR: str = "uploads/quarantine"
    REPORT_FILE_STORAGE_BACKEND: str = os.getenv("REPORT_FILE_STORAGE_BACKEND", "local")
    REPORT_FILE_STORAGE_DIR: str = os.getenv("REPORT_FILE_STORAGE_DIR", "private_storage/reports")
    # 生产链路健康探针：必须显式提供一段可识别的短音频，避免仅凭配置项误判健康。
    E2E_HEALTH_PROBE_ENABLED: bool = os.getenv(
        "E2E_HEALTH_PROBE_ENABLED",
        "true" if IS_PRODUCTION else "false",
    ).strip().lower() in {"1", "true", "yes", "on"}
    E2E_HEALTH_PROBE_AUDIO_PATH: Optional[str] = os.getenv(
        "E2E_HEALTH_PROBE_AUDIO_PATH", DEFAULT_E2E_HEALTH_PROBE_AUDIO_PATH
    )
    E2E_HEALTH_PROBE_AUDIO_B64: Optional[str] = os.getenv(
        "E2E_HEALTH_PROBE_AUDIO_B64", None
    )
    E2E_HEALTH_PROBE_AUDIO_FORMAT: str = os.getenv(
        "E2E_HEALTH_PROBE_AUDIO_FORMAT", "wav"
    )
    E2E_HEALTH_PROBE_EXPECTED_TEXT: Optional[str] = os.getenv(
        "E2E_HEALTH_PROBE_EXPECTED_TEXT", DEFAULT_E2E_HEALTH_PROBE_EXPECTED_TEXT
    )
    E2E_HEALTH_PROBE_TIMEOUT_SECONDS: float = float(
        os.getenv("E2E_HEALTH_PROBE_TIMEOUT_SECONDS", "30")
    )
    E2E_HEALTH_PROBE_TOKEN: Optional[str] = os.getenv(
        "E2E_HEALTH_PROBE_TOKEN", None
    )
    RELEASE_GATE_REQUIRE_E2E_HEALTH: bool = os.getenv(
        "RELEASE_GATE_REQUIRE_E2E_HEALTH",
        "true" if IS_PRODUCTION else "false",
    ).strip().lower() in {"1", "true", "yes", "on"}
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".doc"}
    AVATAR_MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024  # 2MB
    
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
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def normalize_allowed_origins(cls, value):
        return _coerce_list_value(value, DEFAULT_ALLOWED_ORIGINS)

    class Config:
        env_file = ".env"
        case_sensitive = True

# 创建全局配置实例
settings = Settings()

# 生产环境 fail-fast 校验
if settings.IS_PRODUCTION:
    if settings.SECRET_KEY == "your-secret-key-change-in-production":
        raise ValueError("生产环境必须配置 SECRET_KEY")
    if not settings.DATABASE_URL:
        raise ValueError("生产环境必须配置 DATABASE_URL")
    if settings.DEBUG:
        raise ValueError("生产环境 DEBUG 不能为 true")
    if "*" in settings.ALLOWED_ORIGINS and settings.ALLOWED_ORIGINS != ["*"]:
        # 允許單獨 ["*"] 但不建議與 credentials 同時使用；這裡只檢查極端情況
        pass
    # 額外：若同時開啟 allow_credentials 與 [*]，在 main.py 啟動時再做攔截或警示
