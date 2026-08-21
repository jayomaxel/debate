import uuid

import pytest

from models.background_job import BackgroundJob
from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from models.user import User
from schemas.operations import BackgroundJobStatus
from services.background_job_runtime import DEBATE_REPORT_JOB_TYPE, build_debate_report_handler
from services.background_job_service import BackgroundJobService
from services.background_job_worker import BackgroundJobWorker


pytestmark = [pytest.mark.e2e, pytest.mark.integration]


@pytest.mark.asyncio
async def test_report_job_reaches_scoring_and_report_ready(e2e_db, e2e_session_factory):
    teacher = User(
        id=uuid.uuid4(), account=f"e2e-t-{uuid.uuid4().hex[:8]}", password_hash="x",
        user_type="teacher", name="E2E Teacher", email=f"{uuid.uuid4().hex}@example.test",
    )
    student = User(
        id=uuid.uuid4(), account=f"e2e-s-{uuid.uuid4().hex[:8]}", password_hash="x",
        user_type="student", name="E2E Student", email=f"{uuid.uuid4().hex}@example.test",
    )
    debate = Debate(
        id=uuid.uuid4(), topic="E2E report lifecycle", duration=10,
        invitation_code=uuid.uuid4().hex[:6], teacher_id=teacher.id, status="completed",
    )
    participation = DebateParticipation(
        id=uuid.uuid4(), debate_id=debate.id, user_id=student.id,
        role="debater_1", stance="positive",
    )
    speech = Speech(
        id=uuid.uuid4(), debate_id=debate.id, speaker_id=student.id,
        speaker_type="human", speaker_role="debater_1", phase="opening",
        content="Evidence supports a clear conclusion.", duration=30, is_valid_for_scoring=True,
    )
    e2e_db.add_all([teacher, student, debate, participation, speech])
    e2e_db.commit()

    job, created = BackgroundJobService.enqueue(
        e2e_db,
        job_type=DEBATE_REPORT_JOB_TYPE,
        dedupe_key=f"e2e-report:{debate.id}",
        payload={"debate_id": str(debate.id), "room_id": str(debate.id)},
        target_type="debate",
        target_id=str(debate.id),
    )
    assert created is True
    worker = BackgroundJobWorker(session_factory=e2e_session_factory, worker_id="e2e-report-worker")
    worker.register(DEBATE_REPORT_JOB_TYPE, build_debate_report_handler(e2e_session_factory))
    assert await worker.run_once() is True

    e2e_db.expire_all()
    stored_job = e2e_db.get(BackgroundJob, job.id)
    scores = e2e_db.query(Score).filter(Score.speech_id == speech.id).all()
    stored_debate = e2e_db.get(Debate, debate.id)
    assert stored_job.status == BackgroundJobStatus.SUCCEEDED.value
    assert len(scores) == 1
    assert scores[0].status == "fallback"
    assert scores[0].scoring_source == "fallback"
    assert scores[0].scoring_quality == "fallback"
    assert scores[0].eligible_for_analytics is False
    assert isinstance(stored_debate.report, dict)
    global_report = stored_debate.report.get("global_report")
    assert isinstance(global_report, dict) and global_report.get("winner")
    assert stored_debate.report["report_meta"]["scoring_source"] == "fallback"
    assert stored_debate.report["score_fallback_generated"] is True
