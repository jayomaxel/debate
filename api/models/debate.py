"""
辩论模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, func, text
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
