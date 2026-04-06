"""
能力评估模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .user import User

class AbilityAssessment(Base):
    __tablename__ = "ability_assessments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    personality_type = Column(String(10), nullable=True)  # MBTI类型
    expression_willingness = Column(Integer, nullable=False)
    logical_thinking = Column(Integer, nullable=False)
    expression_willingness_score = Column(Integer, nullable=True)
    logical_thinking_score = Column(Integer, nullable=True)
    stablecoin_knowledge_score = Column(Integer, nullable=True)
    financial_knowledge_score = Column(Integer, nullable=True)
    critical_thinking_score = Column(Integer, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    recommended_role = Column(
        Enum('debater_1', 'debater_2', 'debater_3', 'debater_4', name='recommended_role_enum'),
        nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    user: Mapped["User"] = relationship("User")
    
    def __repr__(self):
        return f"<AbilityAssessment(id={self.id}, user_id={self.user_id}, role={self.recommended_role})>"
