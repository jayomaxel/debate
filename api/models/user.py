"""
用户模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import List, TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .class_model import Class
    from .debate import DebateParticipation

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    user_type = Column(Enum('teacher', 'student', 'administrator', name='user_type_enum'), nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    student_id = Column(String(50), nullable=True)  # 学号
    class_id = Column(UUID(as_uuid=True), ForeignKey('classes.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    class_: Mapped["Class"] = relationship("Class", back_populates="students", foreign_keys=[class_id])
    teaching_classes: Mapped[List["Class"]] = relationship(
        "Class",
        back_populates="teacher",
        foreign_keys="Class.teacher_id",
    )
    debate_participations: Mapped[List["DebateParticipation"]] = relationship(
        "DebateParticipation", 
        back_populates="user"
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, account={self.account}, type={self.user_type})>"
