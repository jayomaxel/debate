import uuid
from datetime import datetime, timedelta

import pytest

from models.class_model import Class
from models.debate import DebateParticipation, DebateReservationInvitation
from models.user import User
from services.debate_service import DebateService
from services.room_manager import DebateRoomManager


def _user(account: str, name: str, user_type: str, class_id=None) -> User:
    return User(
        id=uuid.uuid4(),
        account=account,
        name=name,
        email=f"{account}@test.com",
        password_hash="hashed",
        user_type=user_type,
        class_id=class_id,
        created_at=datetime.utcnow(),
    )


def _teacher_class_and_students(db_session, student_count: int = 2):
    teacher = _user(f"teacher_{uuid.uuid4().hex[:8]}", "Teacher", "teacher")
    db_session.add(teacher)
    db_session.flush()
    cls = Class(
        id=uuid.uuid4(),
        name="Consistency Class",
        code=f"C{uuid.uuid4().hex[:8]}",
        teacher_id=teacher.id,
    )
    db_session.add(cls)
    db_session.flush()
    students = []
    for index in range(student_count):
        student = _user(f"student_{uuid.uuid4().hex[:8]}_{index}", f"Student {index}", "student", cls.id)
        db_session.add(student)
        students.append(student)
    db_session.commit()
    return teacher, cls, students


def test_create_lobby_room_writes_database_fields(db_session):
    _, _, students = _teacher_class_and_students(db_session, 1)
    student = students[0]

    room = DebateService.create_lobby_room(
        db=db_session,
        student_id=str(student.id),
        room_name="自发房间",
        topic="是否应该开放课堂辩论",
        capacity=3,
        visibility="private",
        password="secret123",
    )

    participation = db_session.query(DebateParticipation).filter(
        DebateParticipation.debate_id == uuid.UUID(room["room_id"]),
        DebateParticipation.user_id == student.id,
        DebateParticipation.left_at.is_(None),
    ).one()
    assert room["mode"] == "student_lobby"
    assert room["visibility"] == "private"
    assert room["has_password"] is True
    assert participation.is_moderator is True
    assert participation.is_room_owner is True
    assert participation.seat_order == 1


@pytest.mark.asyncio
async def test_reservation_uses_invitation_table_and_checkin_creates_participation(db_session):
    teacher, cls, students = _teacher_class_and_students(db_session, 2)
    scheduled = datetime.utcnow() + timedelta(hours=1)

    reservation = await DebateService.create_reservation(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic="预约制辩论事实源测试",
        duration=30,
        scheduled_start_time=scheduled,
        checkin_open_time=datetime.utcnow() - timedelta(minutes=1),
        checkin_close_time=datetime.utcnow() + timedelta(minutes=30),
        student_ids=[str(student.id) for student in students],
        host_user_id=str(students[0].id),
    )

    debate_id = uuid.UUID(reservation["reservation_id"])
    invitations = db_session.query(DebateReservationInvitation).filter(
        DebateReservationInvitation.debate_id == debate_id,
        DebateReservationInvitation.revoked_at.is_(None),
    ).all()
    assert len(invitations) == 2
    assert db_session.query(DebateParticipation).filter(
        DebateParticipation.debate_id == debate_id,
        DebateParticipation.left_at.is_(None),
    ).count() == 0

    accepted = DebateService.respond_reservation_invitation(
        db=db_session,
        student_id=str(students[0].id),
        reservation_id=str(debate_id),
        action="accept",
    )
    assert accepted["invitation_status"] == "accepted"

    checked_in = DebateService.check_in_reservation(
        db=db_session,
        student_id=str(students[0].id),
        reservation_id=str(debate_id),
    )
    participation = db_session.query(DebateParticipation).filter(
        DebateParticipation.debate_id == debate_id,
        DebateParticipation.user_id == students[0].id,
        DebateParticipation.left_at.is_(None),
    ).one()
    assert checked_in["checked_in"] is True
    assert participation.invitation_id is not None
    assert participation.attendance_status == "checked_in"
    assert participation.is_moderator is True


@pytest.mark.asyncio
async def test_websocket_reservation_guard_requires_checkin(db_session):
    teacher, cls, students = _teacher_class_and_students(db_session, 1)
    scheduled = datetime.utcnow() + timedelta(hours=1)
    reservation = await DebateService.create_reservation(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic="WebSocket 入场校验",
        duration=30,
        scheduled_start_time=scheduled,
        checkin_open_time=datetime.utcnow() - timedelta(minutes=1),
        checkin_close_time=datetime.utcnow() + timedelta(minutes=30),
        student_ids=[str(students[0].id)],
    )
    room_id = reservation["room_id"]
    manager = DebateRoomManager()
    await manager.create_room(room_id, room_id, db_session)

    assert await manager.join_room(room_id, str(students[0].id), db_session) is False

    DebateService.respond_reservation_invitation(
        db=db_session,
        student_id=str(students[0].id),
        reservation_id=room_id,
        action="accept",
    )
    assert await manager.join_room(room_id, str(students[0].id), db_session) is False

    DebateService.check_in_reservation(
        db=db_session,
        student_id=str(students[0].id),
        reservation_id=room_id,
    )
    assert await manager.join_room(room_id, str(students[0].id), db_session) is True
