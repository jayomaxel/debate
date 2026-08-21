import uuid

from models.background_job import BackgroundJob
from models.debate import Debate
from schemas.operations import BackgroundJobStatus
from services.background_job_runtime import DEBATE_REPORT_JOB_TYPE
from services.background_job_service import BackgroundJobService
from services.room_manager import DebateRoomManager, REPORT_JOB_META_KEY, ROOM_META_KEY


def _completed_debate(*, report=None) -> Debate:
    return Debate(
        id=uuid.uuid4(),
        topic="Report job lifecycle",
        duration=30,
        invitation_code=uuid.uuid4().hex[:6],
        status="completed",
        report=report or {},
    )


def test_report_job_is_durable_and_idempotent(db_session):
    debate = _completed_debate()
    db_session.add(debate)
    db_session.commit()
    manager = DebateRoomManager()
    room_id = str(debate.id)

    assert manager.enqueue_report_job(db_session, debate.id, room_id) is True
    assert manager.enqueue_report_job(db_session, debate.id, room_id) is False

    jobs = db_session.query(BackgroundJob).filter(
        BackgroundJob.job_type == DEBATE_REPORT_JOB_TYPE,
        BackgroundJob.target_id == str(debate.id),
    ).all()
    assert len(jobs) == 1
    assert jobs[0].status == BackgroundJobStatus.QUEUED.value
    assert jobs[0].payload["room_id"] == room_id

    claimed = BackgroundJobService.claim_next(
        db_session,
        worker_id="report-worker",
        job_types=[DEBATE_REPORT_JOB_TYPE],
    )
    assert claimed.id == jobs[0].id
    assert BackgroundJobService.complete(
        db_session,
        job_id=claimed.id,
        worker_id="report-worker",
        result={"report_status": "ready"},
    ) is True

    completed = BackgroundJobService.get(db_session, claimed.id)
    assert completed.status == BackgroundJobStatus.SUCCEEDED.value
    assert manager.enqueue_report_job(db_session, debate.id, room_id) is False


def test_failed_report_job_is_automatically_retryable(db_session):
    debate = _completed_debate()
    db_session.add(debate)
    db_session.commit()
    manager = DebateRoomManager()
    room_id = str(debate.id)

    assert manager.enqueue_report_job(db_session, debate.id, room_id) is True
    claimed = BackgroundJobService.claim_next(
        db_session,
        worker_id="report-worker",
        job_types=[DEBATE_REPORT_JOB_TYPE],
    )
    assert BackgroundJobService.fail(
        db_session,
        job_id=claimed.id,
        worker_id="report-worker",
        error_code="REPORT_FAILED",
        error_message="temporary failure",
    ) is True
    assert BackgroundJobService.retry(db_session, job_id=claimed.id) is True

    retried = BackgroundJobService.claim_next(
        db_session,
        worker_id="report-worker-2",
        job_types=[DEBATE_REPORT_JOB_TYPE],
    )
    assert retried.id == claimed.id
    assert retried.attempt_count == 2


def test_legacy_pending_report_job_is_migrated(db_session):
    debate = _completed_debate(
        report={
            ROOM_META_KEY: {
                REPORT_JOB_META_KEY: {
                    "status": "running",
                    "attempts": 1,
                    "room_id": "legacy-room",
                    "updated_at": "2000-01-01T00:00:00",
                }
            }
        }
    )
    db_session.add(debate)
    db_session.commit()
    manager = DebateRoomManager()

    import asyncio

    recovered = asyncio.run(manager.recover_pending_report_jobs(db_session))

    assert recovered == 1
    durable = db_session.query(BackgroundJob).filter(
        BackgroundJob.job_type == DEBATE_REPORT_JOB_TYPE,
        BackgroundJob.target_id == str(debate.id),
    ).one()
    assert durable.status == BackgroundJobStatus.QUEUED.value
    assert durable.payload["room_id"] == "legacy-room"
