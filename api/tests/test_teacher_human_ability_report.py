import uuid
from datetime import datetime

from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from models.user import User
from services.report_service import ReportGenerator


def _student(index: int) -> User:
    return User(
        id=uuid.uuid4(),
        account=f"radar_student_{index}",
        name=f"Radar Student {index}",
        email=f"radar_student_{index}@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )


def _speech(debate_id, student_id, role: str, content: str) -> Speech:
    return Speech(
        id=uuid.uuid4(),
        debate_id=debate_id,
        speaker_id=student_id,
        speaker_type="human" if student_id else "ai",
        speaker_role=role,
        phase="opening",
        content=content,
        duration=10,
        is_valid_for_scoring=True,
        timestamp=datetime.utcnow(),
    )


def test_human_radar_excludes_ai_and_weights_students_equally(db_session):
    admin = db_session.query(User).filter(User.user_type == "administrator").first()
    students = [_student(1), _student(2)]
    debate = Debate(
        id=uuid.uuid4(),
        topic="能力雷达统计口径",
        description="",
        duration=5,
        invitation_code="RADAR01",
        status="completed",
    )
    participations = [
        DebateParticipation(
            id=uuid.uuid4(),
            debate_id=debate.id,
            user_id=student.id,
            role=f"debater_{index}",
            stance="positive" if index == 1 else "negative",
        )
        for index, student in enumerate(students, 1)
    ]
    db_session.add_all([*students, debate, *participations])
    db_session.flush()

    for student, participation, values in (
        (students[0], participations[0], [40, 60]),
        (students[1], participations[1], [100]),
    ):
        for value in values:
            speech = _speech(debate.id, student.id, participation.role, f"有效发言 {value}")
            db_session.add(speech)
            db_session.flush()
            db_session.add(
                Score(
                    participation_id=participation.id,
                    speech_id=speech.id,
                    logic_score=value,
                    argument_score=value,
                    response_score=value,
                    persuasion_score=value,
                    teamwork_score=value,
                    overall_score=value,
                )
            )

    db_session.add(_speech(debate.id, None, "ai_1", "AI 发言不进入能力雷达"))
    db_session.commit()

    report = ReportGenerator.generate_student_report(
        db_session,
        str(debate.id),
        str(admin.id),
    )
    human = report.statistics["human_ability"]

    assert human["evaluated_student_count"] == 2
    assert human["valid_human_speech_count"] == 3
    assert human["excluded_ai_speech_count"] == 1
    assert human["ability_scores"]["logical_construction"] == 75.0
    assert human["overall_score"] == 75.0


def test_human_radar_returns_null_scores_when_only_ai_spoke(db_session):
    admin = db_session.query(User).filter(User.user_type == "administrator").first()
    debate = Debate(
        id=uuid.uuid4(),
        topic="只有 AI 发言",
        description="",
        duration=5,
        invitation_code="RADAR02",
        status="completed",
    )
    db_session.add_all([debate, _speech(debate.id, None, "ai_1", "AI 发言")])
    db_session.commit()

    report = ReportGenerator.generate_student_report(
        db_session,
        str(debate.id),
        str(admin.id),
    )
    human = report.statistics["human_ability"]

    assert human["has_human_ability_data"] is False
    assert human["ability_scores"] is None
    assert human["overall_score"] is None
