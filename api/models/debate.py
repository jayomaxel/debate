"""
辩论模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text, func, text
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
    from .class_model import Class

class Debate(Base):
    __tablename__ = "debates"
    __table_args__ = (
        Index("idx_debates_mode_status_created_at", "mode", "status", "created_at"),
        Index("idx_debates_lobby_visibility", "mode", "visibility", "status"),
        Index("idx_debates_reservation_time", "mode", "reservation_status", "scheduled_start_time"),
        Index("idx_debates_teacher_reserved", "teacher_id", "mode", "scheduled_start_time"),
        Index("idx_debates_creator", "creator_user_id", "created_at"),
        Index("idx_debates_host", "host_user_id"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    duration = Column(Integer, nullable=False)  # 分钟
    invitation_code = Column(String(6), unique=True, nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey('classes.id'), nullable=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    status = Column(
        Enum('draft', 'published', 'in_progress', 'completed', name='debate_status_enum'),
        default='draft'
    )
    mode = Column(
        Enum('teacher_assigned', 'student_lobby', 'teacher_reserved', name='debate_mode_enum'),
        nullable=False,
        default='teacher_assigned',
        server_default='teacher_assigned'
    )
    room_name = Column(String(100), nullable=True)
    visibility = Column(
        Enum('public', 'private', name='debate_visibility_enum'),
        nullable=False,
        default='private',
        server_default='private'
    )
    join_password_hash = Column(String(255), nullable=True)
    password_updated_at = Column(DateTime, nullable=True)
    capacity = Column(Integer, nullable=False, default=4, server_default='4')
    creator_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    host_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    scheduled_start_time = Column(DateTime, nullable=True)
    checkin_open_time = Column(DateTime, nullable=True)
    checkin_close_time = Column(DateTime, nullable=True)
    allow_spectators = Column(Boolean, nullable=False, default=False, server_default='false')
    reservation_status = Column(
        Enum(
            'draft',
            'scheduled',
            'checkin_open',
            'waiting',
            'in_progress',
            'completed',
            'cancelled',
            name='debate_reservation_status_enum'
        ),
        nullable=True
    )
    reservation_published_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancel_reason = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    report = Column(JSON, nullable=True)  # 全局评分报告
    created_at = Column(DateTime, default=datetime.utcnow)

    report_pdf = Column(Text, nullable=True) # pdf报告文件路径
    
    # 关系
    class_: Mapped["Class"] = relationship("Class", back_populates="debates")
    teacher: Mapped["User"] = relationship("User", foreign_keys=[teacher_id])
    creator: Mapped["User"] = relationship("User", foreign_keys=[creator_user_id])
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_user_id])
    host: Mapped["User"] = relationship("User", foreign_keys=[host_user_id])
    participations: Mapped[List["DebateParticipation"]] = relationship(
        "DebateParticipation",
        back_populates="debate"
    )
    reservation_invitations: Mapped[List["DebateReservationInvitation"]] = relationship(
        "DebateReservationInvitation",
        back_populates="debate"
    )
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="debate")
    speeches: Mapped[List["Speech"]] = relationship("Speech", back_populates="debate")
    event_logs: Mapped[List["DebateEventLog"]] = relationship(
        "DebateEventLog",
        back_populates="debate",
    )
    role_assignment_runs: Mapped[List["DebateRoleAssignmentRun"]] = relationship(
        "DebateRoleAssignmentRun",
        back_populates="debate",
        foreign_keys="DebateRoleAssignmentRun.debate_id",
    )
    reservation_assignment_runs: Mapped[List["DebateRoleAssignmentRun"]] = relationship(
        "DebateRoleAssignmentRun",
        back_populates="reservation_debate",
        foreign_keys="DebateRoleAssignmentRun.reservation_id",
    )
    role_performance_samples: Mapped[List["DebateRolePerformanceSample"]] = relationship(
        "DebateRolePerformanceSample",
        back_populates="debate",
    )
    
    def __repr__(self):
        return f"<Debate(id={self.id}, topic={self.topic[:30]}, status={self.status})>"


class DebateEventLog(Base):
    __tablename__ = "debate_event_logs"
    __table_args__ = (
        Index("idx_debate_event_logs_debate_created", "debate_id", "created_at"),
        Index("idx_debate_event_logs_room_created", "room_id", "created_at"),
        Index("idx_debate_event_logs_type_state", "event_type", "match_state"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id = Column(UUID(as_uuid=True), ForeignKey("debates.id"), nullable=False)
    room_id = Column(String(64), nullable=False)
    event_type = Column(String(32), nullable=False)
    match_state = Column(String(32), nullable=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_role = Column(String(32), nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    debate: Mapped["Debate"] = relationship("Debate", back_populates="event_logs")
    actor: Mapped["User"] = relationship("User", foreign_keys=[actor_user_id])


class DebateParticipation(Base):
    __tablename__ = "debate_participations"
    __table_args__ = (
        Index("idx_participations_debate_active", "debate_id", "left_at"),
        Index("idx_participations_user", "user_id", "joined_at"),
        Index("idx_participations_moderator", "debate_id", "is_moderator"),
        Index("idx_participations_seat", "debate_id", "seat_order"),
        Index(
            "uniq_participation_active_user",
            "debate_id",
            "user_id",
            unique=True,
            postgresql_where=text("left_at IS NULL"),
            sqlite_where=text("left_at IS NULL"),
        ),
        Index(
            "uniq_participation_active_seat",
            "debate_id",
            "seat_order",
            unique=True,
            postgresql_where=text("left_at IS NULL AND seat_order IS NOT NULL"),
            sqlite_where=text("left_at IS NULL AND seat_order IS NOT NULL"),
        ),
        Index(
            "uniq_participation_active_role",
            "debate_id",
            "stance",
            "role",
            unique=True,
            postgresql_where=text("left_at IS NULL"),
            sqlite_where=text("left_at IS NULL"),
        ),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id = Column(UUID(as_uuid=True), ForeignKey('debates.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    role = Column(
        Enum('debater_1', 'debater_2', 'debater_3', 'debater_4', name='debater_role_enum'),
        nullable=False
    )
    stance = Column(Enum('positive', 'negative', name='stance_enum'), nullable=False)
    role_reason = Column(String(32), nullable=True)
    is_moderator = Column(Boolean, nullable=False, default=False, server_default='false')
    is_room_owner = Column(Boolean, nullable=False, default=False, server_default='false')
    invitation_id = Column(UUID(as_uuid=True), ForeignKey('debate_reservation_invitations.id'), nullable=True)
    invited_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    attendance_status = Column(
        Enum('not_checked_in', 'checked_in', 'absent', name='debate_attendance_status_enum'),
        nullable=True
    )
    checked_in_at = Column(DateTime, nullable=True)
    seat_order = Column(Integer, nullable=True)
    left_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    debate: Mapped["Debate"] = relationship("Debate", back_populates="participations")
    user: Mapped["User"] = relationship(
        "User",
        back_populates="debate_participations",
        foreign_keys=[user_id]
    )
    inviter: Mapped["User"] = relationship("User", foreign_keys=[invited_by])
    invitation: Mapped["DebateReservationInvitation"] = relationship(
        "DebateReservationInvitation",
        back_populates="participation"
    )
    scores: Mapped[List["Score"]] = relationship("Score", back_populates="participation")
    
    def __repr__(self):
        return f"<DebateParticipation(debate_id={self.debate_id}, user_id={self.user_id}, role={self.role})>"


class DebateReservationInvitation(Base):
    __tablename__ = "debate_reservation_invitations"
    __table_args__ = (
        Index(
            "idx_invitation_student_status",
            "student_id",
            "response_status",
            "attendance_status",
        ),
        Index("idx_invitation_debate_attendance", "debate_id", "attendance_status"),
        Index("idx_invitation_teacher_created", "invited_by_teacher_id", "created_at"),
        Index("idx_invitation_expires", "expires_at", "response_status"),
        Index("idx_invitation_debate_revoked", "debate_id", "revoked_at"),
        Index(
            "uniq_active_invitation_debate_student",
            "debate_id",
            "student_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id = Column(UUID(as_uuid=True), ForeignKey('debates.id'), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    invited_by_teacher_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    assigned_role = Column(
        Enum('debater_1', 'debater_2', 'debater_3', 'debater_4', name='debater_role_enum'),
        nullable=True
    )
    assigned_stance = Column(Enum('positive', 'negative', name='stance_enum'), nullable=True)
    is_designated_moderator = Column(Boolean, nullable=False, default=False, server_default='false')
    is_backup_moderator = Column(Boolean, nullable=False, default=False, server_default='false')
    read_status = Column(
        Enum('unread', 'read', name='reservation_invitation_read_status_enum'),
        nullable=False,
        default='unread',
        server_default='unread'
    )
    response_status = Column(
        Enum('pending', 'accepted', 'rejected', 'expired', name='reservation_invitation_response_status_enum'),
        nullable=False,
        default='pending',
        server_default='pending'
    )
    attendance_status = Column(
        Enum('not_checked_in', 'checked_in', 'absent', name='debate_attendance_status_enum'),
        nullable=False,
        default='not_checked_in',
        server_default='not_checked_in'
    )
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by_teacher_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    revoke_reason = Column(Text, nullable=True)
    read_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    checked_in_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
    )

    debate: Mapped["Debate"] = relationship("Debate", back_populates="reservation_invitations")
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    invited_by_teacher: Mapped["User"] = relationship("User", foreign_keys=[invited_by_teacher_id])
    revoked_by_teacher: Mapped["User"] = relationship("User", foreign_keys=[revoked_by_teacher_id])
    participation: Mapped["DebateParticipation"] = relationship(
        "DebateParticipation",
        back_populates="invitation",
        uselist=False
    )

    def __repr__(self):
        return (
            "<DebateReservationInvitation("
            f"debate_id={self.debate_id}, student_id={self.student_id}, "
            f"response_status={self.response_status})>"
        )


class DebateRoleAssignmentRun(Base):
    __tablename__ = "debate_role_assignment_runs"
    __table_args__ = (
        Index("idx_role_assignment_runs_debate_created", "debate_id", "created_at"),
        Index("idx_role_assignment_runs_reservation_created", "reservation_id", "created_at"),
        Index("idx_role_assignment_runs_class_source_created", "class_id", "source", "created_at"),
        Index("idx_role_assignment_runs_created_by", "created_by", "created_at"),
        Index("idx_role_assignment_runs_preview", "preview_token"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_run_id = Column(UUID(as_uuid=True), ForeignKey("debate_role_assignment_runs.id"), nullable=True)
    debate_id = Column(UUID(as_uuid=True), ForeignKey("debates.id"), nullable=True)
    reservation_id = Column(UUID(as_uuid=True), ForeignKey("debates.id"), nullable=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=True)
    source = Column(String(32), nullable=False)
    target_mode = Column(String(32), nullable=True)
    assignment_mode = Column(String(32), nullable=False)
    rotation_policy = Column(String(32), nullable=True)
    model_version = Column(String(64), nullable=True)
    prompt_pack_version = Column(String(64), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    preview_token = Column(String(64), nullable=True)
    is_temporary = Column(Boolean, nullable=False, default=False, server_default="false")
    summary = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)

    parent_run: Mapped["DebateRoleAssignmentRun"] = relationship(
        "DebateRoleAssignmentRun",
        remote_side=[id],
    )
    debate: Mapped["Debate"] = relationship(
        "Debate",
        back_populates="role_assignment_runs",
        foreign_keys=[debate_id],
    )
    reservation_debate: Mapped["Debate"] = relationship(
        "Debate",
        back_populates="reservation_assignment_runs",
        foreign_keys=[reservation_id],
    )
    class_: Mapped["Class"] = relationship("Class", foreign_keys=[class_id])
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    items: Mapped[List["DebateRoleAssignmentItem"]] = relationship(
        "DebateRoleAssignmentItem",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[List["DebateRoleAssignmentAuditLog"]] = relationship(
        "DebateRoleAssignmentAuditLog",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    performance_samples: Mapped[List["DebateRolePerformanceSample"]] = relationship(
        "DebateRolePerformanceSample",
        back_populates="assignment_run",
    )


class DebateRoleAssignmentItem(Base):
    __tablename__ = "debate_role_assignment_items"
    __table_args__ = (
        Index("idx_role_assignment_items_run_user", "run_id", "user_id"),
        Index("idx_role_assignment_items_run_final_role", "run_id", "final_role"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("debate_role_assignment_runs.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assignment_source = Column(String(32), nullable=True)
    recommended_role = Column(String(32), nullable=True)
    assigned_role = Column(String(32), nullable=True)
    final_role = Column(String(32), nullable=True)
    teacher_override = Column(Boolean, nullable=False, default=False, server_default="false")
    override_reason = Column(Text, nullable=True)
    fit_score = Column(Float, nullable=True)
    rule_fit_score = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)
    fairness_penalty = Column(Float, nullable=True)
    repeat_penalty = Column(Float, nullable=True)
    imbalance_penalty = Column(Float, nullable=True)
    growth_bonus = Column(Float, nullable=True)
    model_score = Column(Float, nullable=True)
    growth_score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    dimension_contribution = Column(JSON, nullable=True)
    feature_importance = Column(JSON, nullable=True)
    model_basis = Column(JSON, nullable=True)
    analysis_basis = Column(String(64), nullable=True)
    data_sources = Column(JSON, nullable=True)
    standard_profile = Column(JSON, nullable=True)
    historical_role_distribution = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)

    run: Mapped["DebateRoleAssignmentRun"] = relationship(
        "DebateRoleAssignmentRun",
        back_populates="items",
    )
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    performance_samples: Mapped[List["DebateRolePerformanceSample"]] = relationship(
        "DebateRolePerformanceSample",
        back_populates="assignment_item",
    )


class DebateRoleAssignmentAuditLog(Base):
    __tablename__ = "debate_role_assignment_audit_logs"
    __table_args__ = (
        Index("idx_role_assignment_audit_run_created", "run_id", "created_at"),
        Index("idx_role_assignment_audit_debate_created", "debate_id", "created_at"),
        Index("idx_role_assignment_audit_reservation_created", "reservation_id", "created_at"),
        Index("idx_role_assignment_audit_user_created", "user_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("debate_role_assignment_runs.id"), nullable=True)
    debate_id = Column(UUID(as_uuid=True), ForeignKey("debates.id"), nullable=True)
    reservation_id = Column(UUID(as_uuid=True), ForeignKey("debates.id"), nullable=True)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    from_role = Column(String(32), nullable=True)
    to_role = Column(String(32), nullable=True)
    reason = Column(Text, nullable=True)
    action_type = Column(String(32), nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)

    run: Mapped["DebateRoleAssignmentRun"] = relationship(
        "DebateRoleAssignmentRun",
        back_populates="audit_logs",
    )
    debate: Mapped["Debate"] = relationship("Debate", foreign_keys=[debate_id])
    reservation_debate: Mapped["Debate"] = relationship("Debate", foreign_keys=[reservation_id])
    operator: Mapped["User"] = relationship("User", foreign_keys=[operator_id])
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class DebateRolePerformanceSample(Base):
    __tablename__ = "debate_role_performance_samples"
    __table_args__ = (
        Index("idx_role_performance_samples_debate_user", "debate_id", "user_id"),
        Index("idx_role_performance_samples_role_created", "role", "created_at"),
        Index("idx_role_performance_samples_user_role", "user_id", "role"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id = Column(UUID(as_uuid=True), ForeignKey("debates.id"), nullable=False)
    participation_id = Column(UUID(as_uuid=True), ForeignKey("debate_participations.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=True)
    assignment_run_id = Column(UUID(as_uuid=True), ForeignKey("debate_role_assignment_runs.id"), nullable=True)
    assignment_item_id = Column(UUID(as_uuid=True), ForeignKey("debate_role_assignment_items.id"), nullable=True)
    sample_source = Column(String(32), nullable=False, default="completed_debate", server_default="completed_debate")
    role = Column(String(32), nullable=False)
    stance = Column(String(16), nullable=True)
    assignment_mode = Column(String(32), nullable=True)
    rotation_policy = Column(String(32), nullable=True)
    rule_fit_score = Column(Float, nullable=True)
    model_score = Column(Float, nullable=True)
    growth_score = Column(Float, nullable=True)
    final_assignment_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    logic_score = Column(Float, nullable=True)
    argument_score = Column(Float, nullable=True)
    response_score = Column(Float, nullable=True)
    persuasion_score = Column(Float, nullable=True)
    teamwork_score = Column(Float, nullable=True)
    speech_count = Column(Integer, nullable=True)
    total_duration_sec = Column(Integer, nullable=True)
    average_speech_length = Column(Float, nullable=True)
    response_success_rate = Column(Float, nullable=True)
    active_rounds = Column(Integer, nullable=True)
    obvious_mistake_count = Column(Integer, nullable=True)
    teacher_feedback = Column(Text, nullable=True)
    student_reflection = Column(Text, nullable=True)
    mentor_feedback = Column(Text, nullable=True)
    report_summary = Column(Text, nullable=True)
    standard_profile = Column(JSON, nullable=True)
    historical_role_distribution = Column(JSON, nullable=True)
    feature_vector = Column(JSON, nullable=True)
    label_vector = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)

    debate: Mapped["Debate"] = relationship("Debate", back_populates="role_performance_samples")
    participation: Mapped["DebateParticipation"] = relationship("DebateParticipation", foreign_keys=[participation_id])
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    class_: Mapped["Class"] = relationship("Class", foreign_keys=[class_id])
    assignment_run: Mapped["DebateRoleAssignmentRun"] = relationship(
        "DebateRoleAssignmentRun",
        back_populates="performance_samples",
    )
    assignment_item: Mapped["DebateRoleAssignmentItem"] = relationship(
        "DebateRoleAssignmentItem",
        back_populates="performance_samples",
    )
