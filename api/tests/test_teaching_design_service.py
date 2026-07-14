from io import BytesIO
import uuid
from datetime import datetime

import docx

from models.class_model import Class
from models.user import User
from services.teaching_design_service import TeachingDesignService


def _user(account: str, name: str, user_type: str) -> User:
    return User(
        id=uuid.uuid4(),
        account=account,
        name=name,
        email=f"{account}@test.com",
        password_hash="hashed",
        user_type=user_type,
        created_at=datetime.utcnow(),
    )


def _teacher_class(db_session):
    teacher = _user(f"teacher_{uuid.uuid4().hex[:8]}", "Teacher", "teacher")
    db_session.add(teacher)
    db_session.flush()
    cls = Class(
        id=uuid.uuid4(),
        name="Teaching Design Class",
        code=f"D{uuid.uuid4().hex[:8]}",
        teacher_id=teacher.id,
    )
    db_session.add(cls)
    db_session.commit()
    return teacher, cls


def _build_docx_bytes(paragraphs):
    buffer = BytesIO()
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(buffer)
    return buffer.getvalue()


def test_infer_payload_from_raw_text_extracts_core_fields():
    raw_text = """
课程名称：人工智能导论
章节主题：生成式AI与教育
学习目标：
1. 理解生成式AI的课堂应用边界
2. 训练学生立场论证能力
知识点：
生成式AI、课堂评价、学习迁移
重点难点：
工具依赖风险；课堂规则设计
能力目标：
批判性思维、口头表达
适用年级：本科二年级
课时：2课时
辩论焦点：
课堂中应优先强调开放探索还是使用约束
"""

    payload = TeachingDesignService.infer_payload_from_raw_text(raw_text)

    assert payload["course_title"] == "人工智能导论"
    assert payload["chapter_theme"] == "生成式AI与教育"
    assert "理解生成式AI的课堂应用边界" in payload["learning_objectives"]
    assert "生成式AI" in payload["knowledge_points"]
    assert "批判性思维" in payload["capability_targets"]
    assert payload["grade_level"] == "本科二年级"
    assert payload["time_constraints"] == "2课时"


def test_upload_and_extract_current_version_from_docx_persists_active_record(db_session):
    teacher, cls = _teacher_class(db_session)
    file_bytes = _build_docx_bytes(
        [
            "课程名称：人工智能导论",
            "章节主题：生成式AI与教育",
            "学习目标：理解生成式AI的课堂应用边界；训练学生立场论证能力",
            "知识点：生成式AI、课堂评价、学习迁移",
            "能力目标：批判性思维、口头表达",
            "辩论焦点：课堂中是否应限制生成式AI的直接代写使用",
        ]
    )

    version = TeachingDesignService.upload_and_extract_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        file_data=file_bytes,
        filename="teaching-design.docx",
        file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        version_name="v1",
    )

    assert version["source_type"] == "upload"
    assert version["source_filename"] == "teaching-design.docx"
    assert version["source_file_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert version["source_file_size"] == len(file_bytes)
    assert version["is_active"] is True
    assert version["title"] == "teaching-design.docx"
    assert version["extracted_payload"]["course_title"] == "人工智能导论"
    assert "生成式AI" in version["extracted_payload"]["knowledge_points"]


def test_list_versions_returns_active_first(db_session):
    teacher, cls = _teacher_class(db_session)
    TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload={
            "course_title": "人工智能导论",
            "knowledge_points": ["生成式AI"],
            "learning_objectives": ["目标一"],
            "capability_targets": ["表达"],
            "debate_focuses": ["焦点一"],
        },
        version_name="v1",
        title="第一版",
    )
    TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload={
            "course_title": "人工智能导论",
            "knowledge_points": ["课堂评价"],
            "learning_objectives": ["目标二"],
            "capability_targets": ["逻辑"],
            "debate_focuses": ["焦点二"],
        },
        version_name="v2",
        title="第二版",
    )

    versions = TeachingDesignService.list_versions(db_session, str(cls.id))

    assert len(versions) == 2
    assert versions[0]["is_active"] is True
    assert versions[0]["version_name"] == "v2"


def test_activate_version_switches_active_record(db_session):
    teacher, cls = _teacher_class(db_session)
    first = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload={
            "course_title": "人工智能导论",
            "knowledge_points": ["生成式AI"],
            "learning_objectives": ["目标一"],
            "capability_targets": ["表达"],
            "debate_focuses": ["焦点一"],
        },
        version_name="v1",
        title="第一版",
    )
    second = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload={
            "course_title": "人工智能导论",
            "knowledge_points": ["课堂评价"],
            "learning_objectives": ["目标二"],
            "capability_targets": ["逻辑"],
            "debate_focuses": ["焦点二"],
        },
        version_name="v2",
        title="第二版",
    )

    activated = TeachingDesignService.activate_version(
        db=db_session,
        class_id=str(cls.id),
        version_id=first["id"],
    )

    assert activated["id"] == first["id"]
    assert activated["is_active"] is True
    versions = TeachingDesignService.list_versions(db_session, str(cls.id))
    assert versions[0]["id"] == first["id"]
    assert any(item["id"] == second["id"] and item["is_active"] is False for item in versions)


def test_create_corrected_version_creates_new_active_record_with_lineage(db_session):
    teacher, cls = _teacher_class(db_session)
    base = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload={
            "course_title": "人工智能导论",
            "knowledge_points": ["生成式AI"],
            "learning_objectives": ["目标一"],
            "capability_targets": ["表达"],
            "debate_focuses": ["焦点一"],
        },
        version_name="v1",
        title="第一版",
        source_type="upload",
        source_filename="origin.docx",
        source_file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        source_file_size=512,
    )

    corrected = TeachingDesignService.create_corrected_version(
        db=db_session,
        class_id=str(cls.id),
        version_id=base["id"],
        created_by=str(teacher.id),
        extracted_payload={
            "course_title": "人工智能导论",
            "knowledge_points": ["生成式AI", "课堂评价"],
            "learning_objectives": ["目标一", "目标二"],
            "capability_targets": ["表达", "逻辑"],
            "debate_focuses": ["焦点一", "焦点二"],
        },
        correction_notes="教师修正了知识点和目标字段",
    )

    assert corrected["source_type"] == "corrected"
    assert corrected["derived_from_version_id"] == base["id"]
    assert corrected["correction_notes"] == "教师修正了知识点和目标字段"
    assert corrected["source_filename"] == "origin.docx"
    assert corrected["is_active"] is True
