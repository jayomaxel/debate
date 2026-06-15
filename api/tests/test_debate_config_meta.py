import uuid
from datetime import datetime, timedelta

import pytest

from models.class_model import Class
from models.debate import Debate
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

    debate = db_session.query(Debate).filter(Debate.id == uuid.UUID(result["id"])).one()
    stored_meta = DebateService._get_debate_config_meta(debate)
    assert stored_meta["role_assignment_mode"] == "growth_first"
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
