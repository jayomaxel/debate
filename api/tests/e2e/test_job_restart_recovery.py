import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest

from models.background_job import BackgroundJob
from schemas.operations import BackgroundJobStatus
from services.background_job_service import BackgroundJobService
from services.background_job_worker import BackgroundJobWorker


pytestmark = [pytest.mark.e2e, pytest.mark.integration]


@pytest.mark.asyncio
async def test_expired_worker_lease_recovers_without_duplicate_completion(e2e_db, e2e_session_factory):
    job, _ = BackgroundJobService.enqueue(
        e2e_db,
        job_type="e2e_restart_recovery",
        dedupe_key=f"restart-{uuid.uuid4()}",
        payload={"value": 1},
        max_attempts=3,
    )
    child_code = """
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.background_job_service import BackgroundJobService

engine = create_engine(os.environ['E2E_DATABASE_URL'], pool_pre_ping=True)
db = sessionmaker(bind=engine, expire_on_commit=False)()
claimed = BackgroundJobService.claim_next(
    db,
    worker_id='crashed-process-worker',
    job_types=['e2e_restart_recovery'],
    lease_seconds=1,
)
if claimed is None or str(claimed.id) != os.environ['E2E_CRASH_JOB_ID']:
    os._exit(91)
os._exit(23)
"""
    child_env = {**os.environ, "E2E_CRASH_JOB_ID": str(job.id)}
    crashed = subprocess.run(
        [sys.executable, "-c", child_code],
        cwd=Path(__file__).resolve().parents[2],
        env=child_env,
        check=False,
        timeout=30,
    )
    assert crashed.returncode == 23
    e2e_db.expire_all()
    claimed = e2e_db.get(BackgroundJob, job.id)
    assert claimed.status == BackgroundJobStatus.RUNNING.value
    assert claimed.claimed_by == "crashed-process-worker"
    time.sleep(1.2)

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
