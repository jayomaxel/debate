import uuid
from datetime import datetime

import pytest

from models.class_model import Class
from models.debate import Debate
from models.teaching_design import TopicRecommendationItem, TopicRecommendationRun
from models.user import User
from services.teaching_design_service import TeachingDesignService
from services.topic_recommendation_service import TopicRecommendationService


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
        name="Topic Class",
        code=f"T{uuid.uuid4().hex[:8]}",
        teacher_id=teacher.id,
    )
    db_session.add(cls)
    db_session.commit()
    return teacher, cls


def _design_payload():
    return {
        "course_title": "人工智能导论",
        "chapter_theme": "生成式AI与教育",
        "learning_objectives": ["理解生成式AI的课堂价值", "训练立场论证"],
        "knowledge_points": ["生成式AI", "课堂评价", "学习迁移"],
        "key_difficulties": ["工具依赖风险"],
        "capability_targets": ["批判性思维", "口头表达"],
        "grade_level": "本科二年级",
        "time_constraints": "2课时",
        "debate_focuses": ["价值权衡", "应用边界"],
        "forbidden_boundaries": ["脱离课程目标的纯社会热点"],
        "source_summary": "本章关注生成式AI在课堂中的应用与治理。",
    }


def _seed_adopted_debate(
    db_session,
    *,
    cls: Class,
    teacher: User,
    run: TopicRecommendationRun,
    item: TopicRecommendationItem,
    topic_source: str,
    mode: str,
    created_at: datetime,
):
    debate = Debate(
        id=uuid.uuid4(),
        topic=item.topic_text if topic_source == "ai_recommended" else f"{item.topic_text}（调整）",
        description="topic adoption test",
        duration=20,
        invitation_code=f"I{uuid.uuid4().hex[:5].upper()}",
        class_id=cls.id,
        teacher_id=teacher.id,
        status="draft",
        mode=mode,
        report={
            "__room_meta": {
                "debate_config_meta": {
                    "topic_recommendation_run_id": str(run.id),
                    "selected_topic_candidate_id": str(item.id),
                    "topic_source": topic_source,
                }
            }
        },
        created_at=created_at,
    )
    db_session.add(debate)
    db_session.flush()
    return debate


@pytest.mark.asyncio
async def test_generate_topic_recommendations_returns_validated_candidates(db_session, monkeypatch):
    teacher, cls = _teacher_class(db_session)
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="当前教学设计",
    )

    async def fake_request_llm_json(_db, *, messages, temperature=0.2, max_tokens=1200):
        assert messages
        return (
            """
            {"candidates":[
              {
                "topic_text":"生成式AI进入课堂后，教师评价应更看重过程思辨还是结果产出？",
                "course_objectives":["理解生成式AI的课堂价值"],
                "knowledge_points":["课堂评价","生成式AI"],
                "classroom_scene":"课堂辩论",
                "debatability_reason":"该题存在清晰的评价导向分歧。",
                "difficulty_level":"medium",
                "recommendation_reason":"能直接对应本章的评价与应用边界讨论。",
                "source_basis":["课程：人工智能导论","章节：生成式AI与教育"]
              },
              {
                "topic_text":"在生成式AI辅助学习中，课堂更应优先培养工具使用效率还是独立论证能力？",
                "course_objectives":["训练立场论证"],
                "knowledge_points":["学习迁移","生成式AI"],
                "classroom_scene":"课堂辩论",
                "debatability_reason":"该题具有清晰的能力培养取向冲突。",
                "difficulty_level":"medium",
                "recommendation_reason":"适合连接课程知识与能力训练目标。",
                "source_basis":["课程：人工智能导论"]
              },
              {
                "topic_text":"围绕生成式AI教学应用，课堂规则应优先强调开放探索还是使用约束？",
                "course_objectives":["理解生成式AI的课堂价值"],
                "knowledge_points":["生成式AI","课堂评价"],
                "classroom_scene":"课堂辩论",
                "debatability_reason":"该题可以形成治理与创新之间的立场碰撞。",
                "difficulty_level":"high",
                "recommendation_reason":"能够覆盖课程中的应用边界与治理讨论。",
                "source_basis":["章节：生成式AI与教育"]
              }
            ]}
            """,
            "llm",
        )

    monkeypatch.setattr(TopicRecommendationService, "_request_llm_json", fake_request_llm_json)

    result = await TopicRecommendationService.generate_recommendations(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        teaching_design_version_id=design["id"],
        mode="competition",
        activity_focus={"classroom_scene": "课堂辩论"},
        preferred_count=3,
    )

    assert result["status"] == "ready"
    assert result["legacy_status"] == "ready"
    assert result["teaching_design_status"] == "available"
    assert result["generation_quality"] == "validated"
    assert result["generation_source"] == "llm"
    assert result["run_id"] == result["recommendation_run_id"]
    assert result["teaching_design_version_id"] == design["id"]
    assert result["activity_focus"]["classroom_scene"] == "课堂辩论"
    assert len(result["candidates"]) == 3
    assert "mapped_course_objectives" in result["candidates"][0]
    assert "mapped_knowledge_points" in result["candidates"][0]
    assert "recommended_classroom_scene" in result["candidates"][0]
    assert "evidence_basis" in result["candidates"][0]

    persisted_run = db_session.query(TopicRecommendationRun).filter(
        TopicRecommendationRun.id == uuid.UUID(result["run_id"])
    ).one()
    assert persisted_run.preferred_count == 3
    assert len(persisted_run.items) == 3


