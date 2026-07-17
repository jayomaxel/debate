"""Idempotently create data for a complete teacher/student product walkthrough."""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import datetime, timedelta

import database
from models.assessment import AbilityAssessment
from models.class_model import Class
from models.debate import Debate, DebateParticipation, DebateReservationInvitation
from models.teaching_design import ClassTeachingDesignVersion
from models.user import User
from seed_fake_debate_report import seed_fake_bundle
from services.class_service import ClassService
from utils.security import hash_password


PASSWORD = "FlowTest@2026"
CLASS_NAME = "完整流程测试班"
TOPICS = {
    "draft": "生成式 AI 是否应该成为所有课程的基础工具？",
    "published": "课堂使用 AI 会增强还是削弱学生的独立思考？",
    "completed": "人类是否应该与高度拟人化的 AI 伴侣建立真实情感羁绊？",
    "reservation": "AI 教师能否在未来承担主要教学职责？",
    "lobby": "学校是否应该允许学生使用 AI 完成开放式作业？",
}
STUDENTS = (
    ("flow_student1", "流程学生一", "ENTJ", "debater_1"),
    ("flow_student2", "流程学生二", "INTP", "debater_2"),
    ("flow_student3", "流程学生三", "ENFP", "debater_3"),
    ("flow_student4", "流程学生四", "ISTJ", "debater_4"),
)


def ensure_teacher(db, requested: str) -> tuple[User, bool]:
    teacher = db.query(User).filter(User.account == requested, User.user_type == "teacher").first()
    if teacher:
        return teacher, False
    teacher = db.query(User).filter(User.account == "flow_teacher").first()
    if not teacher:
        teacher = User(
            id=uuid.uuid4(), account="flow_teacher", password_hash=hash_password(PASSWORD),
            user_type="teacher", name="完整流程测试教师",
            email="flow.teacher@example.com", phone="13800002026",
        )
        db.add(teacher)
    else:
        teacher.password_hash = hash_password(PASSWORD)
    db.commit()
    return teacher, True


def ensure_class(db, teacher: User) -> Class:
    item = db.query(Class).filter(Class.teacher_id == teacher.id, Class.name == CLASS_NAME).first()
    if item:
        return item
    code = "FLOW26"
    if db.query(Class).filter(Class.code == code).first():
        code = ClassService.generate_class_code()
    item = Class(id=uuid.uuid4(), name=CLASS_NAME, code=code, teacher_id=teacher.id)
    db.add(item)
    db.commit()
    return item


def ensure_students(db, class_obj: Class) -> list[User]:
    result = []
    for index, (account, name, personality, role) in enumerate(STUDENTS, 1):
        student = db.query(User).filter(User.account == account).first()
        if not student:
            student = User(
                id=uuid.uuid4(), account=account, user_type="student", name=name,
                email=f"{account}@example.com", student_id=f"FLOW-2026-{index:03d}",
                password_hash=hash_password(PASSWORD), class_id=class_obj.id,
            )
            db.add(student)
            db.flush()
        student.password_hash = hash_password(PASSWORD)
        student.class_id = class_obj.id
        assessment = (
            db.query(AbilityAssessment)
            .filter(AbilityAssessment.user_id == student.id)
            .order_by(AbilityAssessment.created_at.desc()).first()
        )
        if not assessment:
            assessment = AbilityAssessment(id=uuid.uuid4(), user_id=student.id)
            db.add(assessment)
        assessment.personality_type = personality
        assessment.expression_willingness = 70 + index * 5
        assessment.logical_thinking = 92 - index * 4
        assessment.expression_willingness_score = 70 + index * 5
        assessment.logical_thinking_score = 92 - index * 4
        assessment.stablecoin_knowledge_score = 72 + index * 4
        assessment.financial_knowledge_score = 70 + index * 4
        assessment.critical_thinking_score = 88 - index * 2
        assessment.is_default = False
        assessment.recommended_role = role
        result.append(student)
    db.commit()
    return result


def ensure_design(db, class_obj: Class, teacher: User) -> None:
    design = db.query(ClassTeachingDesignVersion).filter(
        ClassTeachingDesignVersion.class_id == class_obj.id,
        ClassTeachingDesignVersion.version_name == "流程测试教学设计 v1",
    ).first()
    if not design:
        design = ClassTeachingDesignVersion(
            id=uuid.uuid4(), class_id=class_obj.id, created_by=teacher.id,
            version_name="流程测试教学设计 v1", source_type="manual",
        )
        db.add(design)
    design.title = "人工智能伦理与批判性思维单元"
    design.raw_text = "围绕 AI 伦理、技术边界和人机关系开展议题式教学。"
    design.extraction_status = "ready"
    design.extracted_payload = {
        "chapter_focus": "人工智能伦理与社会影响",
        "training_objectives": ["论证结构", "证据评价", "伦理判断", "团队协作"],
        "classroom_scenarios": ["辩论赛", "案例研讨", "角色扮演"],
        "knowledge_points": ["AI 伦理", "算法偏见", "人机关系", "数据隐私"],
    }
    design.is_active = True
    design.activated_at = datetime.utcnow()
    db.commit()


def code_for(db, preferred: str) -> str:
    return preferred if not db.query(Debate).filter(Debate.invitation_code == preferred).first() else ClassService.generate_class_code()


