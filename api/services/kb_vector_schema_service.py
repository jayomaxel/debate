"""Read-only pgvector alignment inspection and RAG availability gating."""

from __future__ import annotations

import asyncio
import logging
import re
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from models.background_job import BackgroundJob


logger = logging.getLogger(__name__)

VECTOR_REBUILD_JOB_TYPE = "kb_vector_rebuild"
VECTOR_REBUILD_TARGET_TYPE = "kb_vector_schema"
VECTOR_REBUILD_TARGET_ID = "global"


class VectorAlignmentUnavailable(RuntimeError):
    """Raised when RAG traffic must be stopped until alignment is restored."""


class KBVectorSchemaService:
    _runtime_lock = RLock()
    _runtime_snapshot: dict[str, Any] = {
        "status": "unknown",
        "error_code": None,
        "inspected_at": None,
    }

    @classmethod
    def set_runtime_snapshot(cls, snapshot: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(snapshot)
        normalized.setdefault("inspected_at", datetime.now(timezone.utc).isoformat())
        with cls._runtime_lock:
            cls._runtime_snapshot = normalized
        return deepcopy(normalized)

    @classmethod
    def runtime_snapshot(cls) -> dict[str, Any]:
        with cls._runtime_lock:
            return deepcopy(cls._runtime_snapshot)

    @staticmethod
    def _parse_vector_dimension(column_type: str | None) -> int | None:
        match = re.fullmatch(r"vector\((\d+)\)", str(column_type or "").strip())
        return int(match.group(1)) if match else None

    @staticmethod
    def inspect_alignment(
        db: Session,
        *,
        configured_dimension: int,
        model_name: str,
        model_output_dimension: int | None,
        probe_error_code: str | None = None,
    ) -> dict[str, Any]:
        """Inspect configuration, column, index and stored vectors without DDL."""
        configured_dimension = int(configured_dimension)
        base = {
            "status": "unavailable",
            "error_code": "VECTOR_SCHEMA_UNAVAILABLE",
            "configured_dimension": configured_dimension,
            "database_dimension": None,
            "model_output_dimension": model_output_dimension,
            "model_name": str(model_name),
            "table_status": "unavailable",
            "index_status": "unavailable",
            "document_count": 0,
            "chunk_count": 0,
            "non_null_embedding_count": 0,
            "stored_dimension_mismatch_count": 0,
            "probe_error_code": probe_error_code,
            "inspected_at": datetime.now(timezone.utc).isoformat(),
        }

        bind = db.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            base["error_code"] = "VECTOR_POSTGRES_REQUIRED"
            return base

        table_exists = bool(
            db.execute(text("SELECT to_regclass('public.kb_document_chunks')")).scalar()
        )
        if not table_exists:
            base["table_status"] = "missing"
            base["index_status"] = "missing"
            base["error_code"] = "VECTOR_TABLE_MISSING"
            return base

        base["table_status"] = "ready"
        column_type = db.execute(
            text(
                """
                SELECT format_type(a.atttypid, a.atttypmod)
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE n.nspname = 'public'
                  AND c.relname = 'kb_document_chunks'
                  AND a.attname = 'embedding'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
                """
            )
        ).scalar()
        database_dimension = KBVectorSchemaService._parse_vector_dimension(column_type)
        base["database_dimension"] = database_dimension

        index_row = db.execute(
            text(
                """
                SELECT i.indisvalid, i.indisready, pg_get_indexdef(i.indexrelid)
                FROM pg_index i
                JOIN pg_class idx ON idx.oid = i.indexrelid
                JOIN pg_namespace n ON n.oid = idx.relnamespace
                WHERE n.nspname = 'public'
                  AND idx.relname = 'idx_kb_chunks_embedding'
                """
            )
        ).first()
        if index_row is None:
            base["index_status"] = "missing"
        elif (
            bool(index_row.indisvalid)
            and bool(index_row.indisready)
            and "vector_cosine_ops" in str(index_row[2] or "")
            and any(method in str(index_row[2] or "").lower() for method in ("hnsw", "ivfflat"))
        ):
            base["index_status"] = "ready"
        else:
            base["index_status"] = "invalid"

        dimension_expression = (
            "vector_dims(embedding)"
            if database_dimension is not None
            else "cardinality(embedding)"
            if str(column_type or "").endswith("[]")
            else "NULL"
        )
        counts = db.execute(
            text(
                f"""
                SELECT
                    (SELECT count(*) FROM kb_documents) AS document_count,
                    count(*) AS chunk_count,
                    count(*) FILTER (WHERE embedding IS NOT NULL) AS non_null_count,
                    count(*) FILTER (
                        WHERE embedding IS NOT NULL
                          AND {dimension_expression} <> :configured_dimension
                    ) AS mismatch_count
                FROM kb_document_chunks
                """
            ),
            {"configured_dimension": configured_dimension},
        ).one()
        base.update(
            {
                "document_count": int(counts.document_count or 0),
                "chunk_count": int(counts.chunk_count or 0),
                "non_null_embedding_count": int(counts.non_null_count or 0),
                "stored_dimension_mismatch_count": int(counts.mismatch_count or 0),
            }
        )

        mismatched = (
            database_dimension != configured_dimension
            or base["index_status"] != "ready"
            or base["stored_dimension_mismatch_count"] > 0
            or (
                model_output_dimension is not None
                and int(model_output_dimension) != configured_dimension
            )
        )
        if mismatched:
            base["status"] = "mismatch"
            base["error_code"] = "VECTOR_DIMENSION_MISMATCH"
        elif model_output_dimension is None:
            base["status"] = "unverified"
            base["error_code"] = "VECTOR_MODEL_DIMENSION_UNVERIFIED"
        else:
            base["status"] = "ready"
            base["error_code"] = None
        return base

    @staticmethod
    async def _probe_model_dimension(vector_config) -> int:
        from openai import OpenAI

        endpoint = str(vector_config.api_endpoint or "").strip()
        base_url = endpoint
        if base_url.endswith("/embeddings"):
            base_url = base_url[: -len("/embeddings")]
        client = OpenAI(
            api_key=vector_config.api_key,
            base_url=base_url or None,
            timeout=10.0,
            max_retries=0,
        )

        def call_model():
            return client.embeddings.create(
                model=vector_config.model_name,
                input="vector dimension alignment probe",
            )

        response = await asyncio.to_thread(call_model)
        embedding = response.data[0].embedding
        if not embedding:
            raise RuntimeError("embedding probe returned an empty vector")
        return len(embedding)

    @staticmethod
    async def inspect_alignment_with_probe(
        db: Session,
        *,
        probe_model: bool = True,
        embedding_probe=None,
    ) -> dict[str, Any]:
        from services.config_service import ConfigService

        vector_config = await ConfigService(db).get_vector_config()
        model_output_dimension = None
        probe_error_code = None
        bind = db.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            snapshot = KBVectorSchemaService.inspect_alignment(
                db,
                configured_dimension=int(vector_config.embedding_dimension or 0),
                model_name=str(vector_config.model_name or ""),
                model_output_dimension=None,
            )
            return KBVectorSchemaService.set_runtime_snapshot(snapshot)
        if probe_model:
            if not (
                vector_config.api_key
                and vector_config.api_endpoint
                and vector_config.model_name
            ):
                probe_error_code = "VECTOR_MODEL_NOT_CONFIGURED"
            else:
                try:
                    probe = embedding_probe or KBVectorSchemaService._probe_model_dimension
                    probed = await probe(vector_config)
                    model_output_dimension = int(probed)
                except Exception:
                    logger.exception("Vector model dimension probe failed")
                    probe_error_code = "VECTOR_MODEL_PROBE_FAILED"

        snapshot = KBVectorSchemaService.inspect_alignment(
            db,
            configured_dimension=int(vector_config.embedding_dimension or 0),
            model_name=str(vector_config.model_name or ""),
            model_output_dimension=model_output_dimension,
            probe_error_code=probe_error_code,
        )
        return KBVectorSchemaService.set_runtime_snapshot(snapshot)

    @staticmethod
    def rebuild_job_active(db: Session) -> bool:
        try:
            bind = db.get_bind()
            dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
            if dialect_name not in {"postgresql", "sqlite"}:
                return False
            if not inspect(bind).has_table("background_jobs"):
                return False
            result = db.execute(
                select(BackgroundJob.id)
                .where(
                    BackgroundJob.job_type == VECTOR_REBUILD_JOB_TYPE,
                    BackgroundJob.target_type == VECTOR_REBUILD_TARGET_TYPE,
                    BackgroundJob.target_id == VECTOR_REBUILD_TARGET_ID,
                    BackgroundJob.status.in_(["queued", "running"]),
                )
                .limit(1)
            )
            if not hasattr(result, "scalar_one_or_none"):
                return False
            return bool(result.scalar_one_or_none())
        except Exception:
            return False

    @staticmethod
    def require_rag_available(db: Session) -> None:
        if KBVectorSchemaService.rebuild_job_active(db):
            raise VectorAlignmentUnavailable("VECTOR_REBUILD_IN_PROGRESS")
        snapshot = KBVectorSchemaService.runtime_snapshot()
        status = str(snapshot.get("status") or "unknown")
        if status not in {"ready", "unknown"}:
            raise VectorAlignmentUnavailable(
                str(snapshot.get("error_code") or "VECTOR_DIMENSION_MISMATCH")
            )

    @staticmethod
    async def ensure_schema_matches_vector_config(db: Session) -> bool:
        """Compatibility shim: inspect only; never mutate schema."""
        await KBVectorSchemaService.inspect_alignment_with_probe(db, probe_model=False)
        return False

    @staticmethod
    def ensure_schema_matches_dimension(db: Session, target_dimension: int) -> bool:
        """Compatibility shim retained for callers during rollout; performs no DDL."""
        logger.warning(
            "Deprecated vector schema auto-alignment was skipped for dimension %s; "
            "use the durable rebuild workflow instead.",
            target_dimension,
        )
        return False