@pytest.mark.asyncio
async def test_generate_topic_recommendations_returns_unavailable_without_teaching_design(db_session):
    teacher, cls = _teacher_class(db_session)

    result = await TopicRecommendationService.generate_recommendations(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
    )

    assert result["status"] == "unavailable"
    assert result["legacy_status"] == "unavailable"
    assert result["teaching_design_status"] == "missing"
    assert result["run_id"] is None
    assert result["candidates"] == []


@pytest.mark.asyncio
async def test_generate_topic_recommendations_uses_fallback_after_llm_failures(db_session, monkeypatch):
    teacher, cls = _teacher_class(db_session)
    TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
    )

    call_count = {"value": 0}

    async def fake_request_llm_json(_db, *, messages, temperature=0.2, max_tokens=1200):
        call_count["value"] += 1
        if call_count["value"] == 1:
            return "this is not json", "llm"
        raise ValueError("repair failed")

    monkeypatch.setattr(TopicRecommendationService, "_request_llm_json", fake_request_llm_json)

    result = await TopicRecommendationService.generate_recommendations(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        preferred_count=4,
        difficulty_preference="mixed",
    )

    assert result["status"] == "ready"
    assert result["legacy_status"] == "ready"
    assert result["generation_quality"] == "fallback"
    assert result["generation_source"] == "fallback"
    assert result["retry_count"] == 2
    assert len(result["candidates"]) >= 3
    assert any("模板化" in warning for warning in result["warnings"])


@pytest.mark.asyncio
async def test_generate_topic_recommendations_returns_partial_when_teaching_design_is_incomplete(db_session, monkeypatch):
    teacher, cls = _teacher_class(db_session)
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload={
            "course_title": "人工智能导论",
            "knowledge_points": ["生成式AI"],
            "learning_objectives": ["理解课堂应用边界"],
        },
        version_name="v-partial",
        title="部分抽取结果",
    )

    async def fake_request_llm_json(_db, *, messages, temperature=0.2, max_tokens=1200):
        return (
            """
            {"candidates":[
              {
                "topic_text":"课堂中是否应限制生成式AI直接代写？",
                "course_objectives":["理解课堂应用边界"],
                "knowledge_points":["生成式AI"],
                "classroom_scene":"课堂辩论",
                "debatability_reason":"题目具有明确立场冲突。",
                "difficulty_level":"medium",
                "recommendation_reason":"能直接对应当前残缺但仍可用的教学设计重点。",
                "source_basis":["课程：人工智能导论"]
              },
              {
                "topic_text":"生成式AI进入课堂后，教师更应强调过程评价还是结果评价？",
                "course_objectives":["理解课堂应用边界"],
                "knowledge_points":["生成式AI"],
                "classroom_scene":"课堂辩论",
                "debatability_reason":"题目可形成评价导向冲突。",
                "difficulty_level":"medium",
                "recommendation_reason":"能支撑教学讨论。",
                "source_basis":["课程：人工智能导论"]
              },
              {
                "topic_text":"在生成式AI辅助学习中，学生应优先提升效率还是独立论证能力？",
                "course_objectives":["理解课堂应用边界"],
                "knowledge_points":["生成式AI"],
                "classroom_scene":"课堂辩论",
                "debatability_reason":"题目存在清晰价值取向分歧。",
                "difficulty_level":"medium",
                "recommendation_reason":"能够支撑辩论式课堂活动。",
                "source_basis":["课程：人工智能导论"]
              }
            ]}
            """,
            "llm",
        )

    monkeypatch.setattr(TopicRecommendationService, "_request_llm_json", fake_request_llm_json)

    result = await TopicRecommendationService.generate_recommendations(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        teaching_design_version_id=design["id"],
        preferred_count=3,
    )

    assert result["status"] == "partial"
    assert result["legacy_status"] == "partial"
    assert result["teaching_design_status"] == "partial"
    assert any("抽取结果不完整" in warning for warning in result["warnings"])


@pytest.mark.asyncio
async def test_generate_topic_recommendations_rejects_unknown_teaching_design_version(db_session):
    teacher, cls = _teacher_class(db_session)

    with pytest.raises(ValueError, match="教学设计版本不存在"):
        await TopicRecommendationService.generate_recommendations(
            db=db_session,
            class_id=str(cls.id),
            created_by=str(teacher.id),
            teaching_design_version_id=str(uuid.uuid4()),
        )


@pytest.mark.asyncio
async def test_generate_topic_recommendations_rejects_unknown_regenerate_source_run(db_session):
    teacher, cls = _teacher_class(db_session)
    TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
    )

    with pytest.raises(ValueError, match="待重新生成的候选辩题记录不存在"):
        await TopicRecommendationService.generate_recommendations(
            db=db_session,
            class_id=str(cls.id),
            created_by=str(teacher.id),
            regenerate_from_run_id=str(uuid.uuid4()),
        )


