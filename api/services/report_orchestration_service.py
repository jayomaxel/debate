"""
Teacher/student report orchestration owned by the B-side debate workflow.

This service composes the A-side ReportGenerator with score readiness, report
metadata, teaching summaries, and lightweight recalculation behavior.
"""
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session

from models.debate import Debate
from models.score import Score
from models.speech import Speech
from services.report_file_storage_service import ReportFileStorageService
from services.report_service import ReportGenerator
from services.scoring_service import ScoringService
from services.score_validation_service import ScoreValidationService


class ReportOrchestrationService:
    """B-side report workflow orchestration around the core report generator."""

    REPORT_QUALITY_VALUES = ("validated", "partial", "fallback")
    LEGACY_REPORT_QUALITY_VALUES = ("repaired",)
    SCORE_FALLBACK_MARKER = "评分系统暂时不可用"

    @staticmethod
    def _uuid_or_none(value: Any) -> Optional[uuid.UUID]:
        if value is None or value == "":
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except ValueError:
            return None

    @staticmethod
    def _safe_report_dict(debate: Debate) -> Dict[str, Any]:
        report = getattr(debate, "report", None)
        return report if isinstance(report, dict) else {}

    @staticmethod
    def infer_report_quality(report_meta: Dict[str, Any]) -> str:
        explicit_quality = report_meta.get("report_quality")
        speech_count = int(report_meta.get("score_speech_count") or 0)
        missing_count = int(report_meta.get("score_missing_count") or 0)
        report_status = str(report_meta.get("report_status") or "")
        markdown_status = str(report_meta.get("report_markdown_status") or "")
        pdf_status = str(report_meta.get("report_pdf_status") or "")
        score_fallback_detected = bool(report_meta.get("score_fallback_detected"))

        if speech_count <= 0 or report_status == "empty":
            return "fallback"
        if (
            missing_count > 0
            or report_status == "processing"
            or markdown_status == "failed"
            or pdf_status == "failed"
            or score_fallback_detected
        ):
            return "partial"
        if explicit_quality in {"partial", "fallback"}:
            return str(explicit_quality)
        return "validated"

    @staticmethod
    def _compute_markdown_hash(markdown_text: str, score_revision: int = 0) -> str:
        payload = f"score_revision:{int(score_revision or 0)}\n{markdown_text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _markdown_cache_status(report_data: Dict[str, Any], score_revision: int) -> str:
        status = str(report_data.get("report_markdown_status") or "").strip()
        if status == "failed":
            return "failed"

        markdown_text = report_data.get("report_markdown")
        markdown_hash = report_data.get("report_markdown_hash")
        if not isinstance(markdown_text, str) or not markdown_text.strip():
            return "absent"

        expected_hash = ReportOrchestrationService._compute_markdown_hash(
            markdown_text,
            score_revision,
        )
        return "ready" if markdown_hash == expected_hash else "stale"

    @staticmethod
    def _pdf_cache_status(debate: Debate, report_data: Dict[str, Any]) -> str:
        status = str(report_data.get("report_pdf_status") or "").strip()
        if status == "failed":
            return "failed"

        markdown_hash = report_data.get("report_markdown_hash")
        pdf_hash = report_data.get("report_pdf_markdown_hash")
        pdf_storage = report_data.get(ReportFileStorageService.PDF_STORAGE_META_KEY)
        has_pdf_reference = bool(
            (isinstance(pdf_storage, dict) and pdf_storage.get("storage_key"))
            or str(getattr(debate, "report_pdf", "") or "").strip()
        )

        if pdf_hash and markdown_hash and pdf_hash != markdown_hash:
            return "stale"
        if not pdf_hash and not has_pdf_reference:
            return "absent"
        return (
            "ready"
            if ReportFileStorageService.has_pdf_artifact(debate, str(debate.id))
            else "missing_file"
        )

    @staticmethod
    def _quality_flags(meta: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        if int(meta.get("score_speech_count") or 0) == 0:
            flags.append("no_valid_speech")
        if int(meta.get("score_missing_count") or 0) > 0:
            flags.append("missing_scores")
        if meta.get("score_fallback_detected"):
            flags.append("score_fallback_detected")
        if meta.get("legacy_report_quality") == "repaired":
            flags.append("legacy_repaired_quality")
        if meta.get("report_markdown_status") == "failed":
            flags.append("markdown_generation_failed")
        if meta.get("report_markdown_cache_status") == "stale":
            flags.append("markdown_cache_stale")
        if meta.get("report_pdf_status") == "failed":
            flags.append("pdf_generation_failed")
        if meta.get("report_pdf_cache_status") == "stale":
            flags.append("pdf_cache_stale")
        if meta.get("report_pdf_cache_status") == "missing_file":
            flags.append("pdf_file_missing")
        return flags

    @staticmethod
    def _score_contract_meta(report_data: Dict[str, Any]) -> Dict[str, Any]:
        default_meta = ScoreValidationService.build_report_meta(
            mode=report_data.get("mode")
        ).to_dict()
        meta = report_data.get("report_meta")
        if isinstance(meta, dict):
            default_meta.update(meta)
        return default_meta

    @staticmethod
    def _evidence_source_info(anchor: Dict[str, Any]) -> Dict[str, str]:
        source_type = str(
            anchor.get("evidence_source") or anchor.get("source_type") or ""
        ).strip()
        source_label = str(anchor.get("source_label") or "").strip()
        source_document_id = str(anchor.get("source_document_id") or "").strip()
        anchor_type = str(anchor.get("anchor_type") or "").strip()

        if not source_type:
            if source_document_id:
                source_type = "uploaded_document"
            elif anchor.get("turn_id") or anchor_type == "turn":
                source_type = "debate_speech"
            else:
                source_type = "unknown"

        if not source_label:
            if source_type == "debate_speech":
                source_label = "Debate speech transcript"
            elif source_type == "uploaded_document":
                source_label = "Uploaded support document"
            else:
                source_label = source_type.replace("_", " ")

        return {"source_type": source_type, "label": source_label}

    @staticmethod
    def _summarize_evidence_sources(
        evidence_anchors: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        summary_by_type: Dict[str, Dict[str, Any]] = {}
        for anchor in evidence_anchors or []:
            if not isinstance(anchor, dict):
                continue
            source_info = ReportOrchestrationService._evidence_source_info(anchor)
            source_type = source_info["source_type"]
            bucket = summary_by_type.setdefault(
                source_type,
                {
                    "source_type": source_type,
                    "label": source_info["label"],
                    "count": 0,
                },
            )
            if not bucket.get("label") and source_info["label"]:
                bucket["label"] = source_info["label"]
            bucket["count"] += 1
        return list(summary_by_type.values())

    @staticmethod
    def build_report_meta(db: Session, debate: Debate) -> Dict[str, Any]:
        report_data = ReportOrchestrationService._safe_report_dict(debate)
        score_contract_meta = ReportOrchestrationService._score_contract_meta(report_data)
        evidence_anchors = (
            report_data.get("evidence_anchors")
            if isinstance(report_data.get("evidence_anchors"), list)
            else []
        )
        evidence_sources = ReportOrchestrationService._summarize_evidence_sources(
            evidence_anchors
        )
        speeches = (
            db.query(Speech)
            .filter(
                Speech.debate_id == debate.id,
                Speech.is_valid_for_scoring.is_(True),
            )
            .all()
        )
        valid_speeches = [
            speech
            for speech in speeches
            if str(getattr(speech, "content", "") or "").strip()
        ]
        speech_ids = [speech.id for speech in valid_speeches]
        scores: List[Score] = []
        if speech_ids:
            scores = db.query(Score).filter(Score.speech_id.in_(speech_ids)).all()

        scored_speech_ids = {str(score.speech_id) for score in scores if score.speech_id}
        fallback_scores = [
            score
            for score in scores
            if ReportOrchestrationService.SCORE_FALLBACK_MARKER
            in str(getattr(score, "feedback", "") or "")
        ]
        speech_count = len(valid_speeches)
        scored_count = len(scored_speech_ids)
        missing_count = max(0, speech_count - scored_count)
        inferred_evidence_count = len(evidence_anchors)
        inferred_evidence_sources = list(evidence_sources)
        if inferred_evidence_count == 0 and speech_count > 0:
            inferred_evidence_count = speech_count
            inferred_evidence_sources = [
                {
                    "source_type": "debate_speech",
                    "label": "Debate speech transcript",
                    "count": speech_count,
                }
            ]
        score_revision = int(report_data.get("score_revision") or 0)
        legacy_quality = (
            str(report_data.get("report_quality"))
            if report_data.get("report_quality")
            in ReportOrchestrationService.LEGACY_REPORT_QUALITY_VALUES
            else None
        )
        markdown_cache_status = ReportOrchestrationService._markdown_cache_status(
            report_data,
            score_revision,
        )
        pdf_cache_status = ReportOrchestrationService._pdf_cache_status(debate, report_data)
        computed_status = (
            "empty"
            if speech_count == 0
            else "ready"
            if missing_count == 0
            else "processing"
        )

        meta = {
            "report_status": computed_status,
            "score_revision": score_revision,
            "score_speech_count": speech_count,
            "score_ready_count": scored_count,
            "score_missing_count": missing_count,
            "score_generation_mode": report_data.get("score_generation_mode"),
            "score_fallback_detected": bool(
                report_data.get("score_fallback_generated") or fallback_scores
            ),
            "score_fallback_count": len(fallback_scores),
            "scoring_source": score_contract_meta.get("scoring_source"),
            "scoring_quality": score_contract_meta.get("scoring_quality"),
            "provider": score_contract_meta.get("provider"),
            "prompt_pack_version": score_contract_meta.get("prompt_pack_version"),
            "rubric_version": score_contract_meta.get("rubric_version"),
            "calibration_version": score_contract_meta.get("calibration_version"),
            "mode": score_contract_meta.get("mode") or report_data.get("mode"),
            "retry_count": int(score_contract_meta.get("retry_count") or 0),
            "score_checked_at": report_data.get("score_checked_at"),
            "score_generated_at": report_data.get("score_generated_at"),
            "report_markdown_status": report_data.get("report_markdown_status"),
            "report_markdown_error": report_data.get("report_markdown_error"),
            "report_markdown_cache_status": markdown_cache_status,
            "report_markdown_cached": markdown_cache_status == "ready",
            "report_pdf_status": report_data.get("report_pdf_status"),
            "report_pdf_error": report_data.get("report_pdf_error"),
            "report_pdf_cache_status": pdf_cache_status,
            "report_pdf_cached": pdf_cache_status == "ready",
            "recalculated_at": report_data.get("report_recalculated_at"),
            "recalculation_count": int(
                report_data.get("report_recalculation_count") or 0
            ),
            "legacy_report_quality": legacy_quality,
            "report_quality_supported_values": list(
                ReportOrchestrationService.REPORT_QUALITY_VALUES
            ),
            "evidence_anchor_count": inferred_evidence_count,
            "evidence_source_types": [
                item["source_type"]
                for item in inferred_evidence_sources
                if item.get("source_type")
            ],
            "evidence_sources": inferred_evidence_sources,
            "generated_at": datetime.utcnow().isoformat(),
        }
        meta["report_quality"] = ReportOrchestrationService.infer_report_quality(
            {**report_data, **meta}
        )
        meta["quality_flags"] = ReportOrchestrationService._quality_flags(meta)
        return meta

    @staticmethod
    def build_speech_anchors(
        speeches: List[Dict[str, Any]],
        evidence_anchors: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        evidence_by_turn: Dict[str, Dict[str, str]] = {}
        for evidence_anchor in evidence_anchors or []:
            if not isinstance(evidence_anchor, dict):
                continue
            turn_id = str(evidence_anchor.get("turn_id") or "").strip()
            if not turn_id or turn_id in evidence_by_turn:
                continue
            source_info = ReportOrchestrationService._evidence_source_info(
                evidence_anchor
            )
            evidence_by_turn[turn_id] = {
                "evidence_source": source_info["source_type"],
                "source_label": source_info["label"],
            }

        anchors: List[Dict[str, Any]] = []
        for index, speech in enumerate(speeches or [], start=1):
            content = str(speech.get("content") or "").strip()
            score = speech.get("score") if isinstance(speech.get("score"), dict) else None
            speech_id = str(speech.get("id") or "").strip()
            source_info = evidence_by_turn.get(
                speech_id,
                {
                    "evidence_source": "debate_speech",
                    "source_label": "Debate speech transcript",
                },
            )
            anchors.append(
                {
                    "anchor_id": f"speech:{speech_id or speech.get('id')}",
                    "speech_id": speech.get("id"),
                    "sequence": index,
                    "speaker_name": speech.get("speaker_name"),
                    "speaker_role": speech.get("speaker_role") or speech.get("role"),
                    "phase": speech.get("phase"),
                    "timestamp": speech.get("timestamp"),
                    "summary": content[:120] + ("..." if len(content) > 120 else ""),
                    "overall_score": score.get("overall_score") if score else None,
                    "score_status": "ready" if score else "missing",
                    "evidence_source": source_info.get("evidence_source"),
                    "source_label": source_info.get("source_label"),
                }
            )
        return anchors

    @staticmethod
    def build_score_status(report_meta: Dict[str, Any]) -> Dict[str, Any]:
        speech_count = int(report_meta.get("score_speech_count") or 0)
        scored_count = int(report_meta.get("score_ready_count") or 0)
        missing_count = int(report_meta.get("score_missing_count") or 0)
        return {
            "ready": speech_count > 0 and missing_count == 0,
            "generated": False,
            "speech_count": speech_count,
            "scored_count": scored_count,
            "missing_score_count": missing_count,
            "score_revision": int(report_meta.get("score_revision") or 0),
            "score_generation_mode": report_meta.get("score_generation_mode"),
            "score_fallback_detected": bool(report_meta.get("score_fallback_detected")),
            "report_status": report_meta.get("report_status"),
            "report_quality": report_meta.get("report_quality"),
        }

    @staticmethod
    def attach_report_meta(
        db: Session,
        debate: Debate,
        report_payload: Dict[str, Any],
        *,
        teacher_view: bool,
    ) -> Dict[str, Any]:
        enriched = dict(report_payload or {})
        report_meta = ReportOrchestrationService.build_report_meta(db, debate)
        speech_anchors = ReportOrchestrationService.build_speech_anchors(
            enriched.get("speeches") or [],
            enriched.get("evidence_anchors") or [],
        )
        statistics = dict(enriched.get("statistics") or {})
        statistics["speech_anchors"] = speech_anchors
        statistics["score_status"] = ReportOrchestrationService.build_score_status(
            report_meta
        )
        enriched["statistics"] = statistics

        if teacher_view:
            enriched["report_meta"] = report_meta
        else:
            enriched["report_meta"] = {
                "report_quality": report_meta.get("report_quality"),
                "report_status": report_meta.get("report_status"),
                "score_speech_count": report_meta.get("score_speech_count"),
                "score_missing_count": report_meta.get("score_missing_count"),
            }
        return enriched

    @staticmethod
    def build_teaching_summary(db: Session, debate_id: str) -> Dict[str, Any]:
        debate_uuid = ReportOrchestrationService._uuid_or_none(debate_id)
        debate = db.query(Debate).filter(Debate.id == debate_uuid).first() if debate_uuid else None
        if not debate:
            raise ValueError("debate not found")

        meta = ReportOrchestrationService.build_report_meta(db, debate)
        statistics = ScoringService.get_debate_statistics(db, str(debate.id))
        common_issues: List[Dict[str, Any]] = []
        next_training_focus: List[Dict[str, Any]] = []

        if meta["score_speech_count"] == 0:
            common_issues.append(
                {
                    "type": "no_valid_speech",
                    "title": "No valid speech was available for scoring.",
                    "detail": "The report can only show a fallback state until valid speeches are recorded.",
                }
            )
            next_training_focus.append(
                {
                    "focus": "complete_participation",
                    "reason": "Students need enough valid speech data before the system can produce meaningful feedback.",
                }
            )

        if meta["score_missing_count"] > 0:
            common_issues.append(
                {
                    "type": "missing_scores",
                    "title": "Some speeches are still missing scores.",
                    "detail": f"{meta['score_missing_count']} valid speeches do not have scores yet.",
                }
            )

        dimension_labels = {
            "avg_logic_score": "logic",
            "avg_argument_score": "argument",
            "avg_response_score": "response",
            "avg_persuasion_score": "persuasion",
            "avg_teamwork_score": "teamwork",
        }
        human_stats = statistics.get("human") or {}
        low_dimensions = [
            (dimension, float(human_stats.get(metric) or 0))
            for metric, dimension in dimension_labels.items()
            if float(human_stats.get(metric) or 0) > 0
            and float(human_stats.get(metric) or 0) < 70
        ]
        for dimension, value in sorted(low_dimensions, key=lambda item: item[1])[:3]:
            common_issues.append(
                {
                    "type": "low_dimension_score",
                    "title": f"{dimension} performance needs attention.",
                    "detail": f"Average {dimension} score is {value:.2f}.",
                }
            )
            next_training_focus.append(
                {
                    "focus": dimension,
                    "reason": f"The class average in {dimension} is below the expected practice threshold.",
                }
            )

        report = ReportGenerator.generate_student_report(
            db=db,
            debate_id=str(debate.id),
            student_id=str(debate.teacher_id) if debate.teacher_id else "",
        )
        turning_points: List[Dict[str, Any]] = []
        if report:
            scored_speeches = [
                speech for speech in report.speeches
                if isinstance(speech.get("score"), dict)
            ]
            top_speeches = sorted(
                scored_speeches,
                key=lambda speech: float(
                    (speech.get("score") or {}).get("overall_score") or 0
                ),
                reverse=True,
            )[:3]
            for speech in top_speeches:
                score = speech.get("score") or {}
                turning_points.append(
                    {
                        "anchor_id": f"speech:{speech.get('id')}",
                        "speech_id": speech.get("id"),
                        "phase": speech.get("phase"),
                        "speaker_name": speech.get("speaker_name"),
                        "reason": "High-scoring speech segment that can be used for replay review.",
                        "overall_score": score.get("overall_score"),
                    }
                )

        if not next_training_focus:
            next_training_focus.append(
                {
                    "focus": "evidence_and_response",
                    "reason": "Continue strengthening evidence use and direct response to opposing arguments.",
                }
            )

        return {
            "debate_id": str(debate.id),
            "common_issues": common_issues,
            "turning_points": turning_points,
            "next_training_focus": next_training_focus,
            "score_status": ReportOrchestrationService.build_score_status(meta),
            "report_quality": meta["report_quality"],
            "report_meta": meta,
            "generated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def clear_report_cache_for_recalculation(db: Session, debate_id: str) -> Dict[str, Any]:
        debate_uuid = ReportOrchestrationService._uuid_or_none(debate_id)
        debate = db.query(Debate).filter(Debate.id == debate_uuid).first() if debate_uuid else None
        if not debate:
            raise ValueError("debate not found")

        existing = ReportOrchestrationService._safe_report_dict(debate)
        recalculation_count = int(existing.get("report_recalculation_count") or 0) + 1
        now = datetime.utcnow().isoformat()
        ReportFileStorageService.delete_pdf_artifact_for_debate(debate)
        debate.report = {
            key: value
            for key, value in existing.items()
            if key not in {
                "report_markdown",
                "report_markdown_hash",
                "report_pdf_markdown_hash",
                ReportFileStorageService.PDF_STORAGE_META_KEY,
                "report_quality",
            }
        }
        debate.report.update(
            {
                "report_recalculated_at": now,
                "report_recalculation_count": recalculation_count,
            }
        )
        debate.report_pdf = None
        db.commit()
        db.refresh(debate)

        meta = ReportOrchestrationService.build_report_meta(db, debate)
        debate.report = {
            **ReportOrchestrationService._safe_report_dict(debate),
            "report_quality": meta["report_quality"],
        }
        db.commit()
        return meta

    @staticmethod
    async def build_teacher_report_payload(
        db: Session,
        debate_id: str,
        teacher_id: str,
    ) -> Dict[str, Any]:
        debate_uuid = ReportOrchestrationService._uuid_or_none(debate_id)
        debate = db.query(Debate).filter(Debate.id == debate_uuid).first() if debate_uuid else None
        if not debate:
            raise ValueError("debate not found")

        await ScoringService.ensure_debate_scored(db=db, debate_id=debate_id)
        db.refresh(debate)
        report = ReportGenerator.generate_student_report(
            db=db,
            debate_id=debate_id,
            student_id=teacher_id,
        )
        if not report:
            raise ValueError("report not available")

        report_payload = ReportOrchestrationService.attach_report_meta(
            db=db,
            debate=debate,
            report_payload=report.to_dict(),
            teacher_view=True,
        )
        return {
            "report": report_payload,
            "report_meta": report_payload.get("report_meta") or {},
            "speech_anchors": (report_payload.get("statistics") or {}).get("speech_anchors", []),
        }

    @staticmethod
    async def recalculate_teacher_report(
        db: Session,
        debate_id: str,
    ) -> Dict[str, Any]:
        score_status = await ScoringService.ensure_debate_scored(db=db, debate_id=debate_id)
        report_meta = ReportOrchestrationService.clear_report_cache_for_recalculation(
            db=db,
            debate_id=debate_id,
        )
        teaching_summary = ReportOrchestrationService.build_teaching_summary(
            db=db,
            debate_id=debate_id,
        )
        return {
            "debate_id": debate_id,
            "mode": "lightweight",
            "score_status": score_status,
            "report_meta": report_meta,
            "teaching_summary": teaching_summary,
        }
