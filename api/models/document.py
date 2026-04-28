"""
文档模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from typing import TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .debate import Debate

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id = Column(UUID(as_uuid=True), ForeignKey('debates.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=True)  # 提取的文本内容
    embedding_status = Column(
        Enum('pending', 'processing', 'completed', 'failed', name='embedding_status_enum'),
        default='pending'
    )
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    debate: Mapped["Debate"] = relationship("Debate", back_populates="documents")
    
    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename})>"