@pytest.mark.asyncio
async def test_generate_topic_recommendations_inherits_parent_run_context_on_regenerate(db_session, monkeypatch):
    teacher, cls = _teacher_class(db_session)
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="当前教学设计",
    )

    parent_run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="teaching",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        retry_count=0,
        preferred_count=5,
        difficulty_preference="high",
        request_payload={
            "activity_focus": {
                "chapter_focus": "第3章",
                "training_focus": "价值权衡",
                "classroom_scene": "研讨课",
            },
            "objective": ["训练价值判断"],
            "knowledge_points": ["生成式AI治理"],
            "support_document_ids": ["doc-parent-1", "doc-parent-2"],
        },
        context_snapshot={},
        warnings=[],
    )
    db_session.add(parent_run)
    db_session.commit()

    captured = {}

    async def fake_request_llm_json(_db, *, messages, temperature=0.2, max_tokens=1200):
        payload = messages[1]["content"]
        captured["payload"] = payload
        return (
            """
            {"candidates":[
              {
                "topic_text":"生成式AI课堂治理中，应优先强调开放创新还是风险约束？",
                "course_objectives":["训练价值判断"],
                "knowledge_points":["生成式AI治理"],
                "classroom_scene":"研讨课",
                "debatability_reason":"该题存在清晰价值冲突。",
                "difficulty_level":"high",
                "recommendation_reason":"延续上一轮教学设计与活动聚焦。",
                "source_basis":["课程：人工智能导论"]
              },
              {
                "topic_text":"围绕生成式AI治理，课堂讨论应优先追求规范统一还是情境弹性？",
                "course_objectives":["训练价值判断"],
                "knowledge_points":["生成式AI治理"],
                "classroom_scene":"研讨课",
                "debatability_reason":"该题可形成规范与情境之间的分歧。",
                "difficulty_level":"high",
                "recommendation_reason":"适合延续上一轮训练焦点。",
                "source_basis":["课程：人工智能导论"]
              },
              {
                "topic_text":"在生成式AI教学应用中，教师应优先提升制度约束还是学习者自治？",
                "course_objectives":["训练价值判断"],
                "knowledge_points":["生成式AI治理"],
                "classroom_scene":"研讨课",
                "debatability_reason":"该题可引出治理取向上的对立。",
                "difficulty_level":"high",
                "recommendation_reason":"能直接复用上一轮上下文。",
                "source_basis":["课程：人工智能导论"]
              }
            ]}
            """,
            "llm",
        )

    monkeypatch.setattr(TopicRecommendationService, "_request_llm_json", fake_request_llm_json)

    result = await TopicRecommendationService.generate_recommendations(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        regenerate_from_run_id=str(parent_run.id),
    )

    assert result["status"] == "ready"
    assert result["mode"] == "teaching"
    assert result["activity_focus"]["chapter_focus"] == "第3章"
    assert result["activity_focus"]["training_focus"] == "价值权衡"
    assert result["teaching_design_version_id"] == design["id"]

    import json

    llm_payload = json.loads(captured["payload"])
    assert llm_payload["preferred_count"] == 5
    assert llm_payload["difficulty_preference"] == "high"
    assert llm_payload["context"]["mode"] == "teaching"
    assert llm_payload["context"]["activity_focus"]["chapter_focus"] == "第3章"
    assert llm_payload["context"]["activity_focus"]["classroom_scene"] == "研讨课"
    assert "训练价值判断" in llm_payload["context"]["learning_objectives"]
    assert "生成式AI治理" in llm_payload["context"]["knowledge_points"]


def test_list_topic_recommendation_runs_returns_latest_first(db_session):
    teacher, cls = _teacher_class(db_session)
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="当前教学设计",
    )

    older_run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        retry_count=0,
        preferred_count=4,
        difficulty_preference="medium",
        request_payload={"activity_focus": {"classroom_scene": "课堂辩论"}},
        context_snapshot={},
        warnings=[],
        created_at=datetime(2026, 1, 1, 10, 0, 0),
    )
    newer_run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="teaching",
        status="partial",
        teaching_design_status="partial",
        provider="fallback",
        generation_quality="fallback",
        retry_count=2,
        preferred_count=5,
        difficulty_preference="high",
        request_payload={"activity_focus": {"classroom_scene": "研讨课"}},
        context_snapshot={},
        warnings=["partial"],
        created_at=datetime(2026, 1, 2, 10, 0, 0),
    )
    db_session.add_all([older_run, newer_run])
    db_session.flush()
    db_session.add_all(
        [
            TopicRecommendationItem(
                run_id=older_run.id,
                candidate_order=1,
                topic_text="older-1",
                course_objectives=["o1"],
                knowledge_points=["k1"],
                classroom_scene="课堂辩论",
                debatability_reason="r1",
                difficulty_level="medium",
                recommendation_reason="rr1",
                source_basis=["s1"],
                quality_score=80.0,
                quality_flags=[],
            ),
            TopicRecommendationItem(
                run_id=newer_run.id,
                candidate_order=1,
                topic_text="newer-1",
                course_objectives=["o2"],
                knowledge_points=["k2"],
                classroom_scene="研讨课",
                debatability_reason="r2",
                difficulty_level="high",
                recommendation_reason="rr2",
                source_basis=["s2"],
                quality_score=90.0,
                quality_flags=[],
            ),
            TopicRecommendationItem(
                run_id=newer_run.id,
                candidate_order=2,
                topic_text="newer-2",
                course_objectives=["o3"],
                knowledge_points=["k3"],
                classroom_scene="研讨课",
                debatability_reason="r3",
                difficulty_level="high",
                recommendation_reason="rr3",
                source_basis=["s3"],
                quality_score=88.0,
                quality_flags=[],
            ),
        ]
    )
    db_session.commit()

    runs = TopicRecommendationService.list_runs(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        limit=10,
    )

    assert len(runs) == 2
    assert runs[0]["run_id"] == str(newer_run.id)
    assert runs[0]["status"] == "partial"
    assert runs[0]["candidate_count"] == 2
    assert runs[0]["candidate_topics"] == ["newer-1", "newer-2"]
    assert runs[1]["run_id"] == str(older_run.id)
    assert runs[1]["status"] == "ready"


