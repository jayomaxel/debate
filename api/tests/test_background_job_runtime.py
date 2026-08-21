import asyncio

import pytest
from sqlalchemy.orm import sessionmaker

from services import background_job_runtime


@pytest.mark.asyncio
async def test_background_job_worker_lifecycle(db_session):
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_session.get_bind(),
    )

    worker = await background_job_runtime.start_background_job_worker(session_factory)
    await asyncio.sleep(0)
    running = background_job_runtime.background_job_worker_status()

    assert running["status"] == "running"
    assert running["worker_id"] == worker.worker_id

    await background_job_runtime.stop_background_job_worker()

    assert background_job_runtime.background_job_worker_status() == {
        "status": "stopped",
        "worker_id": None,
    }
