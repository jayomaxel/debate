import uuid
import asyncio
from datetime import datetime

from models.class_model import Class
from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from models.user import User
from services.analytics_service import AnalyticsService
from services.comparison_service import ComparisonService
from services.report_orchestration_service import ReportOrchestrationService
from services.role_assignment_learning_service import RoleAssignmentLearningService
from services.score_eligibility_service import ScoreEligibilityService
from services.scoring_service import ScoringService


def _score_fixture(db_session):
    teacher = User(
        id=uuid.uuid4(),
        account=f"score-teacher-{uuid.uuid4().hex[:8]}",
        name="Score Teacher",
        email=f"{uuid.uuid4().hex}@example.test",
        password_hash="hashed",
        user_type="teacher",
    )
    class_obj = Class(
        id=uuid.uuid4(),
        name="Score Isolation",
        code=uuid.uuid4().hex[:10],
        teacher_id=teacher.id,
    )
    student = User(
        id=uuid.uuid4(),
        account=f"score-student-{uuid.uuid4().hex[:8]}",
        name="Score Student",
        email=f"{uuid.uuid4().hex}@example.test",
        password_hash="hashed",
        user_type="student",
        class_id=class_obj.id,
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="Fallback isolation",
        duration=20,
        invitation_code=uuid.uuid4().hex[:6],
        teacher_id=teacher.id,
        class_id=class_obj.id,
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
    validated_speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="opening",
        content="A validated speech.",
        duration=30,
        is_valid_for_scoring=True,
    )
    fallback_speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="closing",
        content="A speech whose provider failed.",
        duration=30,
        is_valid_for_scoring=True,
    )
    validated = Score(
        id=uuid.uuid4(),
        participation_id=participation.id,
        speech_id=validated_speech.id,
        logic_score=90,
        argument_score=88,
        response_score=86,
        persuasion_score=84,
        teamwork_score=82,
        overall_score=88,
        feedback="validated",
        status="validated",
        scoring_source="judge_model",
        scoring_quality="validated",
        provider="llm",
        rubric_version="rubric-test-v1",
        eligible_for_analytics=True,
    )
    fallback = Score(
        id=uuid.uuid4(),
        participation_id=participation.id,
        speech_id=fallback_speech.id,
        logic_score=70,
        argument_score=70,
        response_score=70,
        persuasion_score=70,
        teamwork_score=70,
        overall_score=70,
        feedback="评分系统暂时不可用",
        status="fallback",
        scoring_source="fallback",
        scoring_quality="fallback",
        provider="llm",
        failure_code="SCORING_PROVIDER_ERROR",
        eligible_for_analytics=False,
    )
    # Flush explicit FK layers so this fixture is valid on PostgreSQL as well
    # as SQLite (these models do not expose every relationship to the ORM).
    db_session.add(teacher)
    db_session.flush()
    db_session.add(class_obj)
    db_session.flush()
    db_session.add_all([student, debate])
    db_session.flush()
    db_session.add_all([participation, validated_speech, fallback_speech])
    db_session.flush()
    db_session.add_all([validated, fallback])
    db_session.commit()
    return class_obj, student, debate, participation, validated, fallback


def test_fallback_is_excluded_from_profiles_averages_rankings_and_training(db_session):
    class_obj, student, debate, participation, _, _ = _score_fixture(db_session)

    final_score = ScoringService.calculate_final_score(db_session, str(participation.id))
    assert final_score["overall_score"] == 88

    student_stats = AnalyticsService(db_session).get_student_statistics(student.id)
    assert student_stats["average_score"] == 88
    assert student_stats["ability_scores"]["logic"] == 90

    class_stats = AnalyticsService(db_session).get_average_score(class_obj.id)
    assert class_stats["class_avg_score"] == 88

    comparison = ComparisonService(db_session).get_class_comparison(student.id)
    assert comparison["sample_size"] == 1
    assert comparison["my"]["overall_score"] == 88

    training_summary = RoleAssignmentLearningService._student_score_summary(
        db_session,
        str(student.id),
    )
    assert training_summary == {"count": 1, "average": 88.0, "volatility": 0.0}

    report_meta = ReportOrchestrationService.build_report_meta(db_session, debate)
    assert report_meta["score_fallback_detected"] is True
    assert report_meta["score_fallback_count"] == 1
    assert report_meta["score_ineligible_count"] == 1
    assert report_meta["report_quality"] == "partial"


def test_successful_retry_becomes_eligible_and_preserves_fallback_audit(db_session):
    _, student, _, _, _, fallback = _score_fixture(db_session)
    provenance = ScoreEligibilityService.provenance_from_report_meta(
        {
            "scoring_source": "judge_model",
            "scoring_quality": "repaired",
            "provider": "llm",
            "retry_count": 2,
            "rubric_version": "rubric-test-v1",
        }
    )
    ScoreEligibilityService.apply_provenance(
        fallback,
        provenance,
        audit_reason="provider_retry_succeeded",
    )
    fallback.logic_score = 92
    fallback.overall_score = 91
    db_session.commit()

    db_session.refresh(fallback)
    assert fallback.status == "repaired"
    assert fallback.eligible_for_analytics is True
    assert fallback.failure_code is None
    assert fallback.score_metadata["attempt_history"][-1]["status"] == "fallback"
    assert fallback.score_metadata["attempt_history"][-1]["reason"] == "provider_retry_succeeded"

    student_stats = AnalyticsService(db_session).get_student_statistics(student.id)
    assert student_stats["average_score"] == 89.5


def test_unknown_legacy_score_is_not_implicitly_trusted():
    score = Score(feedback="ordinary legacy feedback")
    assert ScoreEligibilityService.infer_legacy_status(score.feedback) == "legacy_unknown"
    assert ScoreEligibilityService.is_eligible(score) is False
    assert ScoreEligibilityService.infer_legacy_status("评分系统暂时不可用") == "fallback"


def test_provider_failure_writes_fallback_but_does_not_replace_trusted_retry(
    db_session,
    monkeypatch,
):
    _, _, debate, participation, validated, _ = _score_fixture(db_session)

    class FailingJudge:
        def __init__(self, db):
            self.db = db

        async def score_speech(self, **kwargs):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr("services.scoring_service.JudgeAgent", FailingJudge)

    new_speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="questioning",
        content="Provider failure speech.",
        duration=20,
        is_valid_for_scoring=True,
    )
    db_session.add(new_speech)
    db_session.commit()

    fallback = asyncio.run(
        ScoringService.score_speech(
            db_session,
            str(new_speech.id),
            str(participation.id),
            new_speech.content,
            new_speech.speaker_role,
            new_speech.phase,
            [],
        )
    )
    assert fallback.status == "fallback"
    assert fallback.failure_code == "SCORING_PROVIDER_ERROR"
    assert fallback.eligible_for_analytics is False

    preserved = asyncio.run(
        ScoringService.score_speech(
            db_session,
            str(validated.speech_id),
            str(participation.id),
            "Retry for trusted speech.",
            "debater_1",
            "opening",
            [],
        )
    )
    assert preserved.id == validated.id
    assert preserved.status == "validated"
    assert preserved.overall_score == 88
    inactive = preserved.score_metadata["attempt_history"][-1]
    assert inactive["status"] == "fallback"
    assert inactive["active"] is False
