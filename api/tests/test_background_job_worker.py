import pytest
from sqlalchemy.orm import sessionmaker

from models.background_job import BackgroundJob
from schemas.operations import BackgroundJobStatus
from services.background_job_service import BackgroundJobService
from services.background_job_worker import BackgroundJobWorker


@pytest.fixture
def worker_session_factory(db_session):
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_session.get_bind(),
    )


@pytest.mark.asyncio
async def test_two_workers_execute_one_job_exactly_once(worker_session_factory):
    setup_db = worker_session_factory()
    try:
        job, _ = BackgroundJobService.enqueue(
            setup_db,
            job_type="count_once",
            dedupe_key="same-job",
            payload={"value": 1},
        )
        job_id = job.id
    finally:
        setup_db.close()

    executions = []

    async def handler(payload, claimed_job_id):
        executions.append((claimed_job_id, payload["value"]))
        return {"handled": True}

    first = BackgroundJobWorker(
        session_factory=worker_session_factory,
        worker_id="worker-a",
    )
    second = BackgroundJobWorker(
        session_factory=worker_session_factory,
        worker_id="worker-b",
    )
    first.register("count_once", handler)
    second.register("count_once", handler)

    assert await first.run_once() is True
    assert await second.run_once() is False
    assert executions == [(str(job_id), 1)]

    verify_db = worker_session_factory()
    try:
        stored = verify_db.get(BackgroundJob, job_id)
        assert stored.status == BackgroundJobStatus.SUCCEEDED.value
        assert stored.result == {"handled": True}
    finally:
        verify_db.close()


@pytest.mark.asyncio
async def test_worker_failure_is_requeued_then_succeeds(worker_session_factory):
    setup_db = worker_session_factory()
    try:
        job, _ = BackgroundJobService.enqueue(
            setup_db,
            job_type="retry_once",
            dedupe_key="retry-job",
            payload={},
            max_attempts=2,
        )
        job_id = job.id
    finally:
        setup_db.close()

    attempts = 0

    async def handler(_payload, _job_id):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary")
        return {"attempts": attempts}

    worker = BackgroundJobWorker(
        session_factory=worker_session_factory,
        worker_id="worker-a",
    )
    worker.register("retry_once", handler)

    assert await worker.run_once() is True
    retry_db = worker_session_factory()
    try:
        retry_job = retry_db.get(BackgroundJob, job_id)
        retry_job.available_at = retry_job.created_at
        retry_db.commit()
    finally:
        retry_db.close()

    assert await worker.run_once() is True
    assert attempts == 2

    verify_db = worker_session_factory()
    try:
        stored = verify_db.get(BackgroundJob, job_id)
        assert stored.status == BackgroundJobStatus.SUCCEEDED.value
        assert stored.attempt_count == 2
    finally:
        verify_db.close()


@pytest.mark.asyncio
async def test_worker_preserves_handler_operational_error_code(worker_session_factory):
    class TypedFailure(RuntimeError):
        error_code = "VECTOR_REBUILD_FAILED"

    setup_db = worker_session_factory()
    try:
        job, _ = BackgroundJobService.enqueue(
            setup_db,
            job_type="typed_failure",
            dedupe_key="typed-failure-job",
            payload={},
            max_attempts=1,
        )
        job_id = job.id
    finally:
        setup_db.close()

    async def handler(_payload, _job_id):
        raise TypedFailure("internal details")

    worker = BackgroundJobWorker(
        session_factory=worker_session_factory,
        worker_id="worker-typed",
    )
    worker.register("typed_failure", handler)
    assert await worker.run_once() is True

    verify_db = worker_session_factory()
    try:
        stored = verify_db.get(BackgroundJob, job_id)
        assert stored.status == BackgroundJobStatus.DEAD_LETTER.value
        assert stored.error_code == "VECTOR_REBUILD_FAILED"
    finally:
        verify_db.close()
