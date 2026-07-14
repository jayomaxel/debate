import uuid
from datetime import datetime, timedelta

import pytest

from models.class_model import Class
from models.debate import Debate
from models.teaching_design import (
    ClassTeachingDesignVersion,
    TopicRecommendationItem,
    TopicRecommendationRun,
)
from models.user import User
from routers.teacher import UpdateDebateRequest, _config_meta_payload
from services.debate_service import DebateService


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
        name="Config Class",
        code=f"C{uuid.uuid4().hex[:8]}",
        teacher_id=teacher.id,
    )
    db_session.add(cls)
    db_session.commit()
    return teacher, cls


def _topic_recommendation_fixture(db_session, cls: Class, teacher: User, topic_text: str = "课堂中是否应限制生成式AI的直接代写使用？"):
    design = ClassTeachingDesignVersion(
        id=uuid.uuid4(),
        class_id=cls.id,
        created_by=teacher.id,
        version_name="v1",
        title="教学设计",
        extracted_payload={
            "course_title": "人工智能导论",
            "chapter_theme": "生成式AI与教育",
            "learning_objectives": ["理解生成式AI课堂应用"],
            "knowledge_points": ["生成式AI", "课堂规范"],
            "debate_focuses": ["应用边界"],
        },
        extraction_status="completed",
        is_active=True,
        activated_at=datetime.utcnow(),
    )
    db_session.add(design)
    db_session.flush()

    run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=design.id,
        created_by=teacher.id,
        mode="competition",
        status="available",
        teaching_design_status="available",
        provider="fallback",
        generation_quality="fallback",
        preferred_count=4,
    )
    db_session.add(run)
    db_session.flush()

    item = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run.id,
        candidate_order=1,
        topic_text=topic_text,
        course_objectives=["理解生成式AI课堂应用"],
        knowledge_points=["生成式AI", "课堂规范"],
        classroom_scene="课堂辩论",
        debatability_reason="题目存在清晰的治理与开放之争。",
        difficulty_level="medium",
        recommendation_reason="能够直接对应课程中的应用边界讨论。",
        source_basis=["课程：人工智能导论"],
        quality_score=88.0,
        quality_flags=[],
    )
    db_session.add(item)
    db_session.commit()
    return run, item


@pytest.mark.asyncio
async def test_create_debate_persists_structured_config_meta(db_session):
    teacher, cls = _teacher_class(db_session)
    result = await DebateService.create_debate(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic="是否应当引入课堂辩论",
        duration=30,
        description="原始描述",
        config_meta={
            "mode": "teaching",
            "role_assignment_mode": "growth_first",
            "role_rotation_policy": "growth_priority",
            "fairness_window_size": 7,
            "same_role_max_streak": 3,
            "assignment_policy": "ai_auto_assign",
            "rounds": 4,
            "knowledge_points": ["概念辨析", "论据组织"],
            "objective": ["提升表达"],
            "evaluation_focus": ["逻辑"],
            "forbidden_moves": ["人身攻击"],
            "support_document_ids": ["doc-1", "doc-2"],
            "domain_pack_id": "pack-1",
            "teaching_design_version_id": "design-1",
            "activity_focus": {
                "chapter_focus": "第一章",
                "training_focus": "立论",
                "classroom_scene": "课堂导入",
            },
        },
    )

    assert result["config_meta"]["mode"] == "teaching"
    assert result["config_meta"]["rounds"] == 4
    assert result["config_meta"]["activity_focus"]["training_focus"] == "立论"
    assert result["config_meta"]["role_rotation_policy"] == "growth_priority"
    assert result["config_meta"]["fairness_window_size"] == 7
    assert result["config_meta"]["same_role_max_streak"] == 3

    debate = db_session.query(Debate).filter(Debate.id == uuid.UUID(result["id"])).one()
    stored_meta = DebateService._get_debate_config_meta(debate)
    assert stored_meta["role_assignment_mode"] == "growth_first"
    assert stored_meta["role_rotation_policy"] == "growth_priority"
    assert stored_meta["support_document_ids"] == ["doc-1", "doc-2"]


