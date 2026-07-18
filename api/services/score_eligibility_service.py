"""Single source of truth for score provenance and analytics eligibility."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import and_

from models.score import Score


class ScoreEligibilityService:
    ELIGIBLE_STATUSES = ("validated", "repaired")
    FALLBACK_MARKERS = (
        "评分系统暂时不可用",
        "fallback score generated",
    )

    @classmethod
    def sql_filter(cls):
        """Return the canonical SQL predicate for trusted analytical scores."""
        return and_(
            Score.eligible_for_analytics.is_(True),
            Score.status.in_(cls.ELIGIBLE_STATUSES),
        )

    @classmethod
    def is_eligible(cls, score: Score) -> bool:
        return bool(score.eligible_for_analytics) and score.status in cls.ELIGIBLE_STATUSES

    @classmethod
    def infer_legacy_status(cls, feedback: Optional[str]) -> str:
        normalized = str(feedback or "").strip().lower()
        if any(marker.lower() in normalized for marker in cls.FALLBACK_MARKERS):
            return "fallback"
        return "legacy_unknown"

    @classmethod
    def provenance_from_report_meta(
        cls,
        report_meta: Optional[Mapping[str, Any]],
        *,
        default_source: str = "judge_model",
        model: Optional[str] = None,
        failure_code: Optional[str] = None,
    ) -> dict[str, Any]:
        meta = dict(report_meta or {})
        quality = str(meta.get("scoring_quality") or "fallback").strip().lower()
        source = str(meta.get("scoring_source") or default_source).strip().lower()
        if quality == "validated":
            status = "validated"
        elif quality == "repaired":
            status = "repaired"
        else:
            status = "fallback"
        return {
            "status": status,
            "scoring_source": source,
            "scoring_quality": quality,
            "retry_count": max(0, int(meta.get("retry_count") or 0)),
            "provider": meta.get("provider"),
            "model": model or meta.get("model"),
            "rubric_version": meta.get("rubric_version"),
            "failure_code": failure_code,
            "eligible_for_analytics": status in cls.ELIGIBLE_STATUSES,
        }

    @classmethod
    def apply_provenance(
        cls,
        score: Score,
        provenance: Mapping[str, Any],
        *,
        audit_reason: Optional[str] = None,
    ) -> Score:
        history = list((score.score_metadata or {}).get("attempt_history") or [])
        if getattr(score, "id", None) is not None:
            history.append(
                {
                    "status": score.status,
                    "scoring_source": score.scoring_source,
                    "scoring_quality": score.scoring_quality,
                    "retry_count": int(score.retry_count or 0),
                    "provider": score.provider,
                    "model": score.model,
                    "rubric_version": score.rubric_version,
                    "failure_code": score.failure_code,
                    "eligible_for_analytics": bool(score.eligible_for_analytics),
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "reason": audit_reason or "score_replaced",
                }
            )
        for field_name in (
            "status",
            "scoring_source",
            "scoring_quality",
            "retry_count",
            "provider",
            "model",
            "rubric_version",
            "failure_code",
            "eligible_for_analytics",
        ):
            if field_name in provenance:
                setattr(score, field_name, provenance[field_name])
        score.score_metadata = {
            **dict(score.score_metadata or {}),
            "attempt_history": history,
        }
        return score

    @classmethod
    def record_inactive_attempt(
        cls,
        score: Score,
        provenance: Mapping[str, Any],
        *,
        audit_reason: str,
    ) -> Score:
        """Audit a failed/degraded retry without replacing a trusted active score."""
        history = list((score.score_metadata or {}).get("attempt_history") or [])
        history.append(
            {
                **dict(provenance),
                "active": False,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "reason": audit_reason,
            }
        )
        score.score_metadata = {
            **dict(score.score_metadata or {}),
            "attempt_history": history,
        }
        return score
