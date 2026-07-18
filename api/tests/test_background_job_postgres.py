"""PostgreSQL-only concurrency proof for durable job claiming."""

import os
import threading
import uuid

import pytest
from sqlalchemy import create_engine, delete, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from models.background_job import BackgroundJob
from services.background_job_service import BackgroundJobService


pytestmark = pytest.mark.integration


def _postgres_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or ""
    if not value:
        pytest.skip("TEST_DATABASE_URL or DATABASE_URL is required")
    if make_url(value).get_backend_name() != "postgresql":
        pytest.skip("a PostgreSQL test database is required")
    return value


def test_two_postgres_workers_cannot_claim_the_same_job():
    engine = create_engine(_postgres_url(), pool_pre_ping=True)
    if "background_jobs" not in inspect(engine).get_table_names():
        pytest.skip("run Alembic migration 020 before the queue concurrency test")
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    key = f"postgres-concurrency-{uuid.uuid4()}"
    setup_db = session_factory()
    try:
        job, _ = BackgroundJobService.enqueue(
            setup_db,
            job_type="postgres_concurrency_test",
            dedupe_key=key,
            payload={},
        )
        job_id = job.id
    finally:
        setup_db.close()

    barrier = threading.Barrier(2)
    claims = []
    errors = []

    def claim(worker_id: str) -> None:
        db = session_factory()
        try:
            barrier.wait(timeout=5)
            claimed = BackgroundJobService.claim_next(
                db,
                worker_id=worker_id,
                job_types=["postgres_concurrency_test"],
            )
            claims.append(str(claimed.id) if claimed else None)
        except Exception as exc:  # pragma: no cover - diagnostic capture
            errors.append(exc)
        finally:
            db.close()

    first = threading.Thread(target=claim, args=("worker-a",))
    second = threading.Thread(target=claim, args=("worker-b",))
    first.start()
    second.start()
    first.join(timeout=10)
    second.join(timeout=10)

    cleanup_db = session_factory()
    try:
        cleanup_db.execute(delete(BackgroundJob).where(BackgroundJob.id == job_id))
        cleanup_db.commit()
    finally:
        cleanup_db.close()
        engine.dispose()

    assert errors == []
    assert claims.count(str(job_id)) == 1
    assert claims.count(None) == 1
