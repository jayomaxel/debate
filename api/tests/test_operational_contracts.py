import pytest
from pydantic import ValidationError

from schemas.operations import (
    BackgroundJobStatus,
    ExportStatus,
    OperationalErrorCode,
    OperationalErrorContract,
    ReportOperationStateContract,
    ReportStatus,
    ScoringStatus,
    can_transition,
)


def _values(enum_type):
    return {item.value for item in enum_type}


def test_frozen_operational_status_values():
    assert _values(BackgroundJobStatus) == {
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "dead_letter",
    }
    assert _values(ScoringStatus) == {"pending", "processing", "ready", "failed"}
    assert _values(ReportStatus) == {
        "pending",
        "processing",
        "ready",
        "failed",
        "empty",
    }
    assert _values(ExportStatus) == {
        "not_generated",
        "queued",
        "processing",
        "ready",
        "failed",
        "stale",
    }


def test_frozen_operational_error_codes():
    assert _values(OperationalErrorCode) == {
        "REPORT_DATA_NOT_READY",
        "REPORT_MARKDOWN_GENERATION_FAILED",
        "REPORT_PDF_RENDER_FAILED",
        "REPORT_STORAGE_WRITE_FAILED",
        "VECTOR_DIMENSION_MISMATCH",
        "VECTOR_REBUILD_FAILED",
    }


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (BackgroundJobStatus.QUEUED, BackgroundJobStatus.RUNNING),
        (BackgroundJobStatus.RUNNING, BackgroundJobStatus.SUCCEEDED),
        (BackgroundJobStatus.RUNNING, BackgroundJobStatus.FAILED),
        (BackgroundJobStatus.FAILED, BackgroundJobStatus.QUEUED),
        (BackgroundJobStatus.FAILED, BackgroundJobStatus.DEAD_LETTER),
        (ScoringStatus.PENDING, ScoringStatus.PROCESSING),
        (ScoringStatus.PROCESSING, ScoringStatus.READY),
        (ReportStatus.PROCESSING, ReportStatus.EMPTY),
        (ReportStatus.FAILED, ReportStatus.PROCESSING),
        (ExportStatus.NOT_GENERATED, ExportStatus.QUEUED),
        (ExportStatus.PROCESSING, ExportStatus.READY),
        (ExportStatus.READY, ExportStatus.STALE),
        (ExportStatus.STALE, ExportStatus.QUEUED),
    ],
)
def test_allowed_transitions(current, target):
    assert can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (BackgroundJobStatus.SUCCEEDED, BackgroundJobStatus.RUNNING),
        (BackgroundJobStatus.QUEUED, BackgroundJobStatus.SUCCEEDED),
        (ScoringStatus.PENDING, ScoringStatus.READY),
        (ReportStatus.PENDING, ReportStatus.READY),
        (ExportStatus.NOT_GENERATED, ExportStatus.READY),
        (ExportStatus.READY, ExportStatus.PROCESSING),
        (ReportStatus.READY, ExportStatus.READY),
    ],
)
def test_disallowed_transitions(current, target):
    assert not can_transition(current, target)


def test_operational_error_contract_serializes_stably():
    payload = OperationalErrorContract(
        code=OperationalErrorCode.REPORT_PDF_RENDER_FAILED,
        message="PDF 生成失败，请稍后重试",
        request_id="req_123",
        retryable=True,
        details={"debate_id": "debate-1", "job_id": "job-1"},
    ).model_dump(mode="json")

    assert payload == {
        "code": "REPORT_PDF_RENDER_FAILED",
        "message": "PDF 生成失败，请稍后重试",
        "request_id": "req_123",
        "retryable": True,
        "status": "failed",
        "details": {"debate_id": "debate-1", "job_id": "job-1"},
    }


def test_operational_error_contract_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        OperationalErrorContract(
            code=OperationalErrorCode.REPORT_DATA_NOT_READY,
            message="报告尚未就绪",
            request_id="req_123",
            retryable=True,
            stack_trace="must not leak",
        )


def test_report_operation_state_contract_serializes_stably():
    payload = ReportOperationStateContract(
        debate_id="debate-1",
        scoring_status=ScoringStatus.PROCESSING,
        report_status=ReportStatus.PENDING,
        export_status=ExportStatus.NOT_GENERATED,
        job_id="job-1",
        retry_after=3,
    ).model_dump(mode="json")

    assert payload == {
        "debate_id": "debate-1",
        "scoring_status": "processing",
        "report_status": "pending",
        "export_status": "not_generated",
        "job_id": "job-1",
        "retry_after": 3,
    }


def test_report_operation_state_contract_requires_positive_retry_after():
    with pytest.raises(ValidationError):
        ReportOperationStateContract(
            debate_id="debate-1",
            scoring_status=ScoringStatus.FAILED,
            report_status=ReportStatus.FAILED,
            export_status=ExportStatus.FAILED,
            retry_after=0,
        )
