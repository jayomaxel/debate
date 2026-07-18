import pytest

from services.kb_vector_schema_service import (
    KBVectorSchemaService,
    VectorAlignmentUnavailable,
)


def test_sqlite_alignment_inspection_is_read_only_and_unavailable(db_session):
    snapshot = KBVectorSchemaService.inspect_alignment(
        db_session,
        configured_dimension=1536,
        model_name="test-model",
        model_output_dimension=1536,
    )

    assert snapshot["status"] == "unavailable"
    assert snapshot["error_code"] == "VECTOR_POSTGRES_REQUIRED"


def test_runtime_mismatch_blocks_rag_without_mutating_schema(db_session):
    original = KBVectorSchemaService.runtime_snapshot()
    try:
        KBVectorSchemaService.set_runtime_snapshot(
            {
                "status": "mismatch",
                "error_code": "VECTOR_DIMENSION_MISMATCH",
                "configured_dimension": 1024,
                "database_dimension": 1536,
            }
        )

        with pytest.raises(VectorAlignmentUnavailable, match="VECTOR_DIMENSION_MISMATCH"):
            KBVectorSchemaService.require_rag_available(db_session)
    finally:
        KBVectorSchemaService.set_runtime_snapshot(original)


def test_unknown_runtime_state_keeps_isolated_unit_tests_compatible(db_session):
    original = KBVectorSchemaService.runtime_snapshot()
    try:
        KBVectorSchemaService.set_runtime_snapshot(
            {"status": "unknown", "error_code": None}
        )
        KBVectorSchemaService.require_rag_available(db_session)
    finally:
        KBVectorSchemaService.set_runtime_snapshot(original)
