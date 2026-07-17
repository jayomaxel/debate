import pytest

from models.assessment import AbilityAssessment
from models.user import User
from services.debate_service import DebateService
import uuid


def test_fallback_role_assignment_returns_unique_roles_for_four_students():
    assignments = DebateService._fallback_assign_roles(
        {
            "student-expression": {
                "expression_willingness": 96,
                "logical_thinking": 60,
                "critical_thinking": 55,
                "financial_knowledge": 65,
                "stablecoin_knowledge": 50,
            },
            "student-logic": {
                "expression_willingness": 60,
                "logical_thinking": 96,
                "critical_thinking": 60,
                "financial_knowledge": 70,
                "stablecoin_knowledge": 55,
            },
            "student-critical": {
                "expression_willingness": 55,
                "logical_thinking": 70,
                "critical_thinking": 98,
                "financial_knowledge": 65,
                "stablecoin_knowledge": 60,
            },
            "student-knowledge": {
                "expression_willingness": 70,
                "logical_thinking": 75,
                "critical_thinking": 70,
                "financial_knowledge": 96,
                "stablecoin_knowledge": 88,
            },
        }
    )

    assert len(assignments) == 4
    assert len(set(assignments.values())) == 4
    assert assignments["student-critical"] == "debater_3"


def test_ai_auto_assign_rejects_manual_role_assignment():
    with pytest.raises(ValueError, match="ai_auto_assign"):
        DebateService._enforce_assignment_policy(
            {"assignment_policy": "ai_auto_assign"},
            [{"user_id": "student-1", "role": "debater_1"}],
            operation="create",
        )


def test_manual_role_assignment_marks_teacher_override(db_session):
    student_1 = User(
        id=uuid.uuid4(),
        account="role_assignment_student_1",
        password_hash="hashed",
        user_type="student",
        name="Role Student 1",
        email="role_assignment_student_1@test.com",
    )
    student_2 = User(
        id=uuid.uuid4(),
        account="role_assignment_student_2",
        password_hash="hashed",
        user_type="student",
        name="Role Student 2",
        email="role_assignment_student_2@test.com",
    )
    db_session.add_all([student_1, student_2])
    db_session.flush()
    db_session.add_all(
        [
            AbilityAssessment(
                id=uuid.uuid4(),
                user_id=student_1.id,
                expression_willingness=9,
                logical_thinking=6,
                expression_willingness_score=95,
                logical_thinking_score=60,
                critical_thinking_score=55,
                financial_knowledge_score=65,
                stablecoin_knowledge_score=50,
                is_default=False,
            ),
            AbilityAssessment(
                id=uuid.uuid4(),
                user_id=student_2.id,
                expression_willingness=6,
                logical_thinking=9,
                expression_willingness_score=60,
                logical_thinking_score=95,
                critical_thinking_score=55,
                financial_knowledge_score=65,
                stablecoin_knowledge_score=50,
                is_default=False,
            ),
        ]
    )
    db_session.commit()

    plan = DebateService._build_role_assignment_plan(
        db_session,
        student_ids=[str(student_1.id), str(student_2.id)],
        role_assignments=[
            {"user_id": str(student_1.id), "role": "debater_2", "override_reason": "train questioning"},
            {"user_id": str(student_2.id), "role": "debater_1"},
        ],
        assignment_mode="strength_first",
        config_meta={"assignment_policy": "ai_recommend_then_confirm"},
    )

    assert plan["assignment_mode"] == "strength_first"
    assert len(plan["results"]) == 2
    assert len({item["assigned_role"] for item in plan["results"]}) == 2
    assert any(item["teacher_override"] for item in plan["results"])
    assert any(item["override_reason"] == "train questioning" for item in plan["results"])
    assert any(item["assignment_source"] == "teacher_override" for item in plan["results"])
