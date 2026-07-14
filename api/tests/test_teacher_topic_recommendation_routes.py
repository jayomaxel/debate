import uuid
import sys
import types
from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

if "uvicorn" not in sys.modules:
    sys.modules["uvicorn"] = types.ModuleType("uvicorn")

from database import get_db
from models.class_model import Class
from models.debate import Debate
from models.teaching_design import TopicRecommendationItem, TopicRecommendationRun
from models.user import User
from routers import teacher
from services.teaching_design_service import TeachingDesignService
from testing_db import create_test_engine, create_test_schema, drop_test_schema
from utils.security import create_token


BASE_URL = "http://test"
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_teacher_topic_recommendation_routes.db"
engine = create_test_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
app = FastAPI()
app.include_router(teacher.router)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    create_test_schema(engine)
    yield
    drop_test_schema(engine)


def _design_payload():
    return {
        "course_title": "AI Literacy",
        "chapter_theme": "Generative AI and education",
        "learning_objectives": ["understand classroom uses", "practice argumentation"],
        "knowledge_points": ["generative ai", "assessment", "transfer"],
        "key_difficulties": ["tool dependence"],
        "capability_targets": ["critical thinking", "oral expression"],
        "grade_level": "undergraduate year 2",
        "time_constraints": "2 sessions",
        "debate_focuses": ["value tradeoff", "use boundary"],
        "forbidden_boundaries": ["off-topic social gossip"],
        "source_summary": "This unit focuses on classroom application and governance.",
    }


