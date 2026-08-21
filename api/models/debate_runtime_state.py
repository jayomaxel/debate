"""Authoritative database state for realtime debate rooms."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class DebateRuntimeState(Base):
    __tablename__ = "debate_runtime_states"
    __table_args__ = (
        Index("idx_debate_runtime_states_debate", "debate_id", unique=True),
        Index("idx_debate_runtime_states_lease", "lease_expires_at"),
    )

    room_id = Column(String(64), primary_key=True)
    debate_id = Column(UUID(as_uuid=True), ForeignKey("debates.id", ondelete="CASCADE"), nullable=False)
    state = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=0, server_default="0")
    lease_owner = Column(String(128), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
