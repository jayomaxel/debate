"""Durable, resumable pgvector schema and embedding rebuild workflow."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from models.background_job import BackgroundJob
from services.background_job_service import BackgroundJobService
from services.kb_vector_schema_service import (
    KBVectorSchemaService,
    VECTOR_REBUILD_JOB_TYPE,
    VECTOR_REBUILD_TARGET_ID,
    VECTOR_REBUILD_TARGET_TYPE,
)


logger = logging.getLogger(__name__)
REBUILD_LOCK_NAME = "aidebate:kb_vector_rebuild"
PHASES = (
    "preparing",
    "clearing",
    "altering_schema",
    "embedding",
    "indexing",
    "verifying",
    "ready",
)


class VectorRebuildError(RuntimeError):
    error_code = "VECTOR_REBUILD_FAILED"


class KBVectorRebuildService:
    @staticmethod
    def _validate_dimension(target_dimension: int) -> int:
        normalized = int(target_dimension)
        if normalized <= 0 or normalized > 16000:
            raise ValueError("target vector dimension must be between 1 and 16000")
        return normalized

    @staticmethod
    def get_latest_job(db: Session) -> BackgroundJob | None:
        return BackgroundJobService.get_latest_for_target(
            db,
            job_type=VECTOR_REBUILD_JOB_TYPE,
            target_type=VECTOR_REBUILD_TARGET_TYPE,
            target_id=VECTOR_REBUILD_TARGET_ID,
        )

    @staticmethod
    def enqueue(
        db: Session,
        *,
        target_model: str,
        target_dimension: int,
        requested_by: str,
        batch_size: int = 50,
        reason: str = "manual",
    ) -> tuple[BackgroundJob, bool]:
        target_dimension = KBVectorRebuildService._validate_dimension(target_dimension)
        target_model = str(target_model).strip()
        if not target_model:
            raise ValueError("target_model is required")
        batch_size = max(1, min(int(batch_size), 500))

        active = db.execute(
            select(BackgroundJob)
            .where(
                BackgroundJob.job_type == VECTOR_REBUILD_JOB_TYPE,
                BackgroundJob.target_type == VECTOR_REBUILD_TARGET_TYPE,
                BackgroundJob.target_id == VECTOR_REBUILD_TARGET_ID,
                BackgroundJob.status.in_(["queued", "running"]),
            )
            .order_by(BackgroundJob.created_at.desc(), BackgroundJob.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if active is not None:
            payload = dict(active.payload or {})
            if (
                str(payload.get("target_model") or "") == target_model
                and int(payload.get("target_dimension") or 0) == target_dimension
            ):
                return active, False
            raise RuntimeError("another vector rebuild is already queued or running")

        rebuild_revision = uuid.uuid4().hex
        job, created = BackgroundJobService.enqueue(
            db,
            job_type=VECTOR_REBUILD_JOB_TYPE,
            dedupe_key=f"kb-vector:{target_model}:{target_dimension}:{rebuild_revision}",
            target_type=VECTOR_REBUILD_TARGET_TYPE,
            target_id=VECTOR_REBUILD_TARGET_ID,
            payload={
                "target_model": target_model,
                "target_dimension": target_dimension,
                "requested_by": str(requested_by),
                "batch_size": batch_size,
                "reason": str(reason),
                "rebuild_revision": rebuild_revision,
            },
            priority=200,
            max_attempts=5,
        )
        KBVectorSchemaService.set_runtime_snapshot(
            {
                "status": "rebuilding",
                "error_code": None,
                "job_id": str(job.id),
                "target_model": target_model,
                "configured_dimension": target_dimension,
                "phase": "queued",
            }
        )
        return job, created

    @staticmethod
    def serialize_job(job: BackgroundJob) -> dict[str, Any]:
        result = dict(job.result or {})
        return {
            "job_id": str(job.id),
            "status": str(job.status),
            "phase": result.get("phase") or ("queued" if job.status == "queued" else None),
            "attempt_count": int(job.attempt_count),
            "max_attempts": int(job.max_attempts),
            "target_model": (job.payload or {}).get("target_model"),
            "target_dimension": (job.payload or {}).get("target_dimension"),
            "processed_chunks": int(result.get("processed_chunks") or 0),
            "total_chunks": int(result.get("total_chunks") or 0),
            "cursor": result.get("cursor"),
            "error_code": job.error_code,
            "error_message": (
                "向量重建失败，请检查模型配置后重试"
                if job.status in {"failed", "dead_letter"}
                else None
            ),
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }

    @staticmethod
    def _progress(db: Session, job_id: str, **values: Any) -> None:
        values["progress_updated_at"] = datetime.now(timezone.utc).isoformat()
        if not BackgroundJobService.update_progress(
            db,
            job_id=job_id,
            progress=values,
            lease_seconds=1800,
        ):
            raise RuntimeError("vector rebuild job ownership was lost")

    @staticmethod
    async def run(db: Session, payload: dict[str, Any], job_id: str) -> dict[str, Any]:
        if db.get_bind().dialect.name != "postgresql":
            raise VectorRebuildError("vector rebuild requires PostgreSQL with pgvector")

        target_model = str(payload.get("target_model") or "").strip()
        target_dimension = KBVectorRebuildService._validate_dimension(
            int(payload.get("target_dimension") or 0)
        )
        batch_size = max(1, min(int(payload.get("batch_size") or 50), 500))
        # PostgreSQL advisory locks are connection-scoped. Keep a dedicated
        # connection for the whole rebuild so Session commits/rollbacks cannot
        # return the lock-owning connection to the pool and leak the lock.
        lock_connection = db.get_bind().connect()
        acquired = bool(
            lock_connection.execute(
                text("SELECT pg_try_advisory_lock(hashtext(:lock_name))"),
                {"lock_name": REBUILD_LOCK_NAME},
            ).scalar()
        )
        if not acquired:
            lock_connection.close()
            raise VectorRebuildError("another vector rebuild holds the advisory lock")

        try:
            job = BackgroundJobService.get(db, job_id)
            resume = dict(job.result or {}) if job is not None else {}
            phase = str(resume.get("phase") or "preparing")
            if phase not in PHASES:
                phase = "preparing"
            KBVectorSchemaService.set_runtime_snapshot(
                {
                    "status": "rebuilding",
                    "error_code": None,
                    "job_id": job_id,
                    "target_model": target_model,
                    "configured_dimension": target_dimension,
                    "phase": phase,
                }
            )

            model_output_dimension = resume.get("model_output_dimension")
            if phase == "preparing" or model_output_dimension is None:
                from services.config_service import ConfigService

                ConfigService.invalidate_cache()
                vector_config = await ConfigService(db).get_vector_config()
                if str(vector_config.model_name or "") != target_model:
                    raise RuntimeError("active vector model no longer matches rebuild target")
                model_output_dimension = await KBVectorSchemaService._probe_model_dimension(
                    vector_config
                )
                if int(model_output_dimension) != target_dimension:
                    raise RuntimeError(
                        "configured vector dimension does not match model output dimension"
                    )
                total_chunks = int(
                    db.execute(text("SELECT count(*) FROM kb_document_chunks")).scalar()
                    or 0
                )
                total_documents = int(
                    db.execute(text("SELECT count(*) FROM kb_documents")).scalar()
                    or 0
                )
                KBVectorRebuildService._progress(
                    db,
                    job_id,
                    phase="clearing",
                    model_output_dimension=int(model_output_dimension),
                    total_documents=total_documents,
                    total_chunks=total_chunks,
                    processed_chunks=0,
                    cursor=None,
                )
                phase = "clearing"

            if phase == "clearing":
                db.execute(text("UPDATE kb_document_chunks SET embedding = NULL"))
                db.commit()
                KBVectorRebuildService._progress(
                    db,
                    job_id,
                    phase="altering_schema",
                    processed_chunks=0,
                    cursor=None,
                )
                phase = "altering_schema"

            if phase == "altering_schema":
                db.execute(text("DROP INDEX IF EXISTS idx_kb_chunks_embedding"))
                db.execute(
                    text(
                        f"""
                        ALTER TABLE kb_document_chunks
                        ALTER COLUMN embedding TYPE vector({target_dimension})
                        USING NULL::vector({target_dimension})
                        """
                    )
                )
                db.commit()
                KBVectorRebuildService._progress(
                    db,
                    job_id,
                    phase="embedding",
                    processed_chunks=0,
                    cursor=None,
                )
                phase = "embedding"
                resume = {**resume, "cursor": None, "processed_chunks": 0}

            if phase == "embedding":
                from services.document_service import DocumentService

                cursor = resume.get("cursor")
                processed_chunks = int(resume.get("processed_chunks") or 0)
                while True:
                    rows = db.execute(
                        text(
                            """
                            SELECT id, content
                            FROM kb_document_chunks
                            WHERE (:cursor IS NULL OR id > CAST(:cursor AS uuid))
                            ORDER BY id
                            LIMIT :batch_size
                            """
                        ),
                        {"cursor": cursor, "batch_size": batch_size},
                    ).all()
                    db.commit()
                    if not rows:
                        break

                    # The provider call happens outside any open DB transaction.
                    contents = [str(row.content) for row in rows]
                    embeddings = await DocumentService(db).generate_embeddings(contents)
                    if len(embeddings) != len(rows):
                        raise RuntimeError("embedding provider returned an incomplete batch")
                    if any(len(item) != target_dimension for item in embeddings):
                        raise RuntimeError("embedding provider changed vector dimension mid-rebuild")

                    update_values = [
                        {
                            "chunk_id": str(row.id),
                            "embedding": "[" + ",".join(str(value) for value in embedding) + "]",
                        }
                        for row, embedding in zip(rows, embeddings)
                    ]
                    db.execute(
                        text(
                            """
                            UPDATE kb_document_chunks
                            SET embedding = CAST(:embedding AS vector)
                            WHERE id = CAST(:chunk_id AS uuid)
                            """
                        ),
                        update_values,
                    )
                    db.commit()
                    cursor = str(rows[-1].id)
                    processed_chunks += len(rows)
                    KBVectorRebuildService._progress(
                        db,
                        job_id,
                        phase="embedding",
                        cursor=cursor,
                        processed_chunks=processed_chunks,
                    )

                KBVectorRebuildService._progress(
                    db,
                    job_id,
                    phase="indexing",
                    cursor=cursor,
                    processed_chunks=processed_chunks,
                )
                phase = "indexing"

            if phase == "indexing":
                db.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding
                        ON kb_document_chunks
                        USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 64)
                        """
                    )
                )
                db.commit()
                KBVectorRebuildService._progress(db, job_id, phase="verifying")
                phase = "verifying"

            if phase in {"verifying", "ready"}:
                snapshot = KBVectorSchemaService.inspect_alignment(
                    db,
                    configured_dimension=target_dimension,
                    model_name=target_model,
                    model_output_dimension=int(model_output_dimension),
                )
                if snapshot["non_null_embedding_count"] != snapshot["chunk_count"]:
                    raise RuntimeError("not every knowledge chunk has an embedding")
                if snapshot["status"] != "ready":
                    raise RuntimeError("vector alignment verification failed")
                if snapshot["chunk_count"]:
                    sample_id = db.execute(
                        text(
                            """
                            WITH sample AS (
                                SELECT embedding
                                FROM kb_document_chunks
                                WHERE embedding IS NOT NULL
                                LIMIT 1
                            )
                            SELECT id
                            FROM kb_document_chunks, sample
                            WHERE kb_document_chunks.embedding IS NOT NULL
                            ORDER BY kb_document_chunks.embedding <=> sample.embedding
                            LIMIT 1
                            """
                        )
                    ).scalar_one_or_none()
                    if sample_id is None:
                        raise RuntimeError("sample vector retrieval verification failed")
                if phase != "ready":
                    KBVectorRebuildService._progress(
                        db,
                        job_id,
                        phase="ready",
                        verified_at=datetime.now(timezone.utc).isoformat(),
                    )
                snapshot.update({"job_id": job_id, "phase": "ready"})
                KBVectorSchemaService.set_runtime_snapshot(snapshot)
                return snapshot

            raise RuntimeError(f"unsupported rebuild resume phase: {phase}")
        except Exception as exc:
            db.rollback()
            KBVectorSchemaService.set_runtime_snapshot(
                {
                    "status": "failed",
                    "error_code": "VECTOR_REBUILD_FAILED",
                    "job_id": job_id,
                    "target_model": target_model,
                    "configured_dimension": target_dimension,
                }
            )
            if isinstance(exc, VectorRebuildError):
                raise
            raise VectorRebuildError(str(exc)) from exc
        finally:
            db.rollback()
            try:
                lock_connection.execute(
                    text("SELECT pg_advisory_unlock(hashtext(:lock_name))"),
                    {"lock_name": REBUILD_LOCK_NAME},
                )
            except Exception:
                logger.exception("Failed to release KB vector rebuild advisory lock")
            finally:
                lock_connection.close()


def build_kb_vector_rebuild_handler(session_factory):
    async def handle(payload: dict[str, Any], job_id: str) -> dict[str, Any]:
        db = session_factory()
        try:
            return await KBVectorRebuildService.run(db, payload, job_id)
        finally:
            db.close()

    return handle
