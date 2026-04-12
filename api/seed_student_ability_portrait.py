from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import database
from models.assessment import AbilityAssessment
from models.class_model import Class
from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from models.user import User
from services.assessment_service import AssessmentService
from services.class_service import ClassService
from utils.security import hash_password
from utils.user_email import build_placeholder_email


STUDENT_NAME = "李子子子子子子子子涵"
STUDENT_ACCOUNT = "lizizihan_profile"
STUDENT_PASSWORD = "Test123!"
STUDENT_ID = "LZZH-2026-001"

TEACHER_NAME = "画像测试教师"
TEACHER_ACCOUNT = "portrait_teacher_li"
TEACHER_PASSWORD = "Test123!"
TEACHER_EMAIL = "portrait.teacher.li@example.com"
TEACHER_PHONE = "13800006666"

CLASS_NAME = "画像测试班"
CLASS_CODE = "LZZH01"

FAKE_DEBATES = [
    {
        "topic": "AI 是否应该参与课堂评价",
        "days_ago": 9,
        "role": "debater_1",
        "stance": "positive",
        "speech_phase": "opening",
        "speech_content": "我方认为 AI 可以参与课堂评价，但必须以教师主导、人机协同和过程可解释为前提。",
        "speech_duration": 96,
        "scores": {
            "logic_score": 78.0,
            "argument_score": 80.0,
            "response_score": 74.0,
            "persuasion_score": 76.0,
            "teamwork_score": 82.0,
            "overall_score": 78.0,
        },
    },
    {
        "topic": "生成式 AI 会削弱学生独立思考吗",
        "days_ago": 6,
        "role": "debater_2",
        "stance": "positive",
        "speech_phase": "questioning",
        "speech_content": "我方认为问题不在于工具本身，而在于教学设计是否把 AI 变成了替代思考还是激发思考的支架。",
        "speech_duration": 88,
        "scores": {
            "logic_score": 84.0,
            "argument_score": 86.0,
            "response_score": 82.0,
            "persuasion_score": 83.0,
            "teamwork_score": 85.0,
            "overall_score": 84.0,
        },
    },
    {
        "topic": "中学生是否应该系统学习 AI 伦理",
        "days_ago": 3,
        "role": "debater_4",
        "stance": "positive",
        "speech_phase": "closing",
        "speech_content": "总结来看，AI 伦理教育不是额外负担，而是学生在智能时代进行判断、选择与负责的基础能力。",
        "speech_duration": 102,
        "scores": {
            "logic_score": 88.0,
            "argument_score": 90.0,
            "response_score": 87.0,
            "persuasion_score": 89.0,
            "teamwork_score": 91.0,
            "overall_score": 89.0,
        },
    },
]

ASSESSMENT_SCORES = {
    "personality_type": "ENTJ",
    "expression_willingness": 86,
    "logical_thinking": 92,
    "stablecoin_knowledge": 83,
    "financial_knowledge": 88,
    "critical_thinking": 90,
}


def ensure_teacher(session) -> User:
    teacher = session.query(User).filter(User.account == TEACHER_ACCOUNT).first()
    if teacher is None:
        teacher = User(
            id=uuid.uuid4(),
            account=TEACHER_ACCOUNT,
            password_hash=hash_password(TEACHER_PASSWORD),
            user_type="teacher",
            name=TEACHER_NAME,
            email=TEACHER_EMAIL,
            phone=TEACHER_PHONE,
        )
        session.add(teacher)
        session.commit()
        session.refresh(teacher)
        return teacher

    teacher.name = TEACHER_NAME
    teacher.email = TEACHER_EMAIL
    teacher.phone = TEACHER_PHONE
    teacher.password_hash = hash_password(TEACHER_PASSWORD)
    session.commit()
    session.refresh(teacher)
    return teacher


def ensure_class(session, teacher: User) -> Class:
    class_obj = (
        session.query(Class)
        .filter(Class.teacher_id == teacher.id, Class.name == CLASS_NAME)
        .first()
    )
    if class_obj is not None:
        return class_obj

    conflict = session.query(Class).filter(Class.code == CLASS_CODE).first()
    class_code = CLASS_CODE if conflict is None else ClassService.generate_class_code()
    class_obj = Class(
        id=uuid.uuid4(),
        name=CLASS_NAME,
        code=class_code,
        teacher_id=teacher.id,
    )
    session.add(class_obj)
    session.commit()
    session.refresh(class_obj)
    return class_obj


def ensure_student(session, class_obj: Class) -> User:
    student = session.query(User).filter(User.account == STUDENT_ACCOUNT).first()
    if student is None:
        student = User(
            id=uuid.uuid4(),
            account=STUDENT_ACCOUNT,
            password_hash=hash_password(STUDENT_PASSWORD),
            user_type="student",
            name=STUDENT_NAME,
            email=build_placeholder_email(STUDENT_ACCOUNT),
            student_id=STUDENT_ID,
            class_id=class_obj.id,
        )
        session.add(student)
        session.commit()
        session.refresh(student)
        return student

    student.name = STUDENT_NAME
    student.student_id = STUDENT_ID
    student.class_id = class_obj.id
    student.password_hash = hash_password(STUDENT_PASSWORD)
    if not student.email:
        student.email = build_placeholder_email(STUDENT_ACCOUNT)
    session.commit()
    session.refresh(student)
    return student


