import uuid
from datetime import datetime

import pytest

from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from models.user import User
from services.report_service import ReportGenerator
from services.scoring_service import ScoringService


@pytest.mark.asyncio
async def test_report_readiness_scores_missing_valid_speeches(db_session):
    student = User(
        id=uuid.uuid4(),
        account="report_student",
        name="Report Student",
        email="report_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="人工智能是否应该进入课堂",
        description="",
        duration=5,
        invitation_code="RPT001",
        status="completed",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
    )
    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_1",
        stance="positive",
    )
    speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="opening",
        content="首先，人工智能可以提升课堂效率，并且研究表明个性化学习能够帮助学生更好地理解知识。",
        duration=18,
        is_valid_for_scoring=True,
        timestamp=datetime.utcnow(),
    )
    db_session.add_all([student, debate, participation, speech])
    db_session.commit()

    assert db_session.query(Score).filter(Score.speech_id == speech.id).count() == 0

    status = await ScoringService.ensure_debate_scored(db_session, str(debate.id))
    db_session.refresh(debate)
    report = ReportGenerator.generate_student_report(
        db_session,
        str(debate.id),
        str(student.id),
    )

    assert status["generated"] is True
    assert status["ready"] is True
    assert debate.report["report_meta"]["provider"] == "local"
    assert debate.report["participant_scores"][0]["rubric_version"] == "a.rubric.v1"
    assert debate.report["evidence_anchors"][0]["turn_id"] == str(speech.id)
    assert debate.report["calibration_summary"]["calibration_version"] == "a.calibration.v1"
    assert db_session.query(Score).filter(Score.speech_id == speech.id).count() == 1
    assert report is not None
    assert report.participants[0]["final_score"]["overall_score"] > 0
    assert report.speeches[0]["score"]["overall_score"] > 0

    report_data = report.to_dict()
    assert report_data["participants"] == report.participants
    assert report_data["speeches"] == report.speeches
    assert report_data["statistics"] == report.statistics
    assert report_data["winner"] == report.winner
    assert report_data["mode"] == "competition"
    assert report_data["domain_pack_id"] == "default"
    assert report_data["report_meta"]["scoring_quality"] == "validated"
    assert report_data["report_meta"]["provider"] == "local"
    assert report_data["participant_scores"][0]["overall_score"] > 0
    assert report_data["evidence_anchors"][0]["turn_id"] == str(speech.id)
    assert report_data["turning_points"][0]["turn_id"] == str(speech.id)
    assert report_data["team_summary"]["positive"]["participant_count"] == 1
    assert report_data["statistics"]["calibration_summary"]["calibration_version"] == "a.calibration.v1"
    assert "anomaly_samples" in report_data["statistics"]


def test_report_includes_participants_without_speeches(db_session):
    student = User(
        id=uuid.uuid4(),
        account="silent_student",
        name="Silent Student",
        email="silent_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="测试未发言参与者",
        description="",
        duration=5,
        invitation_code="RPT002",
        status="completed",
    )
    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_1",
        stance="positive",
    )
    db_session.add_all([student, debate, participation])
    db_session.commit()

    report = ReportGenerator.generate_student_report(
        db_session,
        str(debate.id),
        str(student.id),
    )

    assert report is not None
    assert report.participants[0]["user_id"] == str(student.id)
    assert report.participants[0]["has_speech"] is False
    assert report.participants[0]["score_status"] == "no_speech"
    assert report.participants[0]["final_score"]["speech_count"] == 0
    assert report.statistics["calibration_summary"]["sample_count"] >= 1


def test_report_inherits_existing_a_contract_fields(db_session):
    student = User(
        id=uuid.uuid4(),
        account="contract_student",
        name="Contract Student",
        email="contract_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="测试报告合同继承",
        description="",
        duration=5,
        invitation_code="RPT003",
        status="completed",
        report={
            "mode": "teaching",
            "domain_pack_id": "pack-a",
            "report_meta": {
                "scoring_source": "fallback",
                "scoring_quality": "fallback",
                "provider": "llm",
            },
            "turning_points": [{"turn_id": "kept-turn", "summary": "kept", "impact": "kept"}],
            "teaching_summary": {"learning_objectives": ["kept"]},
        },
    )
    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_1",
        stance="positive",
    )
    db_session.add_all([student, debate, participation])
    db_session.commit()

    report = ReportGenerator.generate_student_report(
        db_session,
        str(debate.id),
        str(student.id),
    )

    assert report is not None
    report_data = report.to_dict()
    assert report_data["mode"] == "teaching"
    assert report_data["domain_pack_id"] == "pack-a"
    assert report_data["report_meta"]["scoring_quality"] == "fallback"
    assert report_data["report_meta"]["mode"] == "teaching"
    assert report_data["report_meta"]["prompt_pack_version"] == "a.prompt_pack.v1"
    assert report_data["turning_points"][0]["turn_id"] == "kept-turn"
    assert report_data["teaching_summary"]["learning_objectives"] == ["kept"]
    assert report_data["statistics"]["calibration_summary"]["fairness_check"]["status"] == "needs_review"
