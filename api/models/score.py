"""
评分模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, Column, Float, Text, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .debate import DebateParticipation
    from .speech import Speech

class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        Index("idx_scores_analytics_eligible", "eligible_for_analytics", "participation_id"),
        Index("idx_scores_status", "status"),
        CheckConstraint(
            "status IN ('validated', 'repaired', 'fallback', 'failed', 'legacy_unknown')",
            name="ck_scores_status",
        ),
        CheckConstraint(
            "eligible_for_analytics = false OR status IN ('validated', 'repaired')",
            name="ck_scores_analytics_eligibility",
        ),
    )
    
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
    status = Column(String(32), nullable=False, default="legacy_unknown", server_default="legacy_unknown")
    scoring_source = Column(String(64), nullable=False, default="legacy_unknown", server_default="legacy_unknown")
    scoring_quality = Column(String(32), nullable=False, default="legacy_unknown", server_default="legacy_unknown")
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    provider = Column(String(64), nullable=True)
    model = Column(String(128), nullable=True)
    rubric_version = Column(String(64), nullable=True)
    failure_code = Column(String(64), nullable=True)
    score_metadata = Column("metadata", JSON, nullable=False, default=dict, server_default="{}")
    eligible_for_analytics = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    participation: Mapped["DebateParticipation"] = relationship(
        "DebateParticipation",
        back_populates="scores"
    )
    speech: Mapped["Speech"] = relationship("Speech", foreign_keys=[speech_id])
    
    def __repr__(self):
        return f"<Score(id={self.id}, overall={self.overall_score})>"
