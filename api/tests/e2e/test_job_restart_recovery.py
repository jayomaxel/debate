from datetime import datetime, timedelta, timezone
import uuid

import pytest

from models.background_job import BackgroundJob
from schemas.operations import BackgroundJobStatus
from services.background_job_service import BackgroundJobService
from services.background_job_worker import BackgroundJobWorker


pytestmark = [pytest.mark.e2e, pytest.mark.integration]


@pytest.mark.asyncio
async def test_expired_worker_lease_recovers_without_duplicate_completion(e2e_db, e2e_session_factory):
    base = datetime.now(timezone.utc)
    job, _ = BackgroundJobService.enqueue(
        e2e_db,
        job_type="e2e_restart_recovery",
        dedupe_key=f"restart-{uuid.uuid4()}",
        payload={"value": 1},
        max_attempts=3,
        available_at=base - timedelta(seconds=10),
    )
    claimed = BackgroundJobService.claim_next(
        e2e_db,
        worker_id="crashed-worker",
        job_types=["e2e_restart_recovery"],
        lease_seconds=1,
        now=base - timedelta(seconds=5),
    )
    assert str(claimed.id) == str(job.id)
    assert BackgroundJobService.recover_expired_leases(
        e2e_db,
        now=base,
    ) == 1

    executions = []

    async def handler(payload, job_id):
        executions.append((job_id, payload["value"]))
        return {"recovered": True}

    first = BackgroundJobWorker(session_factory=e2e_session_factory, worker_id="replacement-a")
    second = BackgroundJobWorker(session_factory=e2e_session_factory, worker_id="replacement-b")
    first.register("e2e_restart_recovery", handler)
    second.register("e2e_restart_recovery", handler)
    assert await first.run_once() is True
    assert await second.run_once() is False

    e2e_db.expire_all()
    stored = e2e_db.get(BackgroundJob, job.id)
    assert stored.status == BackgroundJobStatus.SUCCEEDED.value
    assert stored.attempt_count == 2
    assert executions == [(str(job.id), 1)]