def test_list_topic_recommendation_runs_includes_adoption_summary(db_session):
    teacher, cls = _teacher_class(db_session)
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="current design",
    )

    run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
    )
    db_session.add(run)
    db_session.flush()
    item_1 = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run.id,
        candidate_order=1,
        topic_text="candidate-1",
        course_objectives=["o1"],
        knowledge_points=["k1"],
        classroom_scene="scene",
        debatability_reason="r1",
        difficulty_level="medium",
        recommendation_reason="rr1",
        source_basis=["s1"],
        quality_score=80.0,
        quality_flags=[],
    )
    item_2 = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run.id,
        candidate_order=2,
        topic_text="candidate-2",
        course_objectives=["o2"],
        knowledge_points=["k2"],
        classroom_scene="scene",
        debatability_reason="r2",
        difficulty_level="medium",
        recommendation_reason="rr2",
        source_basis=["s2"],
        quality_score=82.0,
        quality_flags=[],
    )
    db_session.add_all([item_1, item_2])
    db_session.flush()

    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run,
        item=item_1,
        topic_source="ai_recommended",
        mode="teacher_assigned",
        created_at=datetime(2026, 1, 3, 10, 0, 0),
    )
    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run,
        item=item_2,
        topic_source="ai_recommended_edited",
        mode="teacher_reserved",
        created_at=datetime(2026, 1, 4, 10, 0, 0),
    )
    db_session.commit()

    runs = TopicRecommendationService.list_runs(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        limit=10,
    )

    assert len(runs) == 1
    summary = runs[0]["adoption_summary"]
    assert summary["total_adoptions"] == 2
    assert summary["direct_adoptions"] == 1
    assert summary["edited_adoptions"] == 1
    assert summary["debate_adoptions"] == 1
    assert summary["reservation_adoptions"] == 1
    assert summary["distinct_candidates_adopted"] == 2
    assert summary["last_adopted_at"] == "2026-01-04T10:00:00"


def test_list_topic_recommendation_runs_filters_by_creator(db_session):
    teacher, cls = _teacher_class(db_session)
    other_teacher = _user(f"teacher_{uuid.uuid4().hex[:8]}", "Other Teacher", "teacher")
    db_session.add(other_teacher)
    db_session.flush()
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="当前教学设计",
    )

    own_run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
    )
    other_run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=other_teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
    )
    db_session.add_all([own_run, other_run])
    db_session.commit()

    runs = TopicRecommendationService.list_runs(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        limit=10,
    )

    assert len(runs) == 1
    assert runs[0]["run_id"] == str(own_run.id)


def test_get_topic_recommendation_run_returns_none_for_other_creator(db_session):
    teacher, cls = _teacher_class(db_session)
    other_teacher = _user(f"teacher_{uuid.uuid4().hex[:8]}", "Other Teacher", "teacher")
    db_session.add(other_teacher)
    db_session.flush()
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="当前教学设计",
    )

    run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
    )
    db_session.add(run)
    db_session.commit()

    result = TopicRecommendationService.get_run(
        db=db_session,
        run_id=str(run.id),
        created_by=str(other_teacher.id),
    )

    assert result is None


