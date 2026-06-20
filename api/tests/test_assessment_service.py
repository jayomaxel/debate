import uuid
from datetime import datetime

from models.assessment import AbilityAssessment
from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from models.user import User
from services.assessment_service import AssessmentService
from services.debate_service import DebateService


def create_student(db_session, account: str = "assessment_student") -> User:
    student = User(
        id=uuid.uuid4(),
        account=account,
        password_hash="hashed_password",
        user_type="student",
        name="Assessment Student",
        email=f"{account}@test.com",
    )
    db_session.add(student)
    db_session.commit()
    return student


def test_get_assessment_returns_none_without_creating_default_row(db_session):
    student = create_student(db_session, "assessment_none")

    result = AssessmentService.get_assessment(db=db_session, user_id=str(student.id))

    assert result is None
    assert (
        db_session.query(AbilityAssessment)
        .filter(AbilityAssessment.user_id == student.id)
        .count()
        == 0
    )


def test_get_assessment_hides_legacy_default_row(db_session):
    student = create_student(db_session, "assessment_default")
    default_assessment = AbilityAssessment(
        id=uuid.uuid4(),
        user_id=student.id,
        personality_type=None,
        expression_willingness=7,
        logical_thinking=6,
        expression_willingness_score=70,
        logical_thinking_score=60,
        stablecoin_knowledge_score=50,
        financial_knowledge_score=65,
        critical_thinking_score=75,
        is_default=True,
        recommended_role="debater_2",
    )
    db_session.add(default_assessment)
    db_session.commit()

    result = AssessmentService.get_assessment(db=db_session, user_id=str(student.id))

    assert result is None
    db_session.refresh(default_assessment)
    assert default_assessment.is_default is True


def test_submit_assessment_reuses_existing_default_row(db_session):
    student = create_student(db_session, "assessment_upgrade")
    default_assessment = AbilityAssessment(
        id=uuid.uuid4(),
        user_id=student.id,
        personality_type=None,
        expression_willingness=7,
        logical_thinking=6,
        expression_willingness_score=70,
        logical_thinking_score=60,
        stablecoin_knowledge_score=50,
        financial_knowledge_score=65,
        critical_thinking_score=75,
        is_default=True,
        recommended_role="debater_2",
    )
    db_session.add(default_assessment)
    db_session.commit()

    result = AssessmentService.submit_assessment(
        db=db_session,
        user_id=str(student.id),
        personality_type="balanced",
        expression_willingness=88,
        logical_thinking=92,
        stablecoin_knowledge=76,
        financial_knowledge=81,
        critical_thinking=90,
    )

    db_session.refresh(default_assessment)

    assert result["id"] == str(default_assessment.id)
    assert result["expression_willingness"] == 88
    assert result["logical_thinking"] == 92
    assert result["stablecoin_knowledge"] == 76
    assert result["financial_knowledge"] == 81
    assert result["critical_thinking"] == 90
    assert result["is_default"] is False
    assert default_assessment.is_default is False
    assert default_assessment.personality_type == "balanced"
    assert (
        db_session.query(AbilityAssessment)
        .filter(AbilityAssessment.user_id == student.id)
        .count()
        == 1
    )
    assert result["standard_profile"] == {
        "expression": 88,
        "logic": 92,
        "critical": 90,
        "knowledge_primary": 81,
        "knowledge_secondary": 76,
    }
    assert result["analysis_basis"] == "self_assessment_only"
    assert result["role_assignment_basis"]["analysis_basis"] == "self_assessment_only"
    assert "dimension_contribution" in result["role_fit"][result["recommended_role"]]


def test_build_standard_profile_maps_legacy_fields():
    profile = AssessmentService.build_standard_profile(
        {
            "expression_willingness": 72,
            "logical_thinking": 84,
            "critical_thinking": 91,
            "financial_knowledge": 66,
            "stablecoin_knowledge": 58,
        }
    )

    assert profile["standard_profile"] == {
        "expression": 72,
        "logic": 84,
        "critical": 91,
        "knowledge_primary": 66,
        "knowledge_secondary": 58,
    }
    assert profile["legacy_profile"]["logical_thinking"] == 84
    assert profile["analysis_basis"] == "self_assessment_only"


