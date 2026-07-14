"""
Teaching design and topic recommendation persistence models.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from database import Base

if TYPE_CHECKING:
    from .class_model import Class
    from .user import User


class ClassTeachingDesignVersion(Base):
    __tablename__ = "class_teaching_design_versions"
    __table_args__ = (
        Index("idx_teaching_design_class_active", "class_id", "is_active", "created_at"),
        Index("idx_teaching_design_class_version", "class_id", "version_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    derived_from_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("class_teaching_design_versions.id"),
        nullable=True,
    )
    version_name = Column(String(64), nullable=True)
    title = Column(String(255), nullable=True)
    source_type = Column(String(32), nullable=False, default="manual", server_default="manual")
    source_filename = Column(String(255), nullable=True)
    source_file_type = Column(String(64), nullable=True)
    source_file_size = Column(Integer, nullable=True)
    raw_text = Column(Text, nullable=True)
    extracted_payload = Column(JSON, nullable=True)
    extraction_status = Column(String(32), nullable=False, default="partial", server_default="partial")
    correction_notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    activated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
    )

    class_: Mapped["Class"] = relationship("Class", foreign_keys=[class_id])
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    parent_version: Mapped["ClassTeachingDesignVersion"] = relationship(
        "ClassTeachingDesignVersion",
        remote_side=[id],
        foreign_keys=[derived_from_version_id],
    )


class TopicRecommendationRun(Base):
    __tablename__ = "topic_recommendation_runs"
    __table_args__ = (
        Index("idx_topic_recommendation_runs_class_created", "class_id", "created_at"),
        Index("idx_topic_recommendation_runs_design_created", "teaching_design_version_id", "created_at"),
        Index("idx_topic_recommendation_runs_creator_created", "created_by", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_run_id = Column(UUID(as_uuid=True), ForeignKey("topic_recommendation_runs.id"), nullable=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)
    teaching_design_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("class_teaching_design_versions.id"),
        nullable=True,
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    mode = Column(String(32), nullable=False, default="competition", server_default="competition")
    status = Column(String(32), nullable=False, default="ready", server_default="ready")
    teaching_design_status = Column(String(32), nullable=False, default="partial", server_default="partial")
    provider = Column(String(32), nullable=False, default="fallback", server_default="fallback")
    generation_quality = Column(String(32), nullable=False, default="fallback", server_default="fallback")
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    preferred_count = Column(Integer, nullable=False, default=4, server_default="4")
    difficulty_preference = Column(String(16), nullable=True)
    request_payload = Column(JSON, nullable=True)
    context_snapshot = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)

    parent_run: Mapped["TopicRecommendationRun"] = relationship(
        "TopicRecommendationRun",
        remote_side=[id],
    )
    class_: Mapped["Class"] = relationship("Class", foreign_keys=[class_id])
    teaching_design_version: Mapped["ClassTeachingDesignVersion"] = relationship(
        "ClassTeachingDesignVersion",
        foreign_keys=[teaching_design_version_id],
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    items: Mapped[List["TopicRecommendationItem"]] = relationship(
        "TopicRecommendationItem",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class TopicRecommendationItem(Base):
    __tablename__ = "topic_recommendation_items"
    __table_args__ = (
        Index("idx_topic_recommendation_items_run_order", "run_id", "candidate_order"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("topic_recommendation_runs.id"), nullable=False)
    candidate_order = Column(Integer, nullable=False, default=1, server_default="1")
    topic_text = Column(Text, nullable=False)
    course_objectives = Column(JSON, nullable=True)
    knowledge_points = Column(JSON, nullable=True)
    classroom_scene = Column(String(255), nullable=True)
    debatability_reason = Column(Text, nullable=True)
    difficulty_level = Column(String(16), nullable=True)
    recommendation_reason = Column(Text, nullable=True)
    source_basis = Column(JSON, nullable=True)
    quality_score = Column(Float, nullable=True)
    quality_flags = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)

    run: Mapped["TopicRecommendationRun"] = relationship(
        "TopicRecommendationRun",
        back_populates="items",
    )