def test_get_topic_recommendation_run_includes_candidate_adoption_stats(db_session):
    teacher, cls = _teacher_class(db_session)
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="current design",
    )

    run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
    )
    db_session.add(run)
    db_session.flush()

    item_1 = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run.id,
        candidate_order=1,
        topic_text="candidate-1",
        course_objectives=["o1"],
        knowledge_points=["k1"],
        classroom_scene="scene",
        debatability_reason="r1",
        difficulty_level="medium",
        recommendation_reason="rr1",
        source_basis=["s1"],
        quality_score=80.0,
        quality_flags=[],
    )
    item_2 = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run.id,
        candidate_order=2,
        topic_text="candidate-2",
        course_objectives=["o2"],
        knowledge_points=["k2"],
        classroom_scene="scene",
        debatability_reason="r2",
        difficulty_level="medium",
        recommendation_reason="rr2",
        source_basis=["s2"],
        quality_score=82.0,
        quality_flags=[],
    )
    db_session.add_all([item_1, item_2])
    db_session.flush()

    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run,
        item=item_1,
        topic_source="ai_recommended",
        mode="teacher_assigned",
        created_at=datetime(2026, 1, 3, 10, 0, 0),
    )
    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run,
        item=item_1,
        topic_source="ai_recommended_edited",
        mode="teacher_reserved",
        created_at=datetime(2026, 1, 5, 10, 0, 0),
    )
    db_session.commit()

    result = TopicRecommendationService.get_run(
        db=db_session,
        run_id=str(run.id),
        created_by=str(teacher.id),
    )

    assert result is not None
    assert result["adoption_summary"]["total_adoptions"] == 2
    assert result["adoption_summary"]["distinct_candidates_adopted"] == 1

    candidate_1 = next(item for item in result["candidates"] if item["candidate_id"] == str(item_1.id))
    candidate_2 = next(item for item in result["candidates"] if item["candidate_id"] == str(item_2.id))

    assert candidate_1["adoption_stats"]["is_adopted"] is True
    assert candidate_1["adoption_stats"]["total_adoptions"] == 2
    assert candidate_1["adoption_stats"]["direct_adoptions"] == 1
    assert candidate_1["adoption_stats"]["edited_adoptions"] == 1
    assert candidate_1["adoption_stats"]["debate_adoptions"] == 1
    assert candidate_1["adoption_stats"]["reservation_adoptions"] == 1
    assert candidate_1["adoption_stats"]["last_adopted_at"] == "2026-01-05T10:00:00"

    assert candidate_2["adoption_stats"]["is_adopted"] is False
    assert candidate_2["adoption_stats"]["total_adoptions"] == 0


def test_get_class_analytics_returns_generation_and_adoption_stats(db_session):
    teacher, cls = _teacher_class(db_session)
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="current design",
    )

    run_a = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        retry_count=0,
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
        created_at=datetime(2026, 1, 2, 10, 0, 0),
    )
    run_b = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="teaching",
        status="partial",
        teaching_design_status="partial",
        provider="fallback",
        generation_quality="fallback",
        retry_count=2,
        preferred_count=5,
        request_payload={},
        context_snapshot={},
        warnings=["fallback"],
        created_at=datetime(2026, 1, 4, 10, 0, 0),
    )
    db_session.add_all([run_a, run_b])
    db_session.flush()

    item_a1 = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run_a.id,
        candidate_order=1,
        topic_text="run-a-1",
        course_objectives=["o1"],
        knowledge_points=["k1"],
        classroom_scene="scene",
        debatability_reason="r1",
        difficulty_level="medium",
        recommendation_reason="rr1",
        source_basis=["s1"],
        quality_score=80.0,
        quality_flags=[],
    )
    item_a2 = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run_a.id,
        candidate_order=2,
        topic_text="run-a-2",
        course_objectives=["o2"],
        knowledge_points=["k2"],
        classroom_scene="scene",
        debatability_reason="r2",
        difficulty_level="medium",
        recommendation_reason="rr2",
        source_basis=["s2"],
        quality_score=82.0,
        quality_flags=[],
    )
    item_b1 = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run_b.id,
        candidate_order=1,
        topic_text="run-b-1",
        course_objectives=["o3"],
        knowledge_points=["k3"],
        classroom_scene="scene",
        debatability_reason="r3",
        difficulty_level="high",
        recommendation_reason="rr3",
        source_basis=["s3"],
        quality_score=83.0,
        quality_flags=[],
    )
    db_session.add_all([item_a1, item_a2, item_b1])
    db_session.flush()

    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run_a,
        item=item_a1,
        topic_source="ai_recommended",
        mode="teacher_assigned",
        created_at=datetime(2026, 1, 5, 10, 0, 0),
    )
    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run_b,
        item=item_b1,
        topic_source="ai_recommended_edited",
        mode="teacher_reserved",
        created_at=datetime(2026, 1, 6, 10, 0, 0),
    )
    db_session.commit()

    analytics = TopicRecommendationService.get_class_analytics(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
    )

    assert analytics["class_id"] == str(cls.id)
    assert analytics["total_runs"] == 2
    assert analytics["total_candidates"] == 3
    assert analytics["adopted_run_count"] == 2
    assert analytics["adopted_candidate_count"] == 2
    assert analytics["total_adoptions"] == 2
    assert analytics["direct_adoptions"] == 1
    assert analytics["edited_adoptions"] == 1
    assert analytics["debate_adoptions"] == 1
    assert analytics["reservation_adoptions"] == 1
    assert analytics["run_adoption_rate"] == 1.0
    assert analytics["candidate_adoption_rate"] == 0.6667
    assert analytics["average_candidates_per_run"] == 1.5
    assert analytics["quality_counts"]["validated"] == 1
    assert analytics["quality_counts"]["fallback"] == 1
    assert analytics["quality_rates"]["validated_rate"] == 0.5
    assert analytics["quality_rates"]["fallback_rate"] == 0.5
    assert analytics["provider_counts"]["llm"] == 1
    assert analytics["provider_counts"]["fallback"] == 1
    assert analytics["status_counts"]["ready"] == 1
    assert analytics["status_counts"]["partial"] == 1
    assert len(analytics["version_breakdown"]) == 1
    assert analytics["version_breakdown"][0]["teaching_design_version_id"] == design["id"]
    assert analytics["latest_run_id"] == str(run_b.id)
    assert analytics["last_generated_at"] == "2026-01-04T10:00:00"
    assert analytics["last_adopted_at"] == "2026-01-06T10:00:00"


