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
from services.background_job_runtime import DEBATE_REPORT_JOB_TYPE
from services.background_job_service import BackgroundJobService
from services.room_manager import DebateRoomManager
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
            status="validated",
            scoring_source="test_fixture",
            scoring_quality="validated",
            eligible_for_analytics=True,
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
async def test_teacher_recalculation_queues_new_revision_without_rescoring():
    seeded = _seed_completed_debate_graph(uuid.uuid4().hex[:8])

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.post(
            f"/api/teacher/debates/{seeded['debate_id']}/report/recalculate",
            headers=seeded["headers"],
        )
        duplicate_response = await client.post(
            f"/api/teacher/debates/{seeded['debate_id']}/report/recalculate",
            headers=seeded["headers"],
        )

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["mode"] == "queued"
    assert data["operation_state"]["report_status"] == "processing"
    assert data["operation_state"]["job_id"]
    assert data["report_meta"]["report_quality"] == "validated"
    assert duplicate_response.status_code == 202
    duplicate_data = duplicate_response.json()["data"]
    assert duplicate_data["reused_job"] is True
    assert duplicate_data["operation_state"]["job_id"] == data["operation_state"]["job_id"]

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
        job = BackgroundJobService.get_latest_for_target(
            db,
            job_type=DEBATE_REPORT_JOB_TYPE,
            target_type="debate",
            target_id=seeded["debate_id"],
        )
        assert job is not None
        assert job.status == "queued"
        assert job.payload["report_job_revision"] == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_teacher_report_read_queues_missing_scores_without_inline_scoring():
    seeded = _seed_completed_debate_graph(uuid.uuid4().hex[:8])
    db = TestingSessionLocal()
    try:
        db.query(Score).delete()
        db.commit()
    finally:
        db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/debates/{seeded['debate_id']}/report",
            headers=seeded["headers"],
        )
        summary_response = await client.get(
            f"/api/teacher/debates/{seeded['debate_id']}/teaching-summary",
            headers=seeded["headers"],
        )

    assert response.status_code == 202
    state = response.json()["data"]
    assert state["scoring_status"] == "processing"
    assert state["report_status"] == "processing"
    assert summary_response.status_code == 202
    assert summary_response.json()["data"]["job_id"] == state["job_id"]

    db = TestingSessionLocal()
    try:
        assert db.query(Score).count() == 0
        job = BackgroundJobService.get_latest_for_target(
            db,
            job_type=DEBATE_REPORT_JOB_TYPE,
            target_type="debate",
            target_id=seeded["debate_id"],
        )
        assert job is not None and job.status == "queued"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_teacher_report_failure_uses_stable_public_error_contract():
    seeded = _seed_completed_debate_graph(uuid.uuid4().hex[:8])
    db = TestingSessionLocal()
    try:
        manager = DebateRoomManager()
        manager.enqueue_report_job(
            db,
            uuid.UUID(seeded["debate_id"]),
            seeded["debate_id"],
        )
        job = BackgroundJobService.claim_next(
            db,
            worker_id="report-contract-worker",
            job_types=[DEBATE_REPORT_JOB_TYPE],
        )
        assert job is not None
        job_id = str(job.id)
        assert BackgroundJobService.fail(
            db,
            job_id=job.id,
            worker_id="report-contract-worker",
            error_code="PROVIDER_FAILURE",
            error_message="sensitive provider stack and credentials",
        )
    finally:
        db.close()

    headers = {**seeded["headers"], "X-Request-Id": "req-report-contract"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/debates/{seeded['debate_id']}/report",
            headers=headers,
        )

    assert response.status_code == 503
    assert response.headers["x-request-id"] == "req-report-contract"
    assert response.json() == {
        "code": "REPORT_DATA_NOT_READY",
        "message": "报告生成失败，请重试",
        "request_id": "req-report-contract",
        "retryable": True,
        "status": "failed",
        "details": {
            "debate_id": seeded["debate_id"],
            "job_id": job_id,
        },
    }
    assert "sensitive provider" not in response.text


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


@pytest.mark.asyncio
async def test_teacher_can_query_and_retry_owned_report_job():
    seeded = _seed_completed_debate_graph(uuid.uuid4().hex[:8])
    db = TestingSessionLocal()
    try:
        manager = DebateRoomManager()
        debate_uuid = uuid.UUID(seeded["debate_id"])
        assert manager.enqueue_report_job(db, debate_uuid, seeded["debate_id"])
        claimed = BackgroundJobService.claim_next(
            db,
            worker_id="failed-report-worker",
            job_types=[DEBATE_REPORT_JOB_TYPE],
        )
        assert BackgroundJobService.fail(
            db,
            job_id=claimed.id,
            worker_id="failed-report-worker",
            error_code="REPORT_FAILED",
            error_message="temporary failure",
        )
    finally:
        db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        status_response = await client.get(
            f"/api/teacher/debates/{seeded['debate_id']}/report/job",
            headers=seeded["headers"],
        )
        retry_response = await client.post(
            f"/api/teacher/debates/{seeded['debate_id']}/report/job/retry",
            headers=seeded["headers"],
        )

    assert status_response.status_code == 200
    assert status_response.json()["data"]["status"] == "failed"
    assert retry_response.status_code == 202
    assert retry_response.json()["data"]["status"] == "queued"

    db = TestingSessionLocal()
    try:
        retried_job = BackgroundJobService.claim_next(
            db,
            worker_id="successful-report-worker",
            job_types=[DEBATE_REPORT_JOB_TYPE],
        )
        assert retried_job is not None
        assert BackgroundJobService.complete(
            db,
            job_id=retried_job.id,
            worker_id="successful-report-worker",
            result={"report_status": "ready"},
        )
    finally:
        db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        ready_response = await client.get(
            f"/api/teacher/debates/{seeded['debate_id']}/report",
            headers=seeded["headers"],
        )
    assert ready_response.status_code == 200
    assert ready_response.json()["data"]["operation_state"]["report_status"] == "ready"


@pytest.mark.asyncio
async def test_teacher_cannot_query_other_teacher_report_job():
    seeded = _seed_completed_debate_graph(uuid.uuid4().hex[:8])
    _, other_headers = _seed_teacher(uuid.uuid4().hex[:8])
    db = TestingSessionLocal()
    try:
        manager = DebateRoomManager()
        manager.enqueue_report_job(
            db,
            uuid.UUID(seeded["debate_id"]),
            seeded["debate_id"],
        )
    finally:
        db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get(
            f"/api/teacher/debates/{seeded['debate_id']}/report/job",
            headers=other_headers,
        )

    assert response.status_code == 403
