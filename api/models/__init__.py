"""
数据模型包
"""
from .user import User
from .class_model import Class
from .debate import Debate, DebateParticipation
from .speech import Speech
from .score import Score
from .document import Document
from .achievement import Achievement
from .assessment import AbilityAssessment
from .config import ModelConfig, CozeConfig, AsrConfig, TtsConfig
from .kb_document import KBDocument, KBDocumentChunk
from .kb_conversation import KBConversation

__all__ = [
    "User",
    "Class",
    "Debate",
    "DebateParticipation",
    "Speech",
    "Score",
    "Document",
    "Achievement",
    "AbilityAssessment",
    "ModelConfig",
    "CozeConfig",
    "AsrConfig",
    "TtsConfig",
    "KBDocument",
    "KBDocumentChunk",
    "KBConversation",
]