def test_get_dashboard_payload_returns_summary_quality_timeline_and_recent_runs(db_session):
    teacher, cls = _teacher_class(db_session)
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="current design",
    )

    run_a = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        retry_count=0,
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
        created_at=datetime(2026, 1, 2, 10, 0, 0),
    )
    run_b = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="fallback",
        generation_quality="fallback",
        retry_count=2,
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=["fallback"],
        created_at=datetime(2026, 1, 5, 10, 0, 0),
    )
    db_session.add_all([run_a, run_b])
    db_session.flush()

    item_a = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run_a.id,
        candidate_order=1,
        topic_text="run-a-1",
        course_objectives=["o1"],
        knowledge_points=["k1"],
        classroom_scene="scene",
        debatability_reason="r1",
        difficulty_level="medium",
        recommendation_reason="rr1",
        source_basis=["s1"],
        quality_score=80.0,
        quality_flags=[],
    )
    item_b = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run_b.id,
        candidate_order=1,
        topic_text="run-b-1",
        course_objectives=["o2"],
        knowledge_points=["k2"],
        classroom_scene="scene",
        debatability_reason="r2",
        difficulty_level="medium",
        recommendation_reason="rr2",
        source_basis=["s2"],
        quality_score=82.0,
        quality_flags=[],
    )
    db_session.add_all([item_a, item_b])
    db_session.flush()

    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run_a,
        item=item_a,
        topic_source="ai_recommended",
        mode="teacher_assigned",
        created_at=datetime(2026, 1, 3, 10, 0, 0),
    )
    db_session.commit()

    dashboard = TopicRecommendationService.get_dashboard_payload(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        recent_limit=2,
    )

    assert dashboard["class_id"] == str(cls.id)
    assert dashboard["summary"]["total_runs"] == 2
    assert dashboard["summary"]["total_adoptions"] == 1
    assert dashboard["quality"]["quality_counts"]["validated"] == 1
    assert dashboard["quality"]["quality_counts"]["fallback"] == 1
    assert dashboard["timeline"]["latest_run_id"] == str(run_b.id)
    assert dashboard["timeline"]["last_generated_at"] == "2026-01-05T10:00:00"
    assert dashboard["timeline"]["last_adopted_at"] == "2026-01-03T10:00:00"
    assert dashboard["timeline"]["latest_run"]["run_id"] == str(run_b.id)
    assert dashboard["timeline"]["latest_adopted_run"]["run_id"] == str(run_a.id)
    assert len(dashboard["recent_runs"]) == 2
    assert dashboard["recent_runs"][0]["run_id"] == str(run_b.id)


def test_time_filtered_history_analytics_and_dashboard(db_session):
    teacher, cls = _teacher_class(db_session)
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="current design",
    )

    old_run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
        created_at=datetime(2026, 1, 2, 10, 0, 0),
    )
    new_run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="fallback",
        generation_quality="fallback",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
        created_at=datetime(2026, 1, 8, 10, 0, 0),
    )
    db_session.add_all([old_run, new_run])
    db_session.flush()

    db_session.add_all(
        [
            TopicRecommendationItem(
                id=uuid.uuid4(),
                run_id=old_run.id,
                candidate_order=1,
                topic_text="old-run-topic",
                course_objectives=["o1"],
                knowledge_points=["k1"],
                classroom_scene="scene",
                debatability_reason="r1",
                difficulty_level="medium",
                recommendation_reason="rr1",
                source_basis=["s1"],
                quality_score=80.0,
                quality_flags=[],
            ),
            TopicRecommendationItem(
                id=uuid.uuid4(),
                run_id=new_run.id,
                candidate_order=1,
                topic_text="new-run-topic",
                course_objectives=["o2"],
                knowledge_points=["k2"],
                classroom_scene="scene",
                debatability_reason="r2",
                difficulty_level="medium",
                recommendation_reason="rr2",
                source_basis=["s2"],
                quality_score=82.0,
                quality_flags=[],
            ),
        ]
    )
    db_session.commit()

    date_from = "2026-01-05T00:00:00"
    date_to = "2026-01-10T00:00:00"

    runs = TopicRecommendationService.list_runs(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        limit=10,
        date_from=date_from,
        date_to=date_to,
    )
    assert len(runs) == 1
    assert runs[0]["run_id"] == str(new_run.id)

    analytics = TopicRecommendationService.get_class_analytics(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        date_from=date_from,
        date_to=date_to,
    )
    assert analytics["date_from"] == date_from
    assert analytics["date_to"] == date_to
    assert analytics["total_runs"] == 1
    assert analytics["quality_counts"]["fallback"] == 1
    assert analytics["latest_run_id"] == str(new_run.id)

    dashboard = TopicRecommendationService.get_dashboard_payload(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        recent_limit=5,
        date_from=date_from,
        date_to=date_to,
    )
    assert dashboard["date_from"] == date_from
    assert dashboard["date_to"] == date_to
    assert dashboard["summary"]["total_runs"] == 1
    assert len(dashboard["recent_runs"]) == 1
    assert dashboard["recent_runs"][0]["run_id"] == str(new_run.id)


