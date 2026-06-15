import uuid

from models.assessment import AbilityAssessment
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
