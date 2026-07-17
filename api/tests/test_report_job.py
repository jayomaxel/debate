import uuid

from models.debate import Debate
from services.room_manager import DebateRoomManager, REPORT_JOB_META_KEY


def _completed_debate() -> Debate:
    return Debate(
        id=uuid.uuid4(),
        topic="Report job lifecycle",
        duration=30,
        invitation_code=uuid.uuid4().hex[:6],
        status="completed",
        report={},
    )


def test_report_job_is_durable_and_idempotent(db_session):
    debate = _completed_debate()
    db_session.add(debate)
    db_session.commit()
    manager = DebateRoomManager()
    room_id = str(debate.id)

    assert manager.enqueue_report_job(db_session, debate.id, room_id) is True
    db_session.refresh(debate)
    queued = manager._report_job_payload(debate)
    assert queued["status"] == "queued"
    assert queued["attempts"] == 0
    assert manager.enqueue_report_job(db_session, debate.id, room_id) is False

    assert manager._claim_report_job(db_session, debate.id, room_id) is True
    db_session.refresh(debate)
    running = manager._report_job_payload(debate)
    assert running["status"] == "running"
    assert running["attempts"] == 1
    assert manager._claim_report_job(db_session, debate.id, room_id) is False

    manager._finish_report_job(db_session, debate.id, succeeded=True)
    db_session.refresh(debate)
    completed = manager._report_job_payload(debate)
    assert completed["status"] == "completed"
    assert completed["error"] is None
    assert manager.enqueue_report_job(db_session, debate.id, room_id) is False


def test_failed_report_job_can_be_retried(db_session):
    debate = _completed_debate()
    db_session.add(debate)
    db_session.commit()
    manager = DebateRoomManager()
    room_id = str(debate.id)

    assert manager.enqueue_report_job(db_session, debate.id, room_id) is True
    assert manager._claim_report_job(db_session, debate.id, room_id) is True
    manager._finish_report_job(
        db_session, debate.id, succeeded=False, error="temporary failure"
    )
    db_session.refresh(debate)
    failed = manager._report_job_payload(debate)
    assert failed["status"] == "failed"
    assert failed["error"] == "temporary failure"

    assert manager.enqueue_report_job(db_session, debate.id, room_id) is True
    assert manager._claim_report_job(db_session, debate.id, room_id) is True
    db_session.refresh(debate)
    retried = manager._report_job_payload(debate)
    assert retried["attempts"] == 2