def _seed_teacher(suffix: str) -> tuple[str, dict]:
    account = f"teacher_topic_route_{suffix}"
    db = TestingSessionLocal()
    try:
        teacher = User(
            id=uuid.uuid4(),
            account=account,
            password_hash="test-hash",
            user_type="teacher",
            name=f"Teacher {suffix}",
            email=f"{account}@test.com",
            phone="13800000000",
        )
        db.add(teacher)
        db.commit()
        token = create_token({"sub": str(teacher.id), "user_type": "teacher"})
        return str(teacher.id), {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _seed_class(teacher_id: str, suffix: str) -> str:
    db = TestingSessionLocal()
    try:
        class_id = uuid.uuid4()
        cls = Class(
            id=class_id,
            name=f"topic-route-class-{suffix}",
            code=f"TR{suffix[:6].upper()}",
            teacher_id=uuid.UUID(teacher_id),
        )
        db.add(cls)
        db.commit()
        return str(class_id)
    finally:
        db.close()


def _seed_topic_run(class_id: str, teacher_id: str) -> tuple[str, str]:
    db = TestingSessionLocal()
    try:
        cls = db.query(Class).filter(Class.id == uuid.UUID(class_id)).one()

        design = TeachingDesignService.upsert_current_version(
            db=db,
            class_id=str(cls.id),
            created_by=teacher_id,
            extracted_payload=_design_payload(),
            version_name="v1",
            title="Current teaching design",
        )

        run = TopicRecommendationRun(
            id=uuid.uuid4(),
            class_id=cls.id,
            teaching_design_version_id=uuid.UUID(design["id"]),
            created_by=uuid.UUID(teacher_id),
            mode="competition",
            status="ready",
            teaching_design_status="available",
            provider="llm",
            generation_quality="validated",
            retry_count=0,
            preferred_count=4,
            difficulty_preference="medium",
            request_payload={"activity_focus": {"classroom_scene": "in-class debate"}},
            context_snapshot={},
            warnings=[],
            created_at=datetime(2026, 1, 3, 10, 0, 0),
        )
        db.add(run)
        db.flush()
        db.add_all(
            [
                TopicRecommendationItem(
                    run_id=run.id,
                    candidate_order=1,
                    topic_text="After generative AI enters the classroom, should assessment focus more on process than on final output?",
                    course_objectives=["understand classroom uses"],
                    knowledge_points=["assessment", "generative ai"],
                    classroom_scene="in-class debate",
                    debatability_reason="The prompt contains a clear value tradeoff.",
                    difficulty_level="medium",
                    recommendation_reason="Directly matches the unit focus on assessment and application boundary.",
                    source_basis=["course theme"],
                    quality_score=88.0,
                    quality_flags=[],
                ),
                TopicRecommendationItem(
                    run_id=run.id,
                    candidate_order=2,
                    topic_text="In AI-assisted learning, should classrooms prioritize tool-use efficiency or independent argumentation ability?",
                    course_objectives=["practice argumentation"],
                    knowledge_points=["transfer", "generative ai"],
                    classroom_scene="in-class debate",
                    debatability_reason="The prompt creates a meaningful capability tradeoff.",
                    difficulty_level="medium",
                    recommendation_reason="It links course knowledge with argument training goals.",
                    source_basis=["course theme"],
                    quality_score=86.0,
                    quality_flags=[],
                ),
            ]
        )
        db.commit()
        return str(run.id), design["id"]
    finally:
        db.close()


def _seed_adopted_debate(
    class_id: str,
    teacher_id: str,
    run_id: str,
    candidate_id: str,
    *,
    topic_text: str,
    topic_source: str,
    mode: str,
    created_at: datetime,
):
    db = TestingSessionLocal()
    try:
        debate = Debate(
            id=uuid.uuid4(),
            topic=topic_text if topic_source == "ai_recommended" else f"{topic_text} (edited)",
            description="route analytics test",
            duration=20,
            invitation_code=f"R{uuid.uuid4().hex[:5].upper()}",
            class_id=uuid.UUID(class_id),
            teacher_id=uuid.UUID(teacher_id),
            status="draft",
            mode=mode,
            report={
                "__room_meta": {
                    "debate_config_meta": {
                        "topic_recommendation_run_id": run_id,
                        "selected_topic_candidate_id": candidate_id,
                        "topic_source": topic_source,
                    }
                }
            },
            created_at=created_at,
        )
        db.add(debate)
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_teacher_can_list_topic_recommendation_history_and_get_detail():
    suffix = uuid.uuid4().hex[:8]
    teacher_id, headers = _seed_teacher(suffix)
    class_id = _seed_class(teacher_id, suffix)
    run_id, design_id = _seed_topic_run(class_id, teacher_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["run_id"] == run_id
        assert data[0]["teaching_design_version_id"] == design_id
        assert data[0]["candidate_count"] == 2
        assert len(data[0]["candidate_topics"]) == 2

        response = await client.get(
            f"/api/teacher/topic-recommendations/{run_id}",
            headers=headers,
        )
        assert response.status_code == 200
        detail = response.json()["data"]
        assert detail["run_id"] == run_id
        assert detail["teaching_design_version_id"] == design_id
        assert len(detail["candidates"]) == 2
        assert "mapped_course_objectives" in detail["candidates"][0]


@pytest.mark.asyncio
async def test_teacher_cannot_access_other_teacher_topic_recommendation_history_or_detail():
    suffix_a = uuid.uuid4().hex[:8]
    suffix_b = uuid.uuid4().hex[:8]
    teacher_a_id, headers_a = _seed_teacher(suffix_a)
    _, headers_b = _seed_teacher(suffix_b)
    class_id = _seed_class(teacher_a_id, suffix_a)
    run_id, _ = _seed_topic_run(class_id, teacher_a_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations",
            headers=headers_b,
        )
        assert response.status_code == 403

        response = await client.get(
            f"/api/teacher/topic-recommendations/{run_id}",
            headers=headers_b,
        )
        assert response.status_code == 404

        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations",
            headers=headers_a,
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_teacher_can_get_topic_recommendation_analytics():
    suffix = uuid.uuid4().hex[:8]
    teacher_id, headers = _seed_teacher(suffix)
    class_id = _seed_class(teacher_id, suffix)
    run_id, _ = _seed_topic_run(class_id, teacher_id)

    db = TestingSessionLocal()
    try:
        first_candidate = (
            db.query(TopicRecommendationItem)
            .filter(TopicRecommendationItem.run_id == uuid.UUID(run_id))
            .order_by(TopicRecommendationItem.candidate_order.asc())
            .first()
        )
        assert first_candidate is not None
        candidate_id = str(first_candidate.id)
        topic_text = first_candidate.topic_text
    finally:
        db.close()

    _seed_adopted_debate(
        class_id,
        teacher_id,
        run_id,
        candidate_id,
        topic_text=topic_text,
        topic_source="ai_recommended",
        mode="teacher_assigned",
        created_at=datetime(2026, 1, 6, 10, 0, 0),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations/analytics",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["class_id"] == class_id
        assert data["total_runs"] == 1
        assert data["total_candidates"] == 2
        assert data["adopted_run_count"] == 1
        assert data["adopted_candidate_count"] == 1
        assert data["total_adoptions"] == 1
        assert data["direct_adoptions"] == 1
        assert data["edited_adoptions"] == 0
        assert data["debate_adoptions"] == 1
        assert data["reservation_adoptions"] == 0
        assert data["run_adoption_rate"] == 1.0
        assert data["candidate_adoption_rate"] == 0.5


@pytest.mark.asyncio
async def test_teacher_cannot_access_other_teacher_topic_recommendation_analytics():
    suffix_a = uuid.uuid4().hex[:8]
    suffix_b = uuid.uuid4().hex[:8]
    teacher_a_id, _ = _seed_teacher(suffix_a)
    _, headers_b = _seed_teacher(suffix_b)
    class_id = _seed_class(teacher_a_id, suffix_a)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations/analytics",
            headers=headers_b,
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_teacher_can_get_topic_recommendation_dashboard():
    suffix = uuid.uuid4().hex[:8]
    teacher_id, headers = _seed_teacher(suffix)
    class_id = _seed_class(teacher_id, suffix)
    run_id, _ = _seed_topic_run(class_id, teacher_id)

    db = TestingSessionLocal()
    try:
        first_candidate = (
            db.query(TopicRecommendationItem)
            .filter(TopicRecommendationItem.run_id == uuid.UUID(run_id))
            .order_by(TopicRecommendationItem.candidate_order.asc())
            .first()
        )
        assert first_candidate is not None
        candidate_id = str(first_candidate.id)
        topic_text = first_candidate.topic_text
    finally:
        db.close()

    _seed_adopted_debate(
        class_id,
        teacher_id,
        run_id,
        candidate_id,
        topic_text=topic_text,
        topic_source="ai_recommended",
        mode="teacher_assigned",
        created_at=datetime(2026, 1, 7, 10, 0, 0),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations/dashboard",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["class_id"] == class_id
        assert data["summary"]["total_runs"] == 1
        assert data["summary"]["total_adoptions"] == 1
        assert data["quality"]["quality_counts"]["validated"] + data["quality"]["quality_counts"]["fallback"] >= 0
        assert "version_breakdown" in data["quality"]
        assert "version_comparison_summary" in data["quality"]
        assert data["timeline"]["latest_run"]["run_id"] == run_id
        assert data["timeline"]["latest_adopted_run"]["run_id"] == run_id
        assert "observations" in data
        assert "high_quality_low_adoption_candidates" in data["observations"]
        assert "high_quality_edited_only_candidates" in data["observations"]
        assert len(data["recent_runs"]) == 1
        assert data["recent_runs"][0]["run_id"] == run_id


@pytest.mark.asyncio
async def test_teacher_cannot_access_other_teacher_topic_recommendation_dashboard():
    suffix_a = uuid.uuid4().hex[:8]
    suffix_b = uuid.uuid4().hex[:8]
    teacher_a_id, _ = _seed_teacher(suffix_a)
    _, headers_b = _seed_teacher(suffix_b)
    class_id = _seed_class(teacher_a_id, suffix_a)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations/dashboard",
            headers=headers_b,
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_teacher_can_filter_topic_recommendation_dashboard_by_time():
    suffix = uuid.uuid4().hex[:8]
    teacher_id, headers = _seed_teacher(suffix)
    class_id = _seed_class(teacher_id, suffix)
    run_id, _ = _seed_topic_run(class_id, teacher_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations/dashboard",
            params={
                "date_from": "2026-01-04T00:00:00",
                "date_to": "2026-01-10T00:00:00",
                "leaderboard_limit": 2,
                "observation_limit": 2,
            },
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["date_from"] == "2026-01-04T00:00:00"
        assert data["date_to"] == "2026-01-10T00:00:00"
        assert data["summary"]["total_runs"] == 0
        assert data["recent_runs"] == []
        assert "leaderboards" in data
        assert len(data["leaderboards"]["top_adopted_candidates"]) == 0
        assert len(data["observations"]["high_quality_low_adoption_candidates"]) == 0
        assert len(data["observations"]["high_quality_edited_only_candidates"]) == 0
        assert len(data["quality"]["version_breakdown"]) == 0
        assert data["quality"]["version_comparison_summary"] is None

        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations/dashboard",
            params={
                "date_from": "2026-01-10T00:00:00",
                "date_to": "2026-01-04T00:00:00",
            },
            headers=headers,
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_teacher_can_get_topic_recommendation_version_comparison():
    suffix = uuid.uuid4().hex[:8]
    teacher_id, headers = _seed_teacher(suffix)
    class_id = _seed_class(teacher_id, suffix)

    db = TestingSessionLocal()
    try:
        design_a = TeachingDesignService.upsert_current_version(
            db=db,
            class_id=class_id,
            created_by=teacher_id,
            extracted_payload=_design_payload(),
            version_name="v1",
            title="Design A",
        )
        design_b = TeachingDesignService.upsert_current_version(
            db=db,
            class_id=class_id,
            created_by=teacher_id,
            extracted_payload=_design_payload(),
            version_name="v2",
            title="Design B",
        )
        run_a = TopicRecommendationRun(
            id=uuid.uuid4(),
            class_id=uuid.UUID(class_id),
            teaching_design_version_id=uuid.UUID(design_a["id"]),
            created_by=uuid.UUID(teacher_id),
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
            class_id=uuid.UUID(class_id),
            teaching_design_version_id=uuid.UUID(design_b["id"]),
            created_by=uuid.UUID(teacher_id),
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
        db.add_all([run_a, run_b])
        db.flush()
        db.add_all(
            [
                TopicRecommendationItem(
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
                ),
                TopicRecommendationItem(
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
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations/version-comparison",
            params={
                "current_version_id": design_b["id"],
                "previous_version_id": design_a["id"],
            },
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["class_id"] == class_id
        assert data["current_version_id"] == design_b["id"]
        assert data["previous_version_id"] == design_a["id"]
        assert "version_comparison_summary" in data

        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations/version-comparison",
            params={"current_version_id": str(uuid.uuid4())},
            headers=headers,
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_teacher_cannot_access_other_teacher_topic_recommendation_version_comparison():
    suffix_a = uuid.uuid4().hex[:8]
    suffix_b = uuid.uuid4().hex[:8]
    teacher_a_id, _ = _seed_teacher(suffix_a)
    _, headers_b = _seed_teacher(suffix_b)
    class_id = _seed_class(teacher_a_id, suffix_a)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/classes/{class_id}/topic-recommendations/version-comparison",
            headers=headers_b,
        )
        assert response.status_code == 403