def test_time_filtered_services_reject_invalid_range(db_session):
    teacher, cls = _teacher_class(db_session)

    with pytest.raises(ValueError, match="date_from 不能晚于 date_to"):
        TopicRecommendationService.get_class_analytics(
            db=db_session,
            class_id=str(cls.id),
            created_by=str(teacher.id),
            date_from="2026-01-10T00:00:00",
            date_to="2026-01-05T00:00:00",
        )


def test_dashboard_payload_includes_candidate_leaderboards(db_session):
    teacher, cls = _teacher_class(db_session)
    design = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="current design",
    )

    run = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
        created_at=datetime(2026, 1, 8, 10, 0, 0),
    )
    db_session.add(run)
    db_session.flush()

    item_a = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run.id,
        candidate_order=1,
        topic_text="candidate-a",
        course_objectives=["oa"],
        knowledge_points=["ka"],
        classroom_scene="scene",
        debatability_reason="ra",
        difficulty_level="medium",
        recommendation_reason="rra",
        source_basis=["sa"],
        quality_score=80.0,
        quality_flags=[],
    )
    item_b = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run.id,
        candidate_order=2,
        topic_text="candidate-b",
        course_objectives=["ob"],
        knowledge_points=["kb"],
        classroom_scene="scene",
        debatability_reason="rb",
        difficulty_level="medium",
        recommendation_reason="rrb",
        source_basis=["sb"],
        quality_score=82.0,
        quality_flags=[],
    )
    item_c = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run.id,
        candidate_order=3,
        topic_text="candidate-c",
        course_objectives=["oc"],
        knowledge_points=["kc"],
        classroom_scene="scene",
        debatability_reason="rc",
        difficulty_level="medium",
        recommendation_reason="rrc",
        source_basis=["sc"],
        quality_score=84.0,
        quality_flags=[],
    )
    db_session.add_all([item_a, item_b, item_c])
    db_session.flush()

    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run,
        item=item_a,
        topic_source="ai_recommended",
        mode="teacher_assigned",
        created_at=datetime(2026, 1, 9, 10, 0, 0),
    )
    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run,
        item=item_a,
        topic_source="ai_recommended_edited",
        mode="teacher_reserved",
        created_at=datetime(2026, 1, 10, 10, 0, 0),
    )
    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run,
        item=item_b,
        topic_source="ai_recommended_edited",
        mode="teacher_reserved",
        created_at=datetime(2026, 1, 11, 10, 0, 0),
    )
    db_session.commit()

    dashboard = TopicRecommendationService.get_dashboard_payload(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        recent_limit=5,
        leaderboard_limit=3,
    )

    top_adopted = dashboard["leaderboards"]["top_adopted_candidates"]
    top_edited = dashboard["leaderboards"]["top_edited_candidates"]

    assert len(top_adopted) == 3
    assert top_adopted[0]["candidate_id"] == str(item_a.id)
    assert top_adopted[0]["total_adoptions"] == 2
    assert top_adopted[1]["candidate_id"] == str(item_b.id)
    assert top_adopted[1]["total_adoptions"] == 1

    assert len(top_edited) == 3
    assert top_edited[0]["candidate_id"] == str(item_a.id)
    assert top_edited[0]["edited_adoptions"] == 1
    assert top_edited[1]["candidate_id"] == str(item_b.id)
    assert top_edited[1]["edited_adoptions"] == 1

    observations = dashboard["observations"]["high_quality_low_adoption_candidates"]
    assert len(observations) == 1
    assert observations[0]["candidate_id"] == str(item_c.id)
    assert observations[0]["quality_score"] == 84.0
    assert observations[0]["total_adoptions"] == 0

    edited_only = dashboard["observations"]["high_quality_edited_only_candidates"]
    assert len(edited_only) == 1
    assert edited_only[0]["candidate_id"] == str(item_b.id)
    assert edited_only[0]["quality_score"] == 82.0
    assert edited_only[0]["edited_adoptions"] == 1
    assert edited_only[0]["direct_adoptions"] == 0


