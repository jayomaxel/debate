import sys
import types
import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

if "uvicorn" not in sys.modules:
    sys.modules["uvicorn"] = types.ModuleType("uvicorn")

from database import get_db
from models.class_model import Class
from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from models.user import User
from routers import teacher
from testing_db import create_test_engine, create_test_schema, drop_test_schema
from utils.security import create_token


BASE_URL = "http://test"
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_teacher_student_contracts.db"
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


def _seed_teacher(suffix: str) -> tuple[str, dict]:
    account = f"teacher_contract_{suffix}"
    db = TestingSessionLocal()
    try:
        teacher_user = User(
            id=uuid.uuid4(),
            account=account,
            password_hash="test-hash",
            user_type="teacher",
            name=f"Teacher {suffix}",
            email=f"{account}@test.com",
            phone="13800000000",
        )
        db.add(teacher_user)
        db.commit()
        token = create_token({"sub": str(teacher_user.id), "user_type": "teacher"})
        return str(teacher_user.id), {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _seed_completed_debate_graph(suffix: str) -> dict:
    teacher_id, headers = _seed_teacher(suffix)
    db = TestingSessionLocal()
    try:
        class_id = uuid.uuid4()
        student_id = uuid.uuid4()
        debate_id = uuid.uuid4()
        participation_id = uuid.uuid4()
        speech_id = uuid.uuid4()

        cls = Class(
            id=class_id,
            name=f"contract-class-{suffix}",
            code=f"TC{suffix[:6].upper()}",
            teacher_id=uuid.UUID(teacher_id),
        )
        student = User(
            id=student_id,
            account=f"student_contract_{suffix}",
            password_hash="test-hash",
            user_type="student",
            name=f"Student {suffix}",
            email=f"student_contract_{suffix}@test.com",
            phone="13900000000",
            class_id=class_id,
        )
        debate = Debate(
            id=debate_id,
            topic="Should classroom AI feedback prioritize speed over depth?",
            description="teacher report contract test",
            duration=20,
            invitation_code=f"C{suffix[:5].upper()}",
            class_id=class_id,
            teacher_id=uuid.UUID(teacher_id),
            status="completed",
            mode="teacher_assigned",
            report={
                "report_markdown": "# Cached teacher report",
                "report_markdown_hash": "hash-before",
                "report_pdf_markdown_hash": "pdf-hash-before",
                "report_quality": "cached",
                "existing_note": "keep me",
            },
            report_pdf="/tmp/report-before.pdf",
            start_time=datetime(2026, 1, 8, 10, 0, 0),
            end_time=datetime(2026, 1, 8, 10, 20, 0),
            created_at=datetime(2026, 1, 8, 9, 50, 0),
        )
        participation = DebateParticipation(
            id=participation_id,
            debate_id=debate_id,
            user_id=student_id,
            role="debater_1",
            stance="positive",
        )
        speech = Speech(
            id=speech_id,
            debate_id=debate_id,
            speaker_id=student_id,
            speaker_type="human",
            speaker_role="debater_1",
            phase="opening",
            side="positive",
            speaker_position=1,
            content="AI feedback should first help students move quickly, then teachers can guide deeper revision.",
            duration=60,
            is_valid_for_scoring=True,
            timestamp=datetime(2026, 1, 8, 10, 3, 0),
        )
        score = Score(
            id=uuid.uuid4(),
            participation_id=participation_id,
            speech_id=speech_id,
            logic_score=82.0,
            argument_score=84.0,
            response_score=79.0,
            persuasion_score=81.0,
            teamwork_score=80.0,
            overall_score=81.2,
            feedback="Clear structure with usable teaching signals.",
        )
        db.add_all([cls, student, debate, participation, speech, score])
        db.commit()

        return {
            "teacher_id": teacher_id,
            "headers": headers,
            "class_id": str(class_id),
            "debate_id": str(debate_id),
            "speech_id": str(speech_id),
        }
    finally:
        db.close()


@pytest.mark.asyncio
async def test_teacher_can_get_report_with_meta_and_speech_anchors():
    seeded = _seed_completed_debate_graph(uuid.uuid4().hex[:8])

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/debates/{seeded['debate_id']}/report",
            headers=seeded["headers"],
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["report_meta"]["report_quality"] == "validated"
    assert data["report"]["report_meta"]["report_quality"] == "validated"
    assert data["report"]["statistics"]["score_status"]["ready"] is True
    assert len(data["speech_anchors"]) == 1
    assert data["speech_anchors"][0]["speech_id"] == seeded["speech_id"]


@pytest.mark.asyncio
async def test_teacher_can_get_teaching_summary():
    seeded = _seed_completed_debate_graph(uuid.uuid4().hex[:8])

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/debates/{seeded['debate_id']}/teaching-summary",
            headers=seeded["headers"],
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["debate_id"] == seeded["debate_id"]
    assert data["report_quality"] == "validated"
    assert data["score_status"]["ready"] is True
    assert data["turning_points"][0]["speech_id"] == seeded["speech_id"]
    assert data["next_training_focus"]


@pytest.mark.asyncio
async def test_teacher_can_lightweight_recalculate_report_without_rescoring():
    seeded = _seed_completed_debate_graph(uuid.uuid4().hex[:8])

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.post(
            f"/api/teacher/debates/{seeded['debate_id']}/report/recalculate",
            headers=seeded["headers"],
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mode"] == "lightweight"
    assert data["score_status"]["generated"] is False
    assert data["report_meta"]["report_quality"] == "validated"

    db = TestingSessionLocal()
    try:
        debate = db.query(Debate).filter(Debate.id == uuid.UUID(seeded["debate_id"])).one()
        assert "report_markdown" not in debate.report
        assert "report_markdown_hash" not in debate.report
        assert "report_pdf_markdown_hash" not in debate.report
        assert debate.report["existing_note"] == "keep me"
        assert debate.report["report_recalculation_count"] == 1
        assert debate.report_pdf is None
        assert db.query(Score).count() == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_teacher_cannot_access_other_teacher_report_contracts():
    seeded = _seed_completed_debate_graph(uuid.uuid4().hex[:8])
    _, other_headers = _seed_teacher(uuid.uuid4().hex[:8])

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        report_response = await client.get(
            f"/api/teacher/debates/{seeded['debate_id']}/report",
            headers=other_headers,
        )
        summary_response = await client.get(
            f"/api/teacher/debates/{seeded['debate_id']}/teaching-summary",
            headers=other_headers,
        )
        recalculate_response = await client.post(
            f"/api/teacher/debates/{seeded['debate_id']}/report/recalculate",
            headers=other_headers,
        )

    assert report_response.status_code == 403
    assert summary_response.status_code == 403
    assert recalculate_response.status_code == 403
