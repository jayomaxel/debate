"""
配置模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from database import Base
from config import settings


class ModelConfig(Base):
    """AI模型配置模型"""
    __tablename__ = "model_config"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False)
    api_endpoint = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False)  # 生产环境中应加密
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2000)
    parameters = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_default(cls):
        """返回默认配置"""
        return cls(
            model_name="gpt-3.5-turbo",
            api_endpoint="https://api.openai.com/v1/chat/completions",
            api_key="",
            temperature=0.7,
            max_tokens=2000,
            parameters={}
        )
    
    def __repr__(self):
        return f"<ModelConfig(id={self.id}, model_name={self.model_name})>"


class CozeConfig(Base):
    """Coze代理配置模型 - 支持多个 Bot Agent"""
    __tablename__ = "coze_config"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 4个AI辩手 Bot ID
    debater_1_bot_id = Column(String(255), nullable=False, default="")
    debater_2_bot_id = Column(String(255), nullable=False, default="")
    debater_3_bot_id = Column(String(255), nullable=False, default="")
    debater_4_bot_id = Column(String(255), nullable=False, default="")
    # 裁判 Bot ID
    judge_bot_id = Column(String(255), nullable=False, default="")
    # 辅助/导师 Bot ID
    mentor_bot_id = Column(String(255), nullable=False, default="")
    # API Token
    api_token = Column(String(255), nullable=False)  # 生产环境中应加密
    # 其他参数
    parameters = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_default_ai_turns(cls) -> dict:
        """返回 AI 回合时序策略默认配置。"""
        return {
            "default": {
                "prethinking_mode": "reactive",
                "response_delay_sec": 2,
                "thinking_timeout_sec": 20,
                "draft_ttl_sec": 120,
            },
            "opening_negative_1": {
                "prethinking_mode": "eager",
                "response_delay_sec": 3,
            },
            "questioning_1_ai2_ask": {
                "prethinking_mode": "eager",
                "response_delay_sec": 2,
            },
        }

    @classmethod
    def get_default(cls):
        """返回默认配置"""
        return cls(
            debater_1_bot_id="",
            debater_2_bot_id="",
            debater_3_bot_id="",
            debater_4_bot_id="",
            judge_bot_id="",
            mentor_bot_id="",
            api_token="",
            parameters={}
        )
    
    def __repr__(self):
        return f"<CozeConfig(id={self.id}, debater_1={self.debater_1_bot_id})>"


class AsrConfig(Base):
    __tablename__ = "asr_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False)
    api_endpoint = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False)
    parameters = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_default(cls):
        return cls(
            model_name="whisper-1",
            api_endpoint="https://api.openai.com/v1/audio/transcriptions",
            api_key="",
            parameters={}
        )

    def __repr__(self):
        return f"<AsrConfig(id={self.id}, model_name={self.model_name})>"


class TtsConfig(Base):
    __tablename__ = "tts_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False)
    api_endpoint = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False)
    parameters = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_default(cls):
        return cls(
            model_name="tts-1",
            api_endpoint="https://api.openai.com/v1/audio/speech",
            api_key="",
            parameters={
                "voice": "alloy",
                "speed": settings.TTS_DEFAULT_SPEED,
                "response_format": "mp3"
            }
        )

    def __repr__(self):
        return f"<TtsConfig(id={self.id}, model_name={self.model_name})>"


class VectorConfig(Base):
    """向量模型配置"""
    __tablename__ = "vector_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False)
    api_endpoint = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False)
    embedding_dimension = Column(Integer, default=1536)
    parameters = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_default(cls):
        return cls(
            model_name="text-embedding-ada-002",
            api_endpoint="https://api.openai.com/v1/embeddings",
            api_key="",
            embedding_dimension=1536,
            parameters={}
        )

    def __repr__(self):
        return f"<VectorConfig(id={self.id}, model_name={self.model_name})>"


class EmailConfig(Base):
    """邮件配置"""
    __tablename__ = "email_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    smtp_host = Column(String(255), nullable=False)
    smtp_port = Column(Integer, nullable=False, default=587)
    smtp_user = Column(String(255), nullable=False)
    smtp_password = Column(String(255), nullable=False)
    from_email = Column(String(255), nullable=False)
    auto_send_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_default(cls):
        return cls(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_user="",
            smtp_password="",
            from_email="",
            auto_send_enabled=False
        )

    def __repr__(self):
        return f"<EmailConfig(id={self.id}, smtp_host={self.smtp_host})>"