@pytest.mark.asyncio
async def test_update_debate_updates_config_meta_and_keeps_description(db_session):
    teacher, cls = _teacher_class(db_session)
    created = await DebateService.create_debate(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic="原始辩题",
        duration=20,
        description="保留说明",
        config_meta={
            "mode": "teaching",
            "role_assignment_mode": "growth_first",
            "support_document_ids": ["doc-a"],
        },
    )

    updated = await DebateService.update_debate(
        db=db_session,
        teacher_id=str(teacher.id),
        debate_id=created["id"],
        config_meta={
            "rounds": 2,
        },
    )

    assert updated["description"] == "保留说明"
    assert updated["config_meta"]["rounds"] == 2
    assert updated["config_meta"]["mode"] == "teaching"
    assert updated["config_meta"]["role_assignment_mode"] == "growth_first"
    assert updated["config_meta"]["support_document_ids"] == ["doc-a"]


@pytest.mark.asyncio
async def test_create_reservation_returns_structured_config_meta(db_session):
    teacher, cls = _teacher_class(db_session)
    student = _user(f"student_{uuid.uuid4().hex[:8]}", "Student", "student", cls.id)
    db_session.add(student)
    db_session.commit()

    result = await DebateService.create_reservation(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic="预约辩题",
        duration=30,
        description="预约描述",
        config_meta={
            "mode": "competition",
            "role_assignment_mode": "strength_first",
            "assignment_policy": "ai_recommend_then_confirm",
            "rounds": 3,
            "activity_focus": {
                "chapter_focus": "第二章",
            },
        },
        scheduled_start_time=datetime.utcnow() + timedelta(hours=1),
        student_ids=[str(student.id)],
    )

    assert result["config_meta"]["rounds"] == 3
    assert result["config_meta"]["activity_focus"]["chapter_focus"] == "第二章"


def test_normalize_debate_config_meta_rejects_unknown_fields():
    with pytest.raises(ValueError, match="未知字段"):
        DebateService.normalize_debate_config_meta({"unknown": 1})


def test_normalize_debate_config_meta_accepts_legacy_json_description():
    meta = DebateService.normalize_debate_config_meta(
        description='{"mode":"teaching","rounds":5,"activity_focus":{"classroom_scene":"demo"}}'
    )
    assert meta["mode"] == "teaching"
    assert meta["rounds"] == 5
    assert meta["activity_focus"]["classroom_scene"] == "demo"


@pytest.mark.asyncio
async def test_update_description_keeps_legacy_config_meta(db_session):
    teacher, cls = _teacher_class(db_session)
    created = await DebateService.create_debate(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic="旧描述兼容",
        duration=20,
        description='{"mode":"teaching","rounds":5,"support_document_ids":["legacy-doc"]}',
    )

    updated = await DebateService.update_debate(
        db=db_session,
        teacher_id=str(teacher.id),
        debate_id=created["id"],
        description="新版纯文本描述",
    )

    assert updated["description"] == "新版纯文本描述"
    assert updated["config_meta"]["mode"] == "teaching"
    assert updated["config_meta"]["rounds"] == 5
    assert updated["config_meta"]["support_document_ids"] == ["legacy-doc"]

    debate = db_session.query(Debate).filter(Debate.id == uuid.UUID(created["id"])).one()
    assert debate.description == "新版纯文本描述"
    assert DebateService._serialize_debate_config_meta(debate)["rounds"] == 5


def test_update_debate_request_accepts_config_meta_only():
    request = UpdateDebateRequest(
        config_meta={
            "rounds": 6,
            "evaluation_focus": ["回应质量"],
        }
    )

    assert request.class_id is None
    assert request.topic is None
    assert request.duration is None
    assert request.config_meta is not None

    payload = _config_meta_payload(request.config_meta)
    assert payload == {
        "rounds": 6,
        "evaluation_focus": ["回应质量"],
    }