def upsert_assessment(session, student: User) -> AbilityAssessment:
    AssessmentService.submit_assessment(
        db=session,
        user_id=str(student.id),
        personality_type=ASSESSMENT_SCORES["personality_type"],
        expression_willingness=ASSESSMENT_SCORES["expression_willingness"],
        logical_thinking=ASSESSMENT_SCORES["logical_thinking"],
        stablecoin_knowledge=ASSESSMENT_SCORES["stablecoin_knowledge"],
        financial_knowledge=ASSESSMENT_SCORES["financial_knowledge"],
        critical_thinking=ASSESSMENT_SCORES["critical_thinking"],
    )
    assessment = (
        session.query(AbilityAssessment)
        .filter(AbilityAssessment.user_id == student.id)
        .first()
    )
    if assessment is None:
        raise RuntimeError("Failed to create ability assessment.")
    return assessment


def upsert_debate_bundle(session, teacher: User, class_obj: Class, student: User) -> None:
    now = datetime.utcnow()

    for item in FAKE_DEBATES:
        start_time = now - timedelta(days=item["days_ago"], minutes=35)
        end_time = now - timedelta(days=item["days_ago"])
        debate = (
            session.query(Debate)
            .filter(Debate.teacher_id == teacher.id, Debate.topic == item["topic"])
            .first()
        )

        if debate is None:
            invitation_code = ClassService.generate_class_code()
            while session.query(Debate).filter(Debate.invitation_code == invitation_code).first():
                invitation_code = ClassService.generate_class_code()

            debate = Debate(
                id=uuid.uuid4(),
                topic=item["topic"],
                description="学生个人画像测试用辩论数据",
                duration=35,
                invitation_code=invitation_code,
                class_id=class_obj.id,
                teacher_id=teacher.id,
                status="completed",
                start_time=start_time,
                end_time=end_time,
                report={
                    "summary": "用于测试学生个人中心能力画像的假数据",
                    "generated_for": STUDENT_NAME,
                },
            )
            session.add(debate)
            session.commit()
            session.refresh(debate)
        else:
            debate.class_id = class_obj.id
            debate.teacher_id = teacher.id
            debate.status = "completed"
            debate.start_time = start_time
            debate.end_time = end_time
            debate.duration = 35
            debate.description = "学生个人画像测试用辩论数据"
            debate.report = {
                "summary": "用于测试学生个人中心能力画像的假数据",
                "generated_for": STUDENT_NAME,
            }
            session.commit()

        participation = (
            session.query(DebateParticipation)
            .filter(
                DebateParticipation.debate_id == debate.id,
                DebateParticipation.user_id == student.id,
            )
            .first()
        )
        if participation is None:
            participation = DebateParticipation(
                id=uuid.uuid4(),
                debate_id=debate.id,
                user_id=student.id,
                role=item["role"],
                stance=item["stance"],
                role_reason="portrait_seed",
            )
            session.add(participation)
            session.commit()
            session.refresh(participation)
        else:
            participation.role = item["role"]
            participation.stance = item["stance"]
            participation.role_reason = "portrait_seed"
            session.commit()

        speech = (
            session.query(Speech)
            .filter(
                Speech.debate_id == debate.id,
                Speech.speaker_id == student.id,
                Speech.speaker_role == item["role"],
            )
            .first()
        )
        if speech is None:
            speech = Speech(
                id=uuid.uuid4(),
                debate_id=debate.id,
                speaker_id=student.id,
                speaker_type="human",
                speaker_role=item["role"],
                phase=item["speech_phase"],
                content=item["speech_content"],
                duration=item["speech_duration"],
                timestamp=end_time - timedelta(minutes=5),
            )
            session.add(speech)
            session.commit()
            session.refresh(speech)
        else:
            speech.phase = item["speech_phase"]
            speech.content = item["speech_content"]
            speech.duration = item["speech_duration"]
            speech.timestamp = end_time - timedelta(minutes=5)
            session.commit()

        score = (
            session.query(Score)
            .filter(Score.participation_id == participation.id)
            .first()
        )
        if score is None:
            score = Score(
                id=uuid.uuid4(),
                participation_id=participation.id,
                speech_id=speech.id,
                feedback="该学生论点结构清晰，表达稳定，具备较强的课堂辩论潜力。",
                **item["scores"],
            )
            session.add(score)
            session.commit()
        else:
            score.speech_id = speech.id
            score.logic_score = item["scores"]["logic_score"]
            score.argument_score = item["scores"]["argument_score"]
            score.response_score = item["scores"]["response_score"]
            score.persuasion_score = item["scores"]["persuasion_score"]
            score.teamwork_score = item["scores"]["teamwork_score"]
            score.overall_score = item["scores"]["overall_score"]
            score.feedback = "该学生论点结构清晰，表达稳定，具备较强的课堂辩论潜力。"
            session.commit()


def main() -> None:
    database.init_engine()
    database.init_db()
    session = database.SessionLocal()

    try:
        teacher = ensure_teacher(session)
        class_obj = ensure_class(session, teacher)
        student = ensure_student(session, class_obj)
        assessment = upsert_assessment(session, student)
        upsert_debate_bundle(session, teacher, class_obj, student)

        completed_debates = (
            session.query(DebateParticipation)
            .join(Debate, DebateParticipation.debate_id == Debate.id)
            .filter(
                DebateParticipation.user_id == student.id,
                Debate.status == "completed",
            )
            .count()
        )

        print("Seed completed.")
        print(f"student_name={student.name}")
        print(f"student_account={student.account}")
        print(f"student_password={STUDENT_PASSWORD}")
        print(f"student_id={student.student_id}")
        print(f"class_name={class_obj.name}")
        print(f"class_code={class_obj.code}")
        print(f"recommended_role={assessment.recommended_role}")
        print(f"completed_debates={completed_debates}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