def test_role_fit_model_returns_contribution_and_reason():
    fit = AssessmentService.score_role_fit(
        {
            "expression_willingness": 60,
            "logical_thinking": 70,
            "critical_thinking": 95,
            "financial_knowledge": 65,
            "stablecoin_knowledge": 55,
        },
        "debater_3",
    )

    assert fit["role"] == "debater_3"
    assert fit["fit_score"] > 0
    assert fit["dimension_contribution"]["critical"] == 38.0
    assert fit["data_basis"] == "self_assessment_only"
    assert "反驳" in fit["assignment_reason"]


def test_get_assessment_includes_history_scores_and_speech_stats(db_session):
    teacher = User(
        id=uuid.uuid4(),
        account="assessment_teacher",
        password_hash="hashed_password",
        user_type="teacher",
        name="Assessment Teacher",
        email="assessment_teacher@test.com",
    )
    student = create_student(db_session, "assessment_history")
    db_session.add(teacher)
    db_session.commit()

    assessment = AbilityAssessment(
        id=uuid.uuid4(),
        user_id=student.id,
        personality_type="balanced",
        expression_willingness=8,
        logical_thinking=8,
        expression_willingness_score=82,
        logical_thinking_score=84,
        stablecoin_knowledge_score=70,
        financial_knowledge_score=76,
        critical_thinking_score=88,
        is_default=False,
        recommended_role="debater_3",
    )
    db_session.add(assessment)
    db_session.flush()

    debate = Debate(
        id=uuid.uuid4(),
        topic="assessment 历史依据测试",
        description="",
        duration=20,
        invitation_code=f"A{uuid.uuid4().hex[:5].upper()}",
        teacher_id=teacher.id,
        status="completed",
        mode="teacher_assigned",
        visibility="private",
        capacity=1,
        creator_user_id=teacher.id,
        owner_user_id=teacher.id,
        host_user_id=teacher.id,
        created_at=datetime.utcnow(),
    )
    db_session.add(debate)
    db_session.flush()

    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_3",
        stance="positive",
        role_reason=DebateService.ROLE_REASON["debater_3"],
        seat_order=3,
        joined_at=datetime.utcnow(),
    )
    db_session.add(participation)
    db_session.flush()

    speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_3",
        phase="free_debate",
        content="我回应对方论证中的逻辑漏洞，因此该结论并不成立。",
        duration=85,
        is_valid_for_scoring=True,
        timestamp=datetime.utcnow(),
    )
    db_session.add(speech)
    db_session.flush()

    score = Score(
        participation_id=participation.id,
        speech_id=speech.id,
        logic_score=86.0,
        argument_score=83.0,
        response_score=88.0,
        persuasion_score=80.0,
        teamwork_score=75.0,
        overall_score=82.5,
        feedback="整体回应有效，无明显违规。",
    )
    db_session.add(score)
    db_session.commit()

    result = AssessmentService.get_assessment(db=db_session, user_id=str(student.id))

    assert result is not None
    assert result["analysis_basis"] == "self_assessment_history_speech"
    assert "history_scores" in result["data_sources"]
    assert "speech_stats" in result["data_sources"]
    assert result["profile_confidence"] == "high"
    assert result["role_assignment_basis"]["history_scores"][0]["count"] == 1
    assert result["role_assignment_basis"]["speech_stats"][0]["speech_count"] == 1


def test_fallback_role_assignment_uses_standard_role_model():
    assignments = DebateService._fallback_assign_roles(
        {
            "student-expression": {
                "expression_willingness": 96,
                "logical_thinking": 88,
                "critical_thinking": 60,
                "financial_knowledge": 90,
                "stablecoin_knowledge": 70,
            },
            "student-logic": {
                "expression_willingness": 55,
                "logical_thinking": 97,
                "critical_thinking": 76,
                "financial_knowledge": 92,
                "stablecoin_knowledge": 70,
            },
            "student-critical": {
                "expression_willingness": 72,
                "logical_thinking": 76,
                "critical_thinking": 99,
                "financial_knowledge": 70,
                "stablecoin_knowledge": 60,
            },
            "student-summary": {
                "expression_willingness": 84,
                "logical_thinking": 82,
                "critical_thinking": 80,
                "financial_knowledge": 76,
                "stablecoin_knowledge": 96,
            },
        }
    )

    assert len(assignments) == 4
    assert len(set(assignments.values())) == 4
    assert assignments["student-critical"] == "debater_3"