@pytest.mark.asyncio
async def test_create_debate_persists_topic_recommendation_provenance(db_session):
    teacher, cls = _teacher_class(db_session)
    run, item = _topic_recommendation_fixture(db_session, cls, teacher)

    created = await DebateService.create_debate(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic=item.topic_text,
        duration=20,
        config_meta={
            "topic_recommendation_run_id": str(run.id),
            "selected_topic_candidate_id": str(item.id),
            "topic_source": "ai_recommended",
        },
    )

    assert created["config_meta"]["topic_recommendation_run_id"] == str(run.id)
    assert created["config_meta"]["selected_topic_candidate_id"] == str(item.id)
    assert created["config_meta"]["topic_source"] == "ai_recommended"
    assert created["config_meta"]["teaching_design_version_id"] == str(run.teaching_design_version_id)


@pytest.mark.asyncio
async def test_update_debate_marks_edited_topic_source_when_teacher_changes_candidate_text(db_session):
    teacher, cls = _teacher_class(db_session)
    run, item = _topic_recommendation_fixture(db_session, cls, teacher)
    created = await DebateService.create_debate(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic=item.topic_text,
        duration=20,
        config_meta={
            "topic_recommendation_run_id": str(run.id),
            "selected_topic_candidate_id": str(item.id),
            "topic_source": "ai_recommended",
        },
    )

    updated = await DebateService.update_debate(
        db=db_session,
        teacher_id=str(teacher.id),
        debate_id=created["id"],
        topic=item.topic_text + "（课堂试行）",
        config_meta={
            "topic_recommendation_run_id": str(run.id),
            "selected_topic_candidate_id": str(item.id),
            "topic_source": "ai_recommended_edited",
        },
    )

    assert updated["config_meta"]["topic_source"] == "ai_recommended_edited"
    assert updated["config_meta"]["teaching_design_version_id"] == str(run.teaching_design_version_id)


@pytest.mark.asyncio
async def test_create_reservation_persists_topic_recommendation_provenance(db_session):
    teacher, cls = _teacher_class(db_session)
    student = _user(f"student_{uuid.uuid4().hex[:8]}", "Student", "student", cls.id)
    db_session.add(student)
    db_session.commit()
    run, item = _topic_recommendation_fixture(db_session, cls, teacher)

    result = await DebateService.create_reservation(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic=item.topic_text,
        duration=30,
        config_meta={
            "topic_recommendation_run_id": str(run.id),
            "selected_topic_candidate_id": str(item.id),
            "topic_source": "ai_recommended",
        },
        scheduled_start_time=datetime.utcnow() + timedelta(hours=1),
        student_ids=[str(student.id)],
    )

    assert result["config_meta"]["topic_recommendation_run_id"] == str(run.id)
    assert result["config_meta"]["selected_topic_candidate_id"] == str(item.id)
    assert result["config_meta"]["topic_source"] == "ai_recommended"
    assert result["config_meta"]["teaching_design_version_id"] == str(run.teaching_design_version_id)


@pytest.mark.asyncio
async def test_create_debate_persists_role_assignment_snapshot(db_session):
    teacher, cls = _teacher_class(db_session)
    student_a = _user(f"student_a_{uuid.uuid4().hex[:8]}", "Student A", "student", cls.id)
    student_b = _user(f"student_b_{uuid.uuid4().hex[:8]}", "Student B", "student", cls.id)
    db_session.add_all([student_a, student_b])
    db_session.commit()

    result = await DebateService.create_debate(
        db=db_session,
        teacher_id=str(teacher.id),
        class_id=str(cls.id),
        topic="人工覆盖辩位",
        duration=20,
        student_ids=[str(student_a.id), str(student_b.id)],
        role_assignments=[
            {"user_id": str(student_a.id), "role": "debater_2"},
            {"user_id": str(student_b.id), "role": "debater_1"},
        ],
    )

    debate = db_session.query(Debate).filter(Debate.id == uuid.UUID(result["id"])).one()
    meta = DebateService._get_room_meta(debate)
    snapshot = meta.get("role_assignment_snapshot") or []
    assert len(snapshot) == 2
    assert any(item["assigned_role"] == "debater_2" for item in snapshot)
    assert result["grouping"][0]["assigned_role"] in {"debater_1", "debater_2"}