def test_analytics_and_dashboard_include_teaching_design_version_breakdown(db_session):
    teacher, cls = _teacher_class(db_session)
    design_a = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="Design A",
    )
    design_b = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v2",
        title="Design B",
    )

    run_a = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design_a["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
        created_at=datetime(2026, 1, 2, 10, 0, 0),
    )
    run_b = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design_b["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="fallback",
        generation_quality="fallback",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
        created_at=datetime(2026, 1, 4, 10, 0, 0),
    )
    db_session.add_all([run_a, run_b])
    db_session.flush()

    item_a = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run_a.id,
        candidate_order=1,
        topic_text="design-a-topic",
        course_objectives=["oa"],
        knowledge_points=["ka"],
        classroom_scene="scene",
        debatability_reason="ra",
        difficulty_level="medium",
        recommendation_reason="rra",
        source_basis=["sa"],
        quality_score=80.0,
        quality_flags=[],
    )
    item_b = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run_b.id,
        candidate_order=1,
        topic_text="design-b-topic",
        course_objectives=["ob"],
        knowledge_points=["kb"],
        classroom_scene="scene",
        debatability_reason="rb",
        difficulty_level="medium",
        recommendation_reason="rrb",
        source_basis=["sb"],
        quality_score=82.0,
        quality_flags=[],
    )
    db_session.add_all([item_a, item_b])
    db_session.flush()

    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run_b,
        item=item_b,
        topic_source="ai_recommended",
        mode="teacher_assigned",
        created_at=datetime(2026, 1, 5, 10, 0, 0),
    )
    db_session.commit()

    analytics = TopicRecommendationService.get_class_analytics(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
    )
    assert len(analytics["version_breakdown"]) == 2
    version_a = next(
        item for item in analytics["version_breakdown"]
        if item["teaching_design_version_id"] == design_a["id"]
    )
    assert version_a["total_runs"] == 1
    assert version_a["total_adoptions"] == 0
    version_b = next(
        item for item in analytics["version_breakdown"]
        if item["teaching_design_version_id"] == design_b["id"]
    )
    assert version_b["total_runs"] == 1
    assert version_b["total_adoptions"] == 1
    assert version_b["run_adoption_rate"] == 1.0

    dashboard = TopicRecommendationService.get_dashboard_payload(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
    )
    assert len(dashboard["quality"]["version_breakdown"]) == 2
    assert any(
        item["teaching_design_version_id"] == design_b["id"]
        for item in dashboard["quality"]["version_breakdown"]
    )
    comparison = dashboard["quality"]["version_comparison_summary"]
    assert comparison is not None
    assert comparison["current_version"]["teaching_design_version_id"] == design_b["id"]
    assert comparison["previous_version"]["teaching_design_version_id"] == design_a["id"]
    assert comparison["delta"]["total_adoptions"] == 1
    assert comparison["delta"]["direct_adoptions"] == 1
    assert comparison["delta"]["edited_adoptions"] == 0
    assert comparison["delta"]["run_adoption_rate"] == 1.0
    assert comparison["delta"]["direct_adoption_share"] == 1.0


def test_get_version_comparison_payload_supports_default_and_explicit_pair(db_session):
    teacher, cls = _teacher_class(db_session)
    design_a = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v1",
        title="Design A",
    )
    design_b = TeachingDesignService.upsert_current_version(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        extracted_payload=_design_payload(),
        version_name="v2",
        title="Design B",
    )

    run_a = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design_a["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="llm",
        generation_quality="validated",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
        created_at=datetime(2026, 1, 2, 10, 0, 0),
    )
    run_b = TopicRecommendationRun(
        id=uuid.uuid4(),
        class_id=cls.id,
        teaching_design_version_id=uuid.UUID(design_b["id"]),
        created_by=teacher.id,
        mode="competition",
        status="ready",
        teaching_design_status="available",
        provider="fallback",
        generation_quality="fallback",
        preferred_count=4,
        request_payload={},
        context_snapshot={},
        warnings=[],
        created_at=datetime(2026, 1, 4, 10, 0, 0),
    )
    db_session.add_all([run_a, run_b])
    db_session.flush()

    item_a = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run_a.id,
        candidate_order=1,
        topic_text="design-a-topic",
        course_objectives=["oa"],
        knowledge_points=["ka"],
        classroom_scene="scene",
        debatability_reason="ra",
        difficulty_level="medium",
        recommendation_reason="rra",
        source_basis=["sa"],
        quality_score=80.0,
        quality_flags=[],
    )
    item_b = TopicRecommendationItem(
        id=uuid.uuid4(),
        run_id=run_b.id,
        candidate_order=1,
        topic_text="design-b-topic",
        course_objectives=["ob"],
        knowledge_points=["kb"],
        classroom_scene="scene",
        debatability_reason="rb",
        difficulty_level="medium",
        recommendation_reason="rrb",
        source_basis=["sb"],
        quality_score=82.0,
        quality_flags=[],
    )
    db_session.add_all([item_a, item_b])
    db_session.flush()

    _seed_adopted_debate(
        db_session,
        cls=cls,
        teacher=teacher,
        run=run_b,
        item=item_b,
        topic_source="ai_recommended",
        mode="teacher_assigned",
        created_at=datetime(2026, 1, 5, 10, 0, 0),
    )
    db_session.commit()

    payload = TopicRecommendationService.get_version_comparison_payload(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
    )
    assert payload["version_comparison_summary"] is not None
    assert payload["version_comparison_summary"]["current_version"]["teaching_design_version_id"] == design_b["id"]
    assert payload["version_comparison_summary"]["previous_version"]["teaching_design_version_id"] == design_a["id"]

    explicit_payload = TopicRecommendationService.get_version_comparison_payload(
        db=db_session,
        class_id=str(cls.id),
        created_by=str(teacher.id),
        current_version_id=design_b["id"],
        previous_version_id=design_a["id"],
    )
    assert explicit_payload["version_comparison_summary"] is not None
    assert explicit_payload["version_comparison_summary"]["current_version"]["teaching_design_version_id"] == design_b["id"]
    assert explicit_payload["version_comparison_summary"]["previous_version"]["teaching_design_version_id"] == design_a["id"]

    with pytest.raises(ValueError, match="current_version_id 不存在于当前统计范围内"):
        TopicRecommendationService.get_version_comparison_payload(
            db=db_session,
            class_id=str(cls.id),
            created_by=str(teacher.id),
            current_version_id=str(uuid.uuid4()),
        )
