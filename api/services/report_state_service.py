"""Read-only report readiness and export state resolution."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.debate import Debate
from models.score import Score
from models.speech import Speech
from schemas.operations import (
    ExportStatus,
    ReportOperationStateContract,
    ReportStatus,
    ScoringStatus,
)
from services.background_job_runtime import DEBATE_REPORT_JOB_TYPE
from services.background_job_service import BackgroundJobService
from services.report_orchestration_service import ReportOrchestrationService


class ReportStateService:
    @staticmethod
    def resolve(db: Session, debate: Debate) -> ReportOperationStateContract:
        valid_speech_count = int(
            db.execute(
                select(func.count(Speech.id)).where(
                    Speech.debate_id == debate.id,
                    Speech.is_valid_for_scoring.is_(True),
                    func.length(func.trim(Speech.content)) > 0,
                )
            ).scalar()
            or 0
        )
        scored_speech_count = int(
            db.execute(
                select(func.count(func.distinct(Score.speech_id)))
                .join(Speech, Speech.id == Score.speech_id)
                .where(
                    Speech.debate_id == debate.id,
                    Speech.is_valid_for_scoring.is_(True),
                    func.length(func.trim(Speech.content)) > 0,
                )
            ).scalar()
            or 0
        )
        job = BackgroundJobService.get_latest_for_target(
            db,
            job_type=DEBATE_REPORT_JOB_TYPE,
            target_type="debate",
            target_id=str(debate.id),
        )

        if valid_speech_count == 0:
            scoring_status = ScoringStatus.READY
            report_status = ReportStatus.EMPTY
        elif job and job.status in {"queued", "running"}:
            scoring_status = ScoringStatus.PROCESSING
            report_status = ReportStatus.PROCESSING
        elif job and job.status in {"failed", "dead_letter"}:
            scoring_status = ScoringStatus.FAILED
            report_status = ReportStatus.FAILED
        elif scored_speech_count >= valid_speech_count:
            scoring_status = ScoringStatus.READY
            report_status = ReportStatus.READY
        else:
            scoring_status = ScoringStatus.PENDING
            report_status = ReportStatus.PENDING

        report_data = debate.report if isinstance(debate.report, dict) else {}
        pdf_cache_status = ReportOrchestrationService._pdf_cache_status(
            debate,
            report_data,
        )
        if pdf_cache_status == "ready":
            export_status = ExportStatus.READY
        elif report_data.get("report_pdf_status") == "failed":
            export_status = ExportStatus.FAILED
        elif pdf_cache_status in {"stale", "missing_file"}:
            export_status = ExportStatus.STALE
        else:
            export_status = ExportStatus.NOT_GENERATED

        return ReportOperationStateContract(
            debate_id=str(debate.id),
            scoring_status=scoring_status,
            report_status=report_status,
            export_status=export_status,
            job_id=str(job.id) if job else None,
            retry_after=3 if report_status == ReportStatus.PROCESSING else None,
        )

    @staticmethod
    def enqueue_if_pending(
        db: Session,
        debate: Debate,
        *,
        room_id: str | None = None,
    ) -> ReportOperationStateContract:
        state = ReportStateService.resolve(db, debate)
        if state.report_status == ReportStatus.PENDING:
            from services.room_manager import room_manager

            room_manager.enqueue_report_job(
                db,
                debate.id,
                room_id or str(debate.id),
            )
            db.refresh(debate)
            state = ReportStateService.resolve(db, debate)
        return state
