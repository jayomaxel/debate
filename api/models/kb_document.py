"""
知识库文档模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, Enum, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship, Mapped
from typing import List, TYPE_CHECKING
from database import Base

if TYPE_CHECKING:
    from .user import User
    from .kb_conversation import KBConversation


class KBDocument(Base):
    """知识库文档模型"""
    __tablename__ = "kb_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_status = Column(
        Enum('pending', 'processing', 'completed', 'failed', name='upload_status_enum', create_type=False),
        nullable=False,
        server_default='pending'
    )
    error_message = Column(Text, nullable=True)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    # 关系
    uploader: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by])
    chunks: Mapped[List["KBDocumentChunk"]] = relationship(
        "KBDocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    
    def __repr__(self):
        return f"<KBDocument(id={self.id}, filename={self.filename}, status={self.upload_status})>"


class KBDocumentChunk(Base):
    """知识库文档块模型（包含向量嵌入）"""
    __tablename__ = "kb_document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('kb_documents.id', ondelete='CASCADE'), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False)
    embedding = Column(ARRAY(Float), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 关系
    document: Mapped["KBDocument"] = relationship("KBDocument", back_populates="chunks")
    
    def __repr__(self):
        return f"<KBDocumentChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"
