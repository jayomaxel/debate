import uuid

import pytest
from sqlalchemy import text

from models.config import VectorConfig
from models.user import User
from services.background_job_service import BackgroundJobService
from services.config_service import ConfigService
from services.document_service import DocumentService
from services.kb_vector_rebuild_service import KBVectorRebuildService
from services.kb_vector_schema_service import KBVectorSchemaService


pytestmark = pytest.mark.pgvector


def _vector_text(dimension: int, first_value: float) -> str:
    values = [first_value] + [0.0] * (dimension - 1)
    return "[" + ",".join(str(value) for value in values) + "]"


def _column_dimension(db_session) -> int:
    value = db_session.execute(
        text(
            """
            SELECT vector_dims(embedding)
            FROM kb_document_chunks
            WHERE embedding IS NOT NULL
            LIMIT 1
            """
        )
    ).scalar_one()
    return int(value)


@pytest.mark.asyncio
async def test_pgvector_rebuild_resumes_and_supports_1536_1024_round_trip(
    db_session,
    monkeypatch,
):
    admin_id = str(db_session.query(User.id).first()[0])
    document_id = "10000000-0000-0000-0000-000000000001"
    chunk_ids = [
        "20000000-0000-0000-0000-000000000001",
        "20000000-0000-0000-0000-000000000002",
    ]
    db_session.execute(
        text(
            """
            INSERT INTO kb_documents (
                id, filename, file_path, file_type, file_size,
                upload_status, uploaded_by, uploaded_at
            ) VALUES (
                CAST(:id AS uuid), 'vector-test.pdf', '/private/vector-test.pdf',
                'application/pdf', 100, 'completed', CAST(:uploaded_by AS uuid), CURRENT_TIMESTAMP
            )
            """
        ),
        {"id": document_id, "uploaded_by": admin_id},
    )
    db_session.execute(
        text(
            """
            INSERT INTO kb_document_chunks (
                id, document_id, chunk_index, content, token_count, embedding, created_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:document_id AS uuid), :chunk_index,
                :content, 5, CAST(:embedding AS vector), CURRENT_TIMESTAMP
            )
            """
        ),
        [
            {
                "id": chunk_ids[0],
                "document_id": document_id,
                "chunk_index": 0,
                "content": "first chunk",
                "embedding": _vector_text(1536, 0.9),
            },
            {
                "id": chunk_ids[1],
                "document_id": document_id,
                "chunk_index": 1,
                "content": "second chunk",
                "embedding": _vector_text(1536, 0.8),
            },
        ],
    )
    vector_config = VectorConfig(
        id=uuid.uuid4(),
        model_name="mock-1536",
        api_endpoint="https://example.invalid/v1/embeddings",
        api_key="test-key",
        embedding_dimension=1536,
        parameters={},
    )
    db_session.add(vector_config)
    db_session.commit()
    ConfigService.invalidate_cache()

    ready_before = KBVectorSchemaService.inspect_alignment(
        db_session,
        configured_dimension=1536,
        model_name="mock-1536",
        model_output_dimension=1536,
    )
    mismatch_before = KBVectorSchemaService.inspect_alignment(
        db_session,
        configured_dimension=1024,
        model_name="mock-1024",
        model_output_dimension=1024,
    )
    assert ready_before["status"] == "ready"
    assert mismatch_before["status"] == "mismatch"
    assert mismatch_before["database_dimension"] == 1536

    dimension_holder = {"value": 1024}

    async def fake_probe(_config):
        return dimension_holder["value"]

    calls = []
    fail_second_batch = {"enabled": True}

    async def resumable_embeddings(_self, texts):
        calls.append(list(texts))
        if fail_second_batch["enabled"] and texts == ["second chunk"]:
            raise RuntimeError("simulated provider interruption")
        dimension = dimension_holder["value"]
        return [
            [0.7 + index * 0.01] + [0.0] * (dimension - 1)
            for index, _text in enumerate(texts)
        ]

    monkeypatch.setattr(
        KBVectorSchemaService,
        "_probe_model_dimension",
        fake_probe,
        raising=True,
    )
    monkeypatch.setattr(
        DocumentService,
        "generate_embeddings",
        resumable_embeddings,
        raising=True,
    )

    updated_config = await ConfigService(db_session).update_vector_config(
        model_name="mock-1024",
        embedding_dimension=1024,
    )
    job = KBVectorRebuildService.get_latest_job(db_session)
    job.payload = {**dict(job.payload or {}), "batch_size": 1}
    db_session.commit()
    assert getattr(updated_config, "_vector_rebuild_job_id") == str(job.id)
    claimed = BackgroundJobService.claim_next(
        db_session,
        worker_id="vector-worker-first",
        job_types=["kb_vector_rebuild"],
    )
    assert str(claimed.id) == str(job.id)

    with pytest.raises(RuntimeError, match="simulated provider interruption"):
        await KBVectorRebuildService.run(
            db_session,
            dict(claimed.payload),
            str(claimed.id),
        )
    progress = BackgroundJobService.get(db_session, claimed.id).result
    assert progress["phase"] == "embedding"
    assert progress["processed_chunks"] == 1
    assert progress["cursor"] == chunk_ids[0]

    assert BackgroundJobService.fail(
        db_session,
        job_id=claimed.id,
        worker_id="vector-worker-first",
        error_code="VECTOR_REBUILD_FAILED",
        error_message="simulated provider interruption",
    )
    assert BackgroundJobService.retry(db_session, job_id=claimed.id)
    fail_second_batch["enabled"] = False
    resumed = BackgroundJobService.claim_next(
        db_session,
        worker_id="vector-worker-resumed",
        job_types=["kb_vector_rebuild"],
    )
    result_1024 = await KBVectorRebuildService.run(
        db_session,
        dict(resumed.payload),
        str(resumed.id),
    )
    assert BackgroundJobService.complete(
        db_session,
        job_id=resumed.id,
        worker_id="vector-worker-resumed",
        result=result_1024,
    )
    assert calls.count(["first chunk"]) == 1
    assert calls.count(["second chunk"]) == 2
    assert result_1024["status"] == "ready"
    assert _column_dimension(db_session) == 1024

    nearest = db_session.execute(
        text(
            """
            SELECT content
            FROM kb_document_chunks
            ORDER BY embedding <=> CAST(:query AS vector)
            LIMIT 1
            """
        ),
        {"query": _vector_text(1024, 0.7)},
    ).scalar_one()
    assert nearest in {"first chunk", "second chunk"}

    dimension_holder["value"] = 1536
    updated_1536 = await ConfigService(db_session).update_vector_config(
        model_name="mock-1536",
        embedding_dimension=1536,
    )
    job_1536 = KBVectorRebuildService.get_latest_job(db_session)
    assert getattr(updated_1536, "_vector_rebuild_job_id") == str(job_1536.id)
    claimed_1536 = BackgroundJobService.claim_next(
        db_session,
        worker_id="vector-worker-upsize",
        job_types=["kb_vector_rebuild"],
    )
    result_1536 = await KBVectorRebuildService.run(
        db_session,
        dict(claimed_1536.payload),
        str(claimed_1536.id),
    )
    assert BackgroundJobService.complete(
        db_session,
        job_id=claimed_1536.id,
        worker_id="vector-worker-upsize",
        result=result_1536,
    )
    assert result_1536["status"] == "ready"
    assert _column_dimension(db_session) == 1536
    assert result_1536["non_null_embedding_count"] == 2
    assert result_1536["index_status"] == "ready"
    assert db_session.execute(text("SELECT count(*) FROM kb_documents")).scalar_one() == 1
