"""
辩论模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import List, TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .user import User
    from .class_model import Class
    from .speech import Speech
    from .document import Document
    from .score import Score

class Debate(Base):
    __tablename__ = "debates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    duration = Column(Integer, nullable=False)  # 分钟
    invitation_code = Column(String(6), unique=True, nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey('classes.id'), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    status = Column(
        Enum('draft', 'published', 'in_progress', 'completed', name='debate_status_enum'),
        default='draft'
    )
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    report = Column(JSON, nullable=True)  # 全局评分报告
    created_at = Column(DateTime, default=datetime.utcnow)

    report_pdf=Column(Text, nullable=True) # pdf报告文件路径
    
    # 关系
    class_: Mapped["Class"] = relationship("Class", back_populates="debates")
    teacher: Mapped["User"] = relationship("User", foreign_keys=[teacher_id])
    participations: Mapped[List["DebateParticipation"]] = relationship(
        "DebateParticipation",
        back_populates="debate"
    )
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="debate")
    speeches: Mapped[List["Speech"]] = relationship("Speech", back_populates="debate")
    
    def __repr__(self):
        return f"<Debate(id={self.id}, topic={self.topic[:30]}, status={self.status})>"


class DebateParticipation(Base):
    __tablename__ = "debate_participations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id = Column(UUID(as_uuid=True), ForeignKey('debates.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    role = Column(
        Enum('debater_1', 'debater_2', 'debater_3', 'debater_4', name='debater_role_enum'),
        nullable=False
    )
    stance = Column(Enum('positive', 'negative', name='stance_enum'), nullable=False)
    role_reason = Column(String(32), nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    debate: Mapped["Debate"] = relationship("Debate", back_populates="participations")
    user: Mapped["User"] = relationship("User", back_populates="debate_participations")
    scores: Mapped[List["Score"]] = relationship("Score", back_populates="participation")
    
    def __repr__(self):
        return f"<DebateParticipation(debate_id={self.debate_id}, user_id={self.user_id}, role={self.role})>"
