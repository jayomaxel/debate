import uuid

from models.assessment import AbilityAssessment
from models.user import User
from services.assessment_service import AssessmentService


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
