"""Transactional operations for the durable background job queue."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from models.background_job import BackgroundJob
from schemas.operations import BackgroundJobStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_job_id(job_id: uuid.UUID | str) -> uuid.UUID:
    if isinstance(job_id, uuid.UUID):
        return job_id
    return uuid.UUID(str(job_id))


class BackgroundJobService:
    """Keep all queue transitions short, atomic and ownership checked."""

    @staticmethod
    def enqueue(
        db: Session,
        *,
        job_type: str,
        dedupe_key: str,
        payload: dict[str, Any],
        target_type: str | None = None,
        target_id: str | None = None,
        priority: int = 0,
        max_attempts: int = 3,
        available_at: datetime | None = None,
    ) -> tuple[BackgroundJob, bool]:
        if not str(job_type).strip():
            raise ValueError("job_type is required")
        if not str(dedupe_key).strip():
            raise ValueError("dedupe_key is required")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")

        job_id = uuid.uuid4()
        values = {
            "id": job_id,
            "job_type": str(job_type).strip(),
            "dedupe_key": str(dedupe_key).strip(),
            "target_type": str(target_type).strip() if target_type else None,
            "target_id": str(target_id).strip() if target_id else None,
            "status": BackgroundJobStatus.QUEUED.value,
            "priority": int(priority),
            "attempt_count": 0,
            "max_attempts": int(max_attempts),
            "payload": dict(payload),
            "available_at": available_at or utcnow(),
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }

        dialect_name = db.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = (
                postgresql_insert(BackgroundJob)
                .values(**values)
                .on_conflict_do_nothing(
                    index_elements=["job_type", "dedupe_key"]
                )
                .returning(BackgroundJob.id)
            )
        elif dialect_name == "sqlite":
            statement = (
                sqlite_insert(BackgroundJob)
                .values(**values)
                .on_conflict_do_nothing(
                    index_elements=["job_type", "dedupe_key"]
                )
                .returning(BackgroundJob.id)
            )
        else:  # pragma: no cover - supported runtime databases are PostgreSQL/SQLite
            raise RuntimeError(f"unsupported queue database dialect: {dialect_name}")

        inserted_id = db.execute(statement).scalar_one_or_none()
        db.commit()
        job = db.execute(
            select(BackgroundJob).where(
                BackgroundJob.job_type == values["job_type"],
                BackgroundJob.dedupe_key == values["dedupe_key"],
            )
        ).scalar_one()
        return job, inserted_id is not None

    @staticmethod
    def _build_claim_statement(
        *,
        worker_id: str,
        job_types: Iterable[str] | None,
        lease_seconds: int,
        current_time: datetime,
    ):
        candidate_query = (
            select(BackgroundJob.id)
            .where(
                BackgroundJob.status == BackgroundJobStatus.QUEUED.value,
                BackgroundJob.available_at <= current_time,
                BackgroundJob.attempt_count < BackgroundJob.max_attempts,
            )
            .order_by(
                BackgroundJob.priority.desc(),
                BackgroundJob.available_at.asc(),
                BackgroundJob.created_at.asc(),
                BackgroundJob.id.asc(),
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        normalized_types = [str(item).strip() for item in (job_types or []) if str(item).strip()]
        if normalized_types:
            candidate_query = candidate_query.where(
                BackgroundJob.job_type.in_(normalized_types)
            )

        return (
            update(BackgroundJob)
            .where(
                BackgroundJob.id == candidate_query.scalar_subquery(),
                BackgroundJob.status == BackgroundJobStatus.QUEUED.value,
            )
            .values(
                status=BackgroundJobStatus.RUNNING.value,
                attempt_count=BackgroundJob.attempt_count + 1,
                claimed_by=str(worker_id).strip(),
                claimed_at=current_time,
                lease_expires_at=current_time + timedelta(seconds=lease_seconds),
                updated_at=current_time,
                error_code=None,
                error_message=None,
            )
            .returning(BackgroundJob.id)
        )

    @staticmethod
    def claim_next(
        db: Session,
        *,
        worker_id: str,
        job_types: Iterable[str] | None = None,
        lease_seconds: int = 300,
        now: datetime | None = None,
    ) -> BackgroundJob | None:
        if not str(worker_id).strip():
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")

        current_time = now or utcnow()
        claim_statement = BackgroundJobService._build_claim_statement(
            worker_id=worker_id,
            job_types=job_types,
            lease_seconds=lease_seconds,
            current_time=current_time,
        )
        claimed_id = db.execute(claim_statement).scalar_one_or_none()
        if claimed_id is None:
            db.rollback()
            return None
        db.commit()
        return db.execute(
            select(BackgroundJob).where(BackgroundJob.id == claimed_id)
        ).scalar_one()

    @staticmethod
    def complete(
        db: Session,
        *,
        job_id: uuid.UUID | str,
        worker_id: str,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> bool:
        current_time = now or utcnow()
        statement = (
            update(BackgroundJob)
            .where(
                BackgroundJob.id == normalize_job_id(job_id),
                BackgroundJob.status == BackgroundJobStatus.RUNNING.value,
                BackgroundJob.claimed_by == str(worker_id),
            )
            .values(
                status=BackgroundJobStatus.SUCCEEDED.value,
                result=dict(result or {}),
                updated_at=current_time,
                finished_at=current_time,
                lease_expires_at=None,
                error_code=None,
                error_message=None,
            )
        )
        updated = db.execute(statement).rowcount
        db.commit()
        return updated == 1

    @staticmethod
    def update_progress(
        db: Session,
        *,
        job_id: uuid.UUID | str,
        progress: dict[str, Any],
        lease_seconds: int = 1800,
        now: datetime | None = None,
    ) -> bool:
        """Persist resumable job progress and refresh its lease in a short transaction."""
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        current_time = now or utcnow()
        job = db.execute(
            select(BackgroundJob)
            .where(
                BackgroundJob.id == normalize_job_id(job_id),
                BackgroundJob.status == BackgroundJobStatus.RUNNING.value,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if job is None:
            db.rollback()
            return False
        job.result = {**dict(job.result or {}), **dict(progress)}
        job.updated_at = current_time
        job.lease_expires_at = current_time + timedelta(seconds=lease_seconds)
        db.commit()
        return True

    @staticmethod
    def fail(
        db: Session,
        *,
        job_id: uuid.UUID | str,
        worker_id: str,
        error_code: str,
        error_message: str,
        now: datetime | None = None,
    ) -> bool:
        current_time = now or utcnow()
        statement = (
            update(BackgroundJob)
            .where(
                BackgroundJob.id == normalize_job_id(job_id),
                BackgroundJob.status == BackgroundJobStatus.RUNNING.value,
                BackgroundJob.claimed_by == str(worker_id),
            )
            .values(
                status=BackgroundJobStatus.FAILED.value,
                error_code=str(error_code)[:64],
                error_message=str(error_message)[:2000],
                updated_at=current_time,
                finished_at=current_time,
                lease_expires_at=None,
            )
        )
        updated = db.execute(statement).rowcount
        db.commit()
        return updated == 1

    @staticmethod
    def retry(
        db: Session,
        *,
        job_id: uuid.UUID | str,
        delay_seconds: int = 0,
        reset_attempts: bool = False,
        now: datetime | None = None,
    ) -> bool:
        if delay_seconds < 0:
            raise ValueError("delay_seconds cannot be negative")
        current_time = now or utcnow()
        job = db.execute(
            select(BackgroundJob)
            .where(BackgroundJob.id == normalize_job_id(job_id))
            .with_for_update()
        ).scalar_one_or_none()
        if job is None or job.status not in {
            BackgroundJobStatus.FAILED.value,
            BackgroundJobStatus.DEAD_LETTER.value,
        }:
            db.rollback()
            return False

        if reset_attempts:
            job.attempt_count = 0
        elif job.attempt_count >= job.max_attempts:
            job.status = BackgroundJobStatus.DEAD_LETTER.value
            job.updated_at = current_time
            db.commit()
            return False

        job.status = BackgroundJobStatus.QUEUED.value
        job.available_at = current_time + timedelta(seconds=delay_seconds)
        job.claimed_by = None
        job.claimed_at = None
        job.lease_expires_at = None
        job.finished_at = None
        job.updated_at = current_time
        db.commit()
        return True

    @staticmethod
    def mark_dead_letter(
        db: Session,
        *,
        job_id: uuid.UUID | str,
        now: datetime | None = None,
    ) -> bool:
        current_time = now or utcnow()
        statement = (
            update(BackgroundJob)
            .where(
                BackgroundJob.id == normalize_job_id(job_id),
                BackgroundJob.status == BackgroundJobStatus.FAILED.value,
            )
            .values(
                status=BackgroundJobStatus.DEAD_LETTER.value,
                updated_at=current_time,
                finished_at=current_time,
                lease_expires_at=None,
            )
        )
        updated = db.execute(statement).rowcount
        db.commit()
        return updated == 1

    @staticmethod
    def recover_expired_leases(
        db: Session,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> int:
        current_time = now or utcnow()
        jobs = db.execute(
            select(BackgroundJob)
            .where(
                BackgroundJob.status == BackgroundJobStatus.RUNNING.value,
                BackgroundJob.lease_expires_at.is_not(None),
                BackgroundJob.lease_expires_at <= current_time,
            )
            .order_by(BackgroundJob.lease_expires_at.asc(), BackgroundJob.id.asc())
            .limit(max(1, int(limit)))
            .with_for_update(skip_locked=True)
        ).scalars().all()

        for job in jobs:
            job.status = BackgroundJobStatus.FAILED.value
            job.error_code = "JOB_LEASE_EXPIRED"
            job.error_message = "worker lease expired before completion"
            job.claimed_by = None
            job.claimed_at = None
            job.lease_expires_at = None
            job.updated_at = current_time
            job.finished_at = current_time
            if job.attempt_count >= job.max_attempts:
                job.status = BackgroundJobStatus.DEAD_LETTER.value
            else:
                job.status = BackgroundJobStatus.QUEUED.value
                job.available_at = current_time
                job.finished_at = None

        db.commit()
        return len(jobs)

    @staticmethod
    def get(db: Session, job_id: uuid.UUID | str) -> BackgroundJob | None:
        return db.execute(
            select(BackgroundJob).where(
                BackgroundJob.id == normalize_job_id(job_id)
            )
        ).scalar_one_or_none()

    @staticmethod
    def get_latest_for_target(
        db: Session,
        *,
        job_type: str,
        target_type: str,
        target_id: str,
    ) -> BackgroundJob | None:
        return db.execute(
            select(BackgroundJob)
            .where(
                BackgroundJob.job_type == str(job_type),
                BackgroundJob.target_type == str(target_type),
                BackgroundJob.target_id == str(target_id),
            )
            .order_by(BackgroundJob.created_at.desc(), BackgroundJob.id.desc())
            .limit(1)
        ).scalar_one_or_none()
