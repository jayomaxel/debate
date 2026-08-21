"""
Score validation and fallback service for work package A.

This service makes degraded scoring explicit. Fallback or partial results must
carry ReportMeta so downstream packages never have to guess score quality.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from services.mode_policy_service import DEFAULT_MODE, ModePolicyService
from services.rubric_service import LEGACY_SCORE_FIELDS, RUBRIC_VERSION


PROMPT_PACK_VERSION = "a.prompt_pack.v1"
CALIBRATION_VERSION = "a.calibration.v1"
SCORING_QUALITIES = ("validated", "repaired", "fallback", "partial")
SCORING_SOURCES = ("judge_model", "local_rule", "fallback")
PROVIDERS = ("coze", "llm", "local")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ReportMeta:
    scoring_source: str = "judge_model"
    scoring_quality: str = "validated"
    provider: str = "llm"
    prompt_pack_version: str = PROMPT_PACK_VERSION
    rubric_version: str = RUBRIC_VERSION
    calibration_version: str = CALIBRATION_VERSION
    mode: str = DEFAULT_MODE
    retry_count: int = 0
    generated_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scoring_source": self.scoring_source,
            "scoring_quality": self.scoring_quality,
            "provider": self.provider,
            "prompt_pack_version": self.prompt_pack_version,
            "rubric_version": self.rubric_version,
            "calibration_version": self.calibration_version,
            "mode": self.mode,
            "retry_count": int(self.retry_count),
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class ScoreValidationResult:
    payload: Dict[str, Any]
    report_meta: ReportMeta
    errors: List[str] = field(default_factory=list)
    repair_prompt: Optional[str] = None

    @property
    def scoring_quality(self) -> str:
        return self.report_meta.scoring_quality

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload": dict(self.payload),
            "report_meta": self.report_meta.to_dict(),
            "errors": list(self.errors),
            "repair_prompt": self.repair_prompt,
        }


class ScoreValidationService:
    """Validates Judge JSON, builds repair prompts, and emits explicit fallback."""

    SCORE_FIELDS = LEGACY_SCORE_FIELDS + ("overall_score",)

    @classmethod
    def normalize_provider(cls, provider: str | None) -> str:
        normalized = str(provider or "llm").strip().lower()
        return normalized if normalized in PROVIDERS else "llm"

    @classmethod
    def build_report_meta(
        cls,
        *,
        scoring_source: str = "judge_model",
        scoring_quality: str = "validated",
        provider: str = "llm",
        mode: str | None = None,
        retry_count: int = 0,
        prompt_pack_version: str = PROMPT_PACK_VERSION,
        rubric_version: str = RUBRIC_VERSION,
        calibration_version: str = CALIBRATION_VERSION,
    ) -> ReportMeta:
        source = scoring_source if scoring_source in SCORING_SOURCES else "fallback"
        quality = scoring_quality if scoring_quality in SCORING_QUALITIES else "fallback"
        return ReportMeta(
            scoring_source=source,
            scoring_quality=quality,
            provider=cls.normalize_provider(provider),
            prompt_pack_version=prompt_pack_version,
            rubric_version=rubric_version,
            calibration_version=calibration_version,
            mode=ModePolicyService.normalize_mode(mode),
            retry_count=max(0, int(retry_count)),
        )

    @classmethod
    def extract_json(cls, raw_text: str | None) -> Dict[str, Any]:
        text = str(raw_text or "").strip()
        if not text:
            raise ValueError("empty model response")

        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char not in "[{":
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value

        raise ValueError("no JSON object found")

    @classmethod
    def validate_speech_score(cls, payload: Mapping[str, Any]) -> ScoreValidationResult:
        errors: List[str] = []
        normalized: Dict[str, Any] = {}

        for field_name in LEGACY_SCORE_FIELDS:
            if field_name not in payload:
                errors.append(f"missing score field: {field_name}")
                continue
            try:
                normalized[field_name] = cls._normalize_score(payload[field_name])
            except (TypeError, ValueError):
                errors.append(f"invalid score field: {field_name}")

        if "overall_score" in payload:
            try:
                normalized["overall_score"] = cls._normalize_score(payload["overall_score"])
            except (TypeError, ValueError):
                errors.append("invalid score field: overall_score")
        elif not errors:
            normalized["overall_score"] = cls._average_score(normalized)
        else:
            errors.append("missing score field: overall_score")

        feedback = str(payload.get("feedback") or "").strip()
        normalized["feedback"] = feedback or "Score validated without detailed feedback."

        meta = cls.build_report_meta(
            scoring_source="judge_model",
            scoring_quality="validated" if not errors else "partial",
        )
        return ScoreValidationResult(payload=normalized, report_meta=meta, errors=errors)

    @classmethod
    def build_repair_prompt(
        cls,
        raw_text: str,
        *,
        expected_contract: Mapping[str, Any] | None = None,
    ) -> str:
        contract = expected_contract or cls.expected_speech_score_contract()
        return (
            "你是裁判输出格式修复器，只能修复格式，不能重新评分。\n"
            "规则：\n"
            "1. 只输出一个合法 JSON 对象，不要 Markdown 代码块、说明或前后文字。\n"
            "2. 保留原回复中可恢复的分数、反馈、speech_id、胜者和理由，不改变其语义。\n"
            "3. 可以修复 JSON 标点、引号、字段名拼写和字符串形式的数字。\n"
            "4. 不得凭空增加原回复没有的评分、违规、证据、胜负结论或报告内容。\n"
            "5. 必填值无法从原回复恢复时填 null，让下游校验触发显式 fallback；不要猜测默认分。\n"
            "6. 严格使用以下字段结构，不添加契约外字段：\n"
            f"{json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True)}\n\n"
            "待修复的原始裁判回复：\n"
            f"{raw_text}"
        )

    @classmethod
    def validate_or_fallback(
        cls,
        raw_text: str | None,
        *,
        repaired_text: str | None = None,
        mode: str | None = None,
        provider: str = "llm",
        fallback_reason: str = "Judge model did not return valid JSON.",
    ) -> ScoreValidationResult:
        errors: List[str] = []

        try:
            raw_payload = cls.extract_json(raw_text)
            raw_result = cls.validate_speech_score(raw_payload)
            if not raw_result.errors:
                meta = cls.build_report_meta(
                    scoring_source="judge_model",
                    scoring_quality="validated",
                    provider=provider,
                    mode=mode,
                    retry_count=0,
                )
                return ScoreValidationResult(payload=raw_result.payload, report_meta=meta)
            errors.extend(raw_result.errors)
        except ValueError as exc:
            errors.append(str(exc))

        repair_prompt = cls.build_repair_prompt(str(raw_text or ""))
        if repaired_text is not None:
            try:
                repaired_payload = cls.extract_json(repaired_text)
                repaired_result = cls.validate_speech_score(repaired_payload)
                if not repaired_result.errors:
                    meta = cls.build_report_meta(
                        scoring_source="judge_model",
                        scoring_quality="repaired",
                        provider=provider,
                        mode=mode,
                        retry_count=1,
                    )
                    return ScoreValidationResult(
                        payload=repaired_result.payload,
                        report_meta=meta,
                        errors=errors,
                        repair_prompt=repair_prompt,
                    )
                errors.extend(repaired_result.errors)
            except ValueError as exc:
                errors.append(str(exc))

        fallback_payload = cls.build_fallback_score(fallback_reason)
        retry_count = 1 if repaired_text is not None else 0
        meta = cls.build_report_meta(
            scoring_source="fallback",
            scoring_quality="fallback",
            provider=provider,
            mode=mode,
            retry_count=retry_count,
        )
        return ScoreValidationResult(
            payload=fallback_payload,
            report_meta=meta,
            errors=errors,
            repair_prompt=repair_prompt,
        )

    @classmethod
    def build_fallback_score(cls, reason: str = "fallback scoring") -> Dict[str, Any]:
        payload = {
            "logic_score": 60.0,
            "argument_score": 60.0,
            "response_score": 60.0,
            "persuasion_score": 60.0,
            "teamwork_score": 60.0,
            "overall_score": 60.0,
            "feedback": f"Fallback score generated: {reason}",
        }
        return payload

    @classmethod
    def expected_speech_score_contract(cls) -> Dict[str, Any]:
        return {
            "logic_score": "number 0-100",
            "argument_score": "number 0-100",
            "response_score": "number 0-100",
            "persuasion_score": "number 0-100",
            "teamwork_score": "number 0-100",
            "overall_score": "number 0-100",
            "feedback": "string",
        }

    @classmethod
    def collect_anomaly_samples(cls, report: Mapping[str, Any]) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        meta = report.get("report_meta") if isinstance(report.get("report_meta"), Mapping) else {}
        quality = str(meta.get("scoring_quality") or "")
        if quality in {"fallback", "partial"}:
            samples.append({"type": "fallback_triggered", "speaker_role": "", "severity": "high"})

        anchors = report.get("evidence_anchors")
        if anchors == []:
            samples.append({"type": "missing_evidence_anchor", "speaker_role": "", "severity": "medium"})

        participant_scores = report.get("participant_scores") or report.get("participants") or []
        if isinstance(participant_scores, Iterable):
            for item in participant_scores:
                if not isinstance(item, Mapping):
                    continue
                speaker_role = str(item.get("speaker_role") or item.get("role") or "")
                score = item.get("overall_score")
                if isinstance(item.get("final_score"), Mapping):
                    score = item["final_score"].get("overall_score", score)
                try:
                    numeric_score = float(score)
                except (TypeError, ValueError):
                    continue
                if numeric_score <= 5 or numeric_score >= 98:
                    samples.append(
                        {
                            "type": "extreme_score",
                            "speaker_role": speaker_role,
                            "severity": "medium",
                            "score": numeric_score,
                        }
                    )
        return samples

    @classmethod
    def build_calibration_summary(
        cls,
        samples: Iterable[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        sample_list = [dict(sample) for sample in samples]
        role_distribution: Dict[str, int] = {}
        for sample in sample_list:
            role = str(sample.get("speaker_role") or "unknown")
            role_distribution[role] = role_distribution.get(role, 0) + 1

        high_severity_count = sum(1 for sample in sample_list if sample.get("severity") == "high")
        fairness_status = "needs_review" if high_severity_count else "not_enough_samples"
        return {
            "calibration_version": CALIBRATION_VERSION,
            "sample_count": len(sample_list),
            "adjacent_consistency_rate": None,
            "role_anomaly_distribution": role_distribution,
            "fairness_check": {
                "status": fairness_status,
                "high_severity_count": high_severity_count,
                "claim": "mechanism only; not a scientifically validated scoring system",
            },
        }

    @staticmethod
    def _normalize_score(value: Any) -> float:
        score = float(value)
        return round(max(0.0, min(100.0, score)), 2)

    @staticmethod
    def _average_score(payload: Mapping[str, Any]) -> float:
        values = [float(payload.get(field, 0) or 0) for field in LEGACY_SCORE_FIELDS]
        return round(sum(values) / len(values), 2)


def validate_or_fallback(
    raw_text: str | None,
    *,
    repaired_text: str | None = None,
    mode: str | None = None,
    provider: str = "llm",
) -> ScoreValidationResult:
    return ScoreValidationService.validate_or_fallback(
        raw_text,
        repaired_text=repaired_text,
        mode=mode,
        provider=provider,
    )
