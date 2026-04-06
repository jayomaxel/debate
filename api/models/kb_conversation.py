"""
知识库对话模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped
from typing import TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .user import User


class KBConversation(Base):
    """知识库对话记录模型"""
    __tablename__ = "kb_conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    session_id = Column(String(100), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    # sources: List of {document_id, document_name, chunk_content, similarity_score}
    sources = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 关系
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<KBConversation(id={self.id}, user_id={self.user_id}, session_id={self.session_id})>"
