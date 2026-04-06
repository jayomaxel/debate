"""
班级模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import List, TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .user import User
    from .debate import Debate

class Class(Base):
    __tablename__ = "classes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False, index=True)  # 班级代码
    teacher_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    teacher: Mapped["User"] = relationship("User", foreign_keys=[teacher_id])
    students: Mapped[List["User"]] = relationship(
        "User", 
        back_populates="class_",
        foreign_keys="User.class_id"
    )
    debates: Mapped[List["Debate"]] = relationship("Debate", back_populates="class_")
    
    def __repr__(self):
        return f"<Class(id={self.id}, name={self.name}, code={self.code})>"
