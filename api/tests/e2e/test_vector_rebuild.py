import pytest

from tests.test_kb_vector_rebuild import (
    test_pgvector_rebuild_resumes_and_supports_1536_1024_round_trip as _pgvector_rebuild_proof,
)


pytestmark = [pytest.mark.e2e, pytest.mark.integration, pytest.mark.pgvector]


@pytest.mark.asyncio
async def test_real_pgvector_rebuild_gate(e2e_db, monkeypatch):
    await _pgvector_rebuild_proof(
        e2e_db,
        monkeypatch,
    )
