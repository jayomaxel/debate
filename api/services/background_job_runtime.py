"""Application lifecycle wiring and handlers for durable background jobs."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from services.background_job_worker import BackgroundJobWorker


logger = logging.getLogger(__name__)

DEBATE_REPORT_JOB_TYPE = "debate_report"
KB_VECTOR_REBUILD_JOB_TYPE = "kb_vector_rebuild"

_worker: BackgroundJobWorker | None = None
_worker_task: asyncio.Task | None = None


def background_job_worker_status() -> dict:
    running = _worker_task is not None and not _worker_task.done()
    return {
        "status": "running" if running else "stopped",
        "worker_id": _worker.worker_id if running and _worker is not None else None,
    }


def build_debate_report_handler(
    session_factory: Callable[[], Session],
):
    async def handle(payload: dict, job_id: str) -> dict:
        from services.room_manager import room_manager

        debate_id = str(payload.get("debate_id") or "").strip()
        room_id = str(payload.get("room_id") or debate_id).strip()
        if not debate_id:
            raise ValueError("debate report job is missing debate_id")

        db = session_factory()
        try:
            await room_manager._auto_score_and_generate_report(db, uuid.UUID(debate_id))
        except Exception:
            db.rollback()
            await room_manager._broadcast_report_status(
                room_id,
                status="failed",
                job_id=job_id,
            )
            raise
        finally:
            db.close()

        await room_manager._broadcast_report_status(
            room_id,
            status="ready",
            job_id=job_id,
        )
        return {"debate_id": debate_id, "room_id": room_id, "report_status": "ready"}

    return handle


async def start_background_job_worker(
    session_factory: Callable[[], Session],
) -> BackgroundJobWorker:
    global _worker, _worker_task
    if _worker_task is not None and not _worker_task.done():
        return _worker

    _worker = BackgroundJobWorker(session_factory=session_factory)
    _worker.register(
        DEBATE_REPORT_JOB_TYPE,
        build_debate_report_handler(session_factory),
    )
    from services.kb_vector_rebuild_service import build_kb_vector_rebuild_handler

    _worker.register(
        KB_VECTOR_REBUILD_JOB_TYPE,
        build_kb_vector_rebuild_handler(session_factory),
    )
    _worker_task = asyncio.create_task(
        _worker.run_forever(),
        name="durable-background-job-worker",
    )
    logger.info("Durable background job worker started: %s", _worker.worker_id)
    return _worker


async def stop_background_job_worker() -> None:
    global _worker, _worker_task
    worker = _worker
    task = _worker_task
    _worker = None
    _worker_task = None
    if worker is None or task is None:
        return

    worker.stop()
    try:
        await asyncio.wait_for(task, timeout=5)
    except asyncio.TimeoutError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    logger.info("Durable background job worker stopped: %s", worker.worker_id)
