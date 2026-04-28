"""
成就模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .user import User

class Achievement(Base):
    __tablename__ = "achievements"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    achievement_type = Column(String(50), nullable=False)  # first_debate, win_streak_3, mvp, etc.
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String(100), nullable=False)
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    user: Mapped["User"] = relationship("User")
    
    def __repr__(self):
        return f"<Achievement(id={self.id}, type={self.achievement_type}, user_id={self.user_id})>"