def ensure_debate(db, teacher: User, class_obj: Class, key: str, status: str, mode="teacher_assigned") -> Debate:
    debate = db.query(Debate).filter(Debate.teacher_id == teacher.id, Debate.topic == TOPICS[key]).first()
    if not debate:
        debate = Debate(
            id=uuid.uuid4(), topic=TOPICS[key], duration=35,
            invitation_code=code_for(db, f"FLOW{list(TOPICS).index(key) + 1:02d}"),
            class_id=class_obj.id, teacher_id=teacher.id,
        )
        db.add(debate)
    debate.description = "完整流程测试数据，可用于教师端和学生端联调。"
    debate.class_id = class_obj.id
    debate.teacher_id = teacher.id
    debate.creator_user_id = teacher.id
    debate.owner_user_id = teacher.id
    debate.host_user_id = teacher.id
    debate.status = status
    debate.mode = mode
    debate.visibility = "public" if mode == "student_lobby" else "private"
    debate.capacity = 4
    db.flush()
    return debate


def ensure_participants(db, debate: Debate, students: list[User]) -> None:
    roles = ("debater_1", "debater_2", "debater_3", "debater_4")
    stances = ("positive", "negative", "positive", "negative")
    for seat, (student, role, stance) in enumerate(zip(students, roles, stances), 1):
        row = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id,
            DebateParticipation.user_id == student.id,
            DebateParticipation.left_at.is_(None),
        ).first()
        if not row:
            row = DebateParticipation(id=uuid.uuid4(), debate_id=debate.id, user_id=student.id)
            db.add(row)
        row.role, row.stance, row.seat_order = role, stance, seat
        row.role_reason = "full_flow_demo"
        row.attendance_status = "not_checked_in"
        row.invited_by = debate.teacher_id


def ensure_reservation(db, teacher: User, class_obj: Class, students: list[User]) -> Debate:
    debate = ensure_debate(db, teacher, class_obj, "reservation", "published", "teacher_reserved")
    scheduled = datetime.utcnow() + timedelta(days=1)
    debate.room_name = "完整流程预约辩论室"
    debate.reservation_status = "scheduled"
    debate.scheduled_start_time = scheduled
    debate.checkin_open_time = scheduled - timedelta(minutes=15)
    debate.checkin_close_time = scheduled + timedelta(minutes=5)
    debate.reservation_published_at = datetime.utcnow()
    debate.allow_spectators = True
    for index, student in enumerate(students, 1):
        invitation = db.query(DebateReservationInvitation).filter(
            DebateReservationInvitation.debate_id == debate.id,
            DebateReservationInvitation.student_id == student.id,
            DebateReservationInvitation.revoked_at.is_(None),
        ).first()
        if not invitation:
            invitation = DebateReservationInvitation(
                id=uuid.uuid4(), debate_id=debate.id, student_id=student.id,
                invited_by_teacher_id=teacher.id,
            )
            db.add(invitation)
        invitation.assigned_role = f"debater_{index}"
        invitation.assigned_stance = "positive" if index % 2 else "negative"
        invitation.read_status = "unread"
        invitation.response_status = "pending"
        invitation.attendance_status = "not_checked_in"
        invitation.expires_at = scheduled
    return debate


def run_seed(db, teacher_account: str) -> dict:
    teacher, fallback = ensure_teacher(db, teacher_account)
    class_obj = ensure_class(db, teacher)
    students = ensure_students(db, class_obj)
    ensure_design(db, class_obj, teacher)
    draft = ensure_debate(db, teacher, class_obj, "draft", "draft")
    published = ensure_debate(db, teacher, class_obj, "published", "published")
    ensure_participants(db, published, students)
    reservation = ensure_reservation(db, teacher, class_obj, students)
    lobby = ensure_debate(db, teacher, class_obj, "lobby", "published", "student_lobby")
    lobby.creator_user_id = lobby.owner_user_id = lobby.host_user_id = students[0].id
    lobby.room_name = "学生公开练习房"
    completed = ensure_debate(db, teacher, class_obj, "completed", "completed")
    db.commit()
    completed = seed_fake_bundle(
        session=db, class_obj=class_obj, teacher=teacher, selected_students=students,
        topic=TOPICS["completed"], duration_minutes=35,
        rng=random.Random(20260717), debate_id=str(completed.id),
    )["debate"]
    return {
        "teacher": teacher, "fallback": fallback, "class": class_obj,
        "students": students, "debates": (draft, published, completed, reservation, lobby),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-account", default="000000")
    args = parser.parse_args()
    database.init_engine()
    database.init_db()
    db = database.SessionLocal()
    try:
        result = run_seed(db, args.teacher_account)
        teacher, class_obj = result["teacher"], result["class"]
        print("Full-flow demo data is ready.")
        print(f"teacher_account={teacher.account}")
        print(f"teacher_password={PASSWORD}" if result["fallback"] else "teacher_password=<existing password unchanged>")
        print(f"class_name={class_obj.name}")
        print(f"class_code={class_obj.code}")
        print(f"student_password={PASSWORD}")
        for student in result["students"]:
            print(f"student={student.account} | {student.name}")
        for debate in result["debates"]:
            print(f"debate={debate.status} | {debate.mode} | {debate.invitation_code} | {debate.topic}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
