"""
发言记录模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .debate import Debate
    from .user import User

class Speech(Base):
    __tablename__ = "speeches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id = Column(UUID(as_uuid=True), ForeignKey('debates.id'), nullable=False)
    speaker_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)  # NULL表示AI
    speaker_type = Column(Enum('human', 'ai', name='speaker_type_enum'), nullable=False)
    speaker_role = Column(String(20), nullable=False)  # debater_1, ai_1, etc.
    phase = Column(
        Enum('opening', 'questioning', 'free_debate', 'closing', name='debate_phase_enum'),
        nullable=False
    )
    content = Column(Text, nullable=False)
    audio_url = Column(String(500), nullable=True)
    duration = Column(Integer, nullable=False)  # 秒
    transcription_status = Column(String(20), nullable=True)
    transcription_error = Column(Text, nullable=True)
    is_valid_for_scoring = Column(Boolean, nullable=False, default=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    debate: Mapped["Debate"] = relationship("Debate", back_populates="speeches")
    speaker: Mapped["User"] = relationship("User", foreign_keys=[speaker_id])
    
    def __repr__(self):
        return f"<Speech(id={self.id}, speaker_role={self.speaker_role}, phase={self.phase})>"
