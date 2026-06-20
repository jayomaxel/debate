import uuid
from datetime import datetime

import pytest

from models.class_model import Class
from models.debate import (
    Debate,
    DebateParticipation,
    DebateRoleAssignmentItem,
    DebateRoleAssignmentRun,
    DebateRolePerformanceSample,
)
from models.score import Score
from models.speech import Speech
from models.user import User
from services.debate_service import DebateService
from services.role_assignment_learning_service import RoleAssignmentLearningService


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


def _teacher_class(db_session):
    teacher = _user(f"teacher_{uuid.uuid4().hex[:8]}", "Teacher", "teacher")
    db_session.add(teacher)
    db_session.flush()
    cls = Class(
        id=uuid.uuid4(),
        name="Learning Class",
        code=f"LC{uuid.uuid4().hex[:8]}",
        teacher_id=teacher.id,
    )
    db_session.add(cls)
    db_session.commit()
    return teacher, cls


@pytest.mark.asyncio
async def test_create_debate_persists_assignment_run_and_model_payload(db_session):
    teacher, cls = _teacher_class(db_session)
    student_a = _user(f"student_a_{uuid.uuid4().hex[:8]}", "Student A", "student", cls.id)
    student_b = _user(f"student_b_{uuid.uuid4().hex[:8]}", "Student B", "student", cls.id)
    db_session.add_all([student_a, student_b])
    db_session.commit()

    result = await DebateService.create_debate(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic="测试辩位学习评分",
        duration=20,
        student_ids=[str(student_a.id), str(student_b.id)],
        role_assignments=[
            {"user_id": str(student_a.id), "role": "debater_2", "override_reason": "需要训练追问能力"},
            {"user_id": str(student_b.id), "role": "debater_1"},
        ],
    )

    assert result["role_assignment_run"] is not None
    assert result["role_assignment_run"]["model_version"] == RoleAssignmentLearningService.MODEL_VERSION
    assert len(result["role_assignment_run"]["items"]) == 2
    assert "model_score" in result["role_assignment_run"]["items"][0]

    run_id = uuid.UUID(result["role_assignment_run"]["run_id"])
    persisted_run = db_session.query(DebateRoleAssignmentRun).filter(DebateRoleAssignmentRun.id == run_id).one()
    assert persisted_run.assignment_mode == "strength_first"
    persisted_items = db_session.query(DebateRoleAssignmentItem).filter(DebateRoleAssignmentItem.run_id == run_id).all()
    assert len(persisted_items) == 2
    assert any(item.override_reason for item in persisted_items)


def test_materialize_debate_samples_from_completed_debate(db_session):
    teacher, cls = _teacher_class(db_session)
    student = _user(f"sample_student_{uuid.uuid4().hex[:8]}", "Sample Student", "student", cls.id)
    db_session.add(student)
    db_session.commit()

    debate = Debate(
        id=uuid.uuid4(),
        topic="样本沉淀测试",
        description="",
        duration=20,
        invitation_code=f"S{uuid.uuid4().hex[:5].upper()}",
        class_id=cls.id,
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
        role="debater_1",
        stance="positive",
        role_reason=DebateService.ROLE_REASON["debater_1"],
        seat_order=1,
    )
    db_session.add(participation)
    db_session.flush()

    run = DebateRoleAssignmentRun(
        debate_id=debate.id,
        class_id=cls.id,
        source="teacher_save",
        target_mode="teacher_assigned",
        assignment_mode="strength_first",
        rotation_policy="balanced_rotation",
        model_version=RoleAssignmentLearningService.MODEL_VERSION,
        created_by=teacher.id,
    )
    db_session.add(run)
    db_session.flush()

    item = DebateRoleAssignmentItem(
        run_id=run.id,
        user_id=student.id,
        recommended_role="debater_1",
        assigned_role="debater_1",
        final_role="debater_1",
        fit_score=78.0,
        rule_fit_score=78.0,
        final_score=80.0,
        model_score=79.0,
        growth_score=62.0,
        confidence=45.0,
        standard_profile={
            "expression": 70,
            "logic": 75,
            "critical": 68,
            "knowledge_primary": 72,
            "knowledge_secondary": 66,
        },
    )
    db_session.add(item)
    db_session.flush()

    speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="opening",
        content="这是一次包含立论结构和论据支持的发言。",
        duration=90,
        is_valid_for_scoring=True,
        timestamp=datetime.utcnow(),
    )
    db_session.add(speech)
    db_session.flush()

    score = Score(
        participation_id=participation.id,
        speech_id=speech.id,
        logic_score=82.0,
        argument_score=80.0,
        response_score=75.0,
        persuasion_score=78.0,
        teamwork_score=74.0,
        overall_score=78.5,
        feedback="整体表现稳定，无明显违规。",
    )
    db_session.add(score)
    db_session.commit()

    samples = RoleAssignmentLearningService.materialize_debate_samples(db_session, str(debate.id))

    assert len(samples) == 1
    persisted = (
        db_session.query(DebateRolePerformanceSample)
        .filter(DebateRolePerformanceSample.debate_id == debate.id)
        .one()
    )
    assert persisted.role == "debater_1"
    assert persisted.assignment_run_id == run.id
    assert persisted.assignment_item_id == item.id
    assert persisted.obvious_mistake_count == 0
    assert persisted.feature_vector is not None
    assert persisted.label_vector is not None
