"""Async worker for jobs persisted by :mod:`background_job_service`."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session

from services.background_job_service import BackgroundJobService


logger = logging.getLogger(__name__)

JobHandler = Callable[[dict[str, Any], str], Awaitable[dict[str, Any] | None]]


class BackgroundJobWorker:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        worker_id: str | None = None,
        poll_interval_seconds: float = 1.0,
        lease_seconds: int = 300,
    ) -> None:
        self.session_factory = session_factory
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:12]}"
        self.poll_interval_seconds = max(0.05, float(poll_interval_seconds))
        self.lease_seconds = max(1, int(lease_seconds))
        self.handlers: dict[str, JobHandler] = {}
        self._stop_event = asyncio.Event()

    def register(self, job_type: str, handler: JobHandler) -> None:
        normalized_type = str(job_type).strip()
        if not normalized_type:
            raise ValueError("job_type is required")
        self.handlers[normalized_type] = handler

    async def run_once(self) -> bool:
        claim_db = self.session_factory()
        try:
            BackgroundJobService.recover_expired_leases(claim_db)
            job = BackgroundJobService.claim_next(
                claim_db,
                worker_id=self.worker_id,
                job_types=self.handlers.keys(),
                lease_seconds=self.lease_seconds,
            )
            if job is None:
                return False
            job_id = str(job.id)
            job_type = str(job.job_type)
            payload = dict(job.payload or {})
            attempt_count = int(job.attempt_count)
            max_attempts = int(job.max_attempts)
        finally:
            claim_db.close()

        handler = self.handlers.get(job_type)
        if handler is None:  # Defensive: claim is already filtered by registered types.
            await self._record_failure(
                job_id=job_id,
                error_code="JOB_HANDLER_NOT_REGISTERED",
                error_message=f"no handler registered for {job_type}",
                retry=False,
            )
            return True

        try:
            result = await handler(payload, job_id)
        except asyncio.CancelledError:
            await self._record_failure(
                job_id=job_id,
                error_code="JOB_WORKER_CANCELLED",
                error_message="worker stopped during job execution",
                retry=attempt_count < max_attempts,
                delay_seconds=0,
            )
            raise
        except Exception as exc:
            logger.exception("Background job failed: id=%s type=%s", job_id, job_type)
            await self._record_failure(
                job_id=job_id,
                error_code=str(getattr(exc, "error_code", "JOB_HANDLER_FAILED")),
                error_message=str(exc),
                retry=attempt_count < max_attempts,
                delay_seconds=min(2 ** max(attempt_count - 1, 0), 60),
            )
            return True

        finish_db = self.session_factory()
        try:
            completed = BackgroundJobService.complete(
                finish_db,
                job_id=job_id,
                worker_id=self.worker_id,
                result=result,
            )
            if not completed:
                logger.warning(
                    "Job completion rejected because ownership changed: id=%s worker=%s",
                    job_id,
                    self.worker_id,
                )
        finally:
            finish_db.close()
        return True

    async def _record_failure(
        self,
        *,
        job_id: str,
        error_code: str,
        error_message: str,
        retry: bool,
        delay_seconds: int = 0,
    ) -> None:
        failure_db = self.session_factory()
        try:
            failed = BackgroundJobService.fail(
                failure_db,
                job_id=job_id,
                worker_id=self.worker_id,
                error_code=error_code,
                error_message=error_message,
            )
            if not failed:
                return
            if retry:
                BackgroundJobService.retry(
                    failure_db,
                    job_id=job_id,
                    delay_seconds=delay_seconds,
                )
            else:
                BackgroundJobService.mark_dead_letter(failure_db, job_id=job_id)
        finally:
            failure_db.close()

    async def run_forever(self) -> None:
        self._stop_event.clear()
        while not self._stop_event.is_set():
            processed = await self.run_once()
            if processed:
                continue
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stop_event.set()
