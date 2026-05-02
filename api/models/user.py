"""
User model.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Column, DateTime, Enum, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from database import Base

if TYPE_CHECKING:
    from .class_model import Class
    from .debate import DebateParticipation


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    user_type = Column(
        Enum("teacher", "student", "administrator", name="user_type_enum"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    student_id = Column(String(50), nullable=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=True)
    avatar_blob = Column(LargeBinary, nullable=True)
    avatar_mime_type = Column(String(100), nullable=True)
    avatar_filename = Column(String(255), nullable=True)
    avatar_default_key = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    class_: Mapped["Class"] = relationship(
        "Class",
        back_populates="students",
        foreign_keys=[class_id],
    )
    teaching_classes: Mapped[List["Class"]] = relationship(
        "Class",
        back_populates="teacher",
        foreign_keys="Class.teacher_id",
    )
    debate_participations: Mapped[List["DebateParticipation"]] = relationship(
        "DebateParticipation",
        back_populates="user",
    )

    def __repr__(self):
        return f"<User(id={self.id}, account={self.account}, type={self.user_type})>"
