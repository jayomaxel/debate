"""
评分模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .debate import DebateParticipation
    from .speech import Speech

class Score(Base):
    __tablename__ = "scores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participation_id = Column(UUID(as_uuid=True), ForeignKey('debate_participations.id'), nullable=False)
    speech_id = Column(UUID(as_uuid=True), ForeignKey('speeches.id'), nullable=True)
    
    # 五维能力评分
    logic_score = Column(Float, nullable=False)  # 逻辑建构力
    argument_score = Column(Float, nullable=False)  # AI核心知识运用
    response_score = Column(Float, nullable=False)  # 批判性思维
    persuasion_score = Column(Float, nullable=False)  # 语言表达力
    teamwork_score = Column(Float, nullable=False)  # AI伦理与科技素养
    
    overall_score = Column(Float, nullable=False)  # 总分
    feedback = Column(Text, nullable=True)  # 反馈
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    participation: Mapped["DebateParticipation"] = relationship(
        "DebateParticipation",
        back_populates="scores"
    )
    speech: Mapped["Speech"] = relationship("Speech", foreign_keys=[speech_id])
    
    def __repr__(self):
        return f"<Score(id={self.id}, overall={self.overall_score})>"
