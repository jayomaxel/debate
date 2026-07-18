import pytest

from tests.test_markdown_pdf import test_markdown_to_pdf as _real_pdf_renderer_proof
from tests.test_score_fallback_isolation import (
    test_fallback_is_excluded_from_profiles_averages_rankings_and_training as _fallback_isolation_proof,
)
from tests.test_student_report_pdf_cache import (
    debate_for_teacher,
    override_app_database,
    setup_database,
    teacher_user,
    teacher_token,
    test_pdf_generation_is_atomic_and_three_reads_render_once as _pdf_cache_proof,
    test_pdf_invalid_renderer_output_uses_stable_error_contract as _pdf_failure_proof,
)


pytestmark = [pytest.mark.e2e, pytest.mark.integration]


@pytest.mark.asyncio
async def test_real_pdf_renderer_gate():
    await _real_pdf_renderer_proof()


def test_pdf_failure_is_retryable_then_three_exports_render_once(
    tmp_path,
    teacher_token,
    debate_for_teacher,
    monkeypatch,
):
    _pdf_failure_proof(
        tmp_path,
        teacher_token,
        debate_for_teacher,
        monkeypatch,
        b"not-a-pdf",
    )
    _pdf_cache_proof(
        tmp_path,
        teacher_token,
        debate_for_teacher,
        monkeypatch,
    )


def test_fallback_is_visible_but_excluded_from_analytics_gate(e2e_db):
    _fallback_isolation_proof(e2e_db)
