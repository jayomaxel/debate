"""Frozen operational contracts shared by background jobs and report APIs."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BackgroundJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class ScoringStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ReportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    EMPTY = "empty"


class ExportStatus(str, Enum):
    NOT_GENERATED = "not_generated"
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    STALE = "stale"


class OperationalErrorCode(str, Enum):
    REPORT_DATA_NOT_READY = "REPORT_DATA_NOT_READY"
    REPORT_MARKDOWN_GENERATION_FAILED = "REPORT_MARKDOWN_GENERATION_FAILED"
    REPORT_PDF_RENDER_FAILED = "REPORT_PDF_RENDER_FAILED"
    REPORT_STORAGE_WRITE_FAILED = "REPORT_STORAGE_WRITE_FAILED"
    VECTOR_DIMENSION_MISMATCH = "VECTOR_DIMENSION_MISMATCH"
    VECTOR_REBUILD_FAILED = "VECTOR_REBUILD_FAILED"


JOB_STATUS_TRANSITIONS: dict[BackgroundJobStatus, frozenset[BackgroundJobStatus]] = {
    BackgroundJobStatus.QUEUED: frozenset(
        {BackgroundJobStatus.RUNNING, BackgroundJobStatus.CANCELLED}
    ),
    BackgroundJobStatus.RUNNING: frozenset(
        {BackgroundJobStatus.SUCCEEDED, BackgroundJobStatus.FAILED}
    ),
    BackgroundJobStatus.SUCCEEDED: frozenset(),
    BackgroundJobStatus.FAILED: frozenset(
        {
            BackgroundJobStatus.QUEUED,
            BackgroundJobStatus.DEAD_LETTER,
            BackgroundJobStatus.CANCELLED,
        }
    ),
    BackgroundJobStatus.CANCELLED: frozenset(),
    BackgroundJobStatus.DEAD_LETTER: frozenset(
        {BackgroundJobStatus.QUEUED, BackgroundJobStatus.CANCELLED}
    ),
}

SCORING_STATUS_TRANSITIONS: dict[ScoringStatus, frozenset[ScoringStatus]] = {
    ScoringStatus.PENDING: frozenset(
        {ScoringStatus.PROCESSING, ScoringStatus.FAILED}
    ),
    ScoringStatus.PROCESSING: frozenset(
        {ScoringStatus.READY, ScoringStatus.FAILED}
    ),
    ScoringStatus.READY: frozenset({ScoringStatus.PROCESSING}),
    ScoringStatus.FAILED: frozenset({ScoringStatus.PROCESSING}),
}

REPORT_STATUS_TRANSITIONS: dict[ReportStatus, frozenset[ReportStatus]] = {
    ReportStatus.PENDING: frozenset(
        {ReportStatus.PROCESSING, ReportStatus.FAILED, ReportStatus.EMPTY}
    ),
    ReportStatus.PROCESSING: frozenset(
        {ReportStatus.READY, ReportStatus.FAILED, ReportStatus.EMPTY}
    ),
    ReportStatus.READY: frozenset({ReportStatus.PROCESSING}),
    ReportStatus.FAILED: frozenset({ReportStatus.PROCESSING}),
    ReportStatus.EMPTY: frozenset({ReportStatus.PROCESSING}),
}

EXPORT_STATUS_TRANSITIONS: dict[ExportStatus, frozenset[ExportStatus]] = {
    ExportStatus.NOT_GENERATED: frozenset(
        {ExportStatus.QUEUED, ExportStatus.PROCESSING}
    ),
    ExportStatus.QUEUED: frozenset(
        {ExportStatus.PROCESSING, ExportStatus.FAILED}
    ),
    ExportStatus.PROCESSING: frozenset(
        {ExportStatus.READY, ExportStatus.FAILED}
    ),
    ExportStatus.READY: frozenset({ExportStatus.STALE}),
    ExportStatus.FAILED: frozenset(
        {ExportStatus.QUEUED, ExportStatus.PROCESSING}
    ),
    ExportStatus.STALE: frozenset(
        {ExportStatus.QUEUED, ExportStatus.PROCESSING}
    ),
}


def can_transition(current: Enum, target: Enum) -> bool:
    """Return whether a frozen operational state transition is allowed."""

    transition_map: dict[Enum, frozenset[Enum]]
    if isinstance(current, BackgroundJobStatus) and isinstance(
        target, BackgroundJobStatus
    ):
        transition_map = JOB_STATUS_TRANSITIONS
    elif isinstance(current, ScoringStatus) and isinstance(target, ScoringStatus):
        transition_map = SCORING_STATUS_TRANSITIONS
    elif isinstance(current, ReportStatus) and isinstance(target, ReportStatus):
        transition_map = REPORT_STATUS_TRANSITIONS
    elif isinstance(current, ExportStatus) and isinstance(target, ExportStatus):
        transition_map = EXPORT_STATUS_TRANSITIONS
    else:
        return False
    return target in transition_map[current]


class OperationalErrorContract(BaseModel):
    """Stable error payload for MSY-owned operational endpoints."""

    model_config = ConfigDict(extra="forbid")

    code: OperationalErrorCode
    message: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    retryable: bool
    status: Literal["failed"] = "failed"
    details: dict[str, Any] = Field(default_factory=dict)


class ReportOperationStateContract(BaseModel):
    """Stable state payload shared by report read, retry and export APIs."""

    model_config = ConfigDict(extra="forbid")

    debate_id: str = Field(min_length=1)
    scoring_status: ScoringStatus
    report_status: ReportStatus
    export_status: ExportStatus
    job_id: str | None = None
    retry_after: int | None = Field(default=None, ge=1)

