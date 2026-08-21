from datetime import timedelta

from sqlalchemy.dialects import postgresql

from schemas.operations import BackgroundJobStatus
from services.background_job_service import BackgroundJobService, utcnow


def _enqueue(db_session, *, key="job-1", priority=0, max_attempts=3):
    return BackgroundJobService.enqueue(
        db_session,
        job_type="test_job",
        dedupe_key=key,
        target_type="test",
        target_id=key,
        payload={"key": key},
        priority=priority,
        max_attempts=max_attempts,
    )


def test_enqueue_is_atomic_and_idempotent(db_session):
    first, first_created = _enqueue(db_session)
    second, second_created = _enqueue(db_session)

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert second.status == BackgroundJobStatus.QUEUED.value


def test_claim_orders_by_priority_and_prevents_second_claim(db_session):
    low, _ = _enqueue(db_session, key="low", priority=1)
    high, _ = _enqueue(db_session, key="high", priority=10)

    claimed = BackgroundJobService.claim_next(db_session, worker_id="worker-a")
    second_worker_claim = BackgroundJobService.claim_next(
        db_session,
        worker_id="worker-b",
        job_types=["missing_type"],
    )

    assert claimed.id == high.id
    assert claimed.claimed_by == "worker-a"
    assert claimed.attempt_count == 1
    assert second_worker_claim is None

    next_claim = BackgroundJobService.claim_next(db_session, worker_id="worker-b")
    assert next_claim.id == low.id
    assert next_claim.id != claimed.id


def test_only_current_owner_can_complete_job(db_session):
    job, _ = _enqueue(db_session)
    claimed = BackgroundJobService.claim_next(db_session, worker_id="worker-a")

    assert claimed.id == job.id
    assert BackgroundJobService.complete(
        db_session,
        job_id=job.id,
        worker_id="worker-b",
        result={"wrong": True},
    ) is False
    assert BackgroundJobService.complete(
        db_session,
        job_id=job.id,
        worker_id="worker-a",
        result={"ok": True},
    ) is True

    completed = BackgroundJobService.get(db_session, job.id)
    assert completed.status == BackgroundJobStatus.SUCCEEDED.value
    assert completed.result == {"ok": True}


def test_failed_job_retries_then_moves_to_dead_letter(db_session):
    job, _ = _enqueue(db_session, max_attempts=1)
    BackgroundJobService.claim_next(db_session, worker_id="worker-a")

    assert BackgroundJobService.fail(
        db_session,
        job_id=job.id,
        worker_id="worker-a",
        error_code="TEMPORARY",
        error_message="temporary failure",
    ) is True
    assert BackgroundJobService.retry(db_session, job_id=job.id) is False

    dead = BackgroundJobService.get(db_session, job.id)
    assert dead.status == BackgroundJobStatus.DEAD_LETTER.value
    assert dead.error_code == "TEMPORARY"


def test_expired_lease_is_recovered_without_duplicate_completion(db_session):
    job, _ = _enqueue(db_session, max_attempts=3)
    claimed_at = utcnow()
    claimed = BackgroundJobService.claim_next(
        db_session,
        worker_id="dead-worker",
        lease_seconds=1,
        now=claimed_at,
    )

    assert claimed.id == job.id
    assert BackgroundJobService.recover_expired_leases(
        db_session,
        now=claimed_at + timedelta(seconds=10),
    ) == 1

    recovered = BackgroundJobService.get(db_session, job.id)
    assert recovered.status == BackgroundJobStatus.QUEUED.value
    assert recovered.error_code == "JOB_LEASE_EXPIRED"
    assert recovered.claimed_by is None

    reclaimed = BackgroundJobService.claim_next(
        db_session,
        worker_id="new-worker",
        now=claimed_at + timedelta(seconds=11),
    )
    assert reclaimed.id == job.id
    assert reclaimed.attempt_count == 2
    assert BackgroundJobService.complete(
        db_session,
        job_id=job.id,
        worker_id="dead-worker",
    ) is False


def test_postgresql_claim_is_atomic_and_uses_skip_locked():
    statement = BackgroundJobService._build_claim_statement(
        worker_id="worker-a",
        job_types=["test_job"],
        lease_seconds=300,
        current_time=utcnow(),
    )

    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).upper()

    assert compiled.startswith("UPDATE BACKGROUND_JOBS")
    assert "FOR UPDATE SKIP LOCKED" in compiled
    assert "RETURNING BACKGROUND_JOBS.ID" in compiled
