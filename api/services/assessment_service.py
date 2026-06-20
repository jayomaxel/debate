"""
Ability assessment service.
"""

from typing import Any, Dict, List, Optional

import math
import uuid
from sqlalchemy.orm import Session

from models.assessment import AbilityAssessment


class AssessmentService:
    """Handle persistence and presentation of student ability assessments."""

    ROLE_DESCRIPTIONS = {
        "debater_1": "一辩 - 立论陈词，奠定基调",
        "debater_2": "二辩 - 攻辩反击，定点补强",
        "debater_3": "三辩 - 逻辑交锋，快速反应",
        "debater_4": "四辩 - 总结陈词，价值升华",
    }
    STANDARD_PROFILE_FIELDS = [
        "expression",
        "logic",
        "critical",
        "knowledge_primary",
        "knowledge_secondary",
    ]
    ROLE_ABILITY_MODEL = {
        "debater_1": {
            "expression": 0.30,
            "logic": 0.30,
            "knowledge_primary": 0.25,
            "critical": 0.15,
        },
        "debater_2": {
            "logic": 0.35,
            "knowledge_primary": 0.30,
            "critical": 0.20,
            "expression": 0.15,
        },
        "debater_3": {
            "critical": 0.40,
            "logic": 0.25,
            "expression": 0.20,
            "knowledge_primary": 0.15,
        },
        "debater_4": {
            "expression": 0.25,
            "logic": 0.25,
            "critical": 0.20,
            "knowledge_primary": 0.15,
            "knowledge_secondary": 0.15,
        },
    }
    ROLE_ASSIGNMENT_REASONS = {
        "debater_1": "适合承担立论框架、概念界定和首轮观点建构。",
        "debater_2": "适合承担论据补强、盘问推进和逻辑追问。",
        "debater_3": "适合承担反驳整合、漏洞识别和临场攻防。",
        "debater_4": "适合承担总结陈词、价值权衡和全场收束。",
    }

    @staticmethod
    def _score(value: Any, default: int = 50) -> int:
        try:
            return max(0, min(100, int(round(float(value)))))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def build_standard_profile(assessment: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Map legacy assessment fields into the standard ability profile."""

        assessment = assessment or {}
        has_self_assessment = bool(assessment)
        standard_profile = {
            "expression": AssessmentService._score(assessment.get("expression_willingness")),
            "logic": AssessmentService._score(assessment.get("logical_thinking")),
            "critical": AssessmentService._score(assessment.get("critical_thinking")),
            "knowledge_primary": AssessmentService._score(assessment.get("financial_knowledge")),
            "knowledge_secondary": AssessmentService._score(assessment.get("stablecoin_knowledge")),
        }
        legacy_profile = {
            "expression_willingness": standard_profile["expression"],
            "logical_thinking": standard_profile["logic"],
            "critical_thinking": standard_profile["critical"],
            "financial_knowledge": standard_profile["knowledge_primary"],
            "stablecoin_knowledge": standard_profile["knowledge_secondary"],
        }
        return {
            "standard_profile": standard_profile,
            "legacy_profile": legacy_profile,
            "analysis_basis": "self_assessment_only" if has_self_assessment else "fallback_rule_only",
            "data_sources": ["self_assessment"] if has_self_assessment else [],
            "profile_confidence": "medium" if has_self_assessment else "low",
        }

    @staticmethod
    def score_role_fit(
        assessment: Optional[Dict[str, Any]],
        role: str,
        *,
        assignment_mode: str = "strength_first",
    ) -> Dict[str, Any]:
        profile_payload = AssessmentService.build_standard_profile(assessment)
        standard_profile = profile_payload["standard_profile"]
        weights = AssessmentService.ROLE_ABILITY_MODEL.get(role, {})
        if not weights:
            raise ValueError("辩位不存在")

        dimension_contribution = {
            dimension: round(standard_profile[dimension] * weight, 2)
            for dimension, weight in weights.items()
        }
        strength_score = round(sum(dimension_contribution.values()), 2)
        if assignment_mode == "growth_first":
            target_gap = sum((100 - standard_profile[dimension]) * weight for dimension, weight in weights.items())
            fit_score = round(target_gap, 2)
        else:
            fit_score = strength_score

        return {
            "role": role,
            "fit_score": fit_score,
            "role_fit_score": fit_score,
            "strength_score": strength_score,
            "dimension_contribution": dimension_contribution,
            "assignment_reason": AssessmentService.ROLE_ASSIGNMENT_REASONS.get(role, ""),
            "data_basis": profile_payload["analysis_basis"],
            "analysis_basis": profile_payload["analysis_basis"],
            "data_sources": profile_payload["data_sources"],
            "profile_confidence": profile_payload["profile_confidence"],
            "standard_profile": standard_profile,
        }

    @staticmethod
    def build_role_fit_matrix(
        assessment: Optional[Dict[str, Any]],
        roles: Optional[List[str]] = None,
        *,
        assignment_mode: str = "strength_first",
    ) -> Dict[str, Dict[str, Any]]:
        roles = roles or list(AssessmentService.ROLE_ABILITY_MODEL.keys())
        return {
            role: AssessmentService.score_role_fit(
                assessment,
                role,
                assignment_mode=assignment_mode,
            )
            for role in roles
        }

    @staticmethod
    def recommend_role_from_profile(
        assessment: Optional[Dict[str, Any]],
        *,
        assignment_mode: str = "strength_first",
    ) -> str:
        fit_matrix = AssessmentService.build_role_fit_matrix(
            assessment,
            assignment_mode=assignment_mode,
        )
        return max(fit_matrix, key=lambda role: fit_matrix[role]["fit_score"])

    @staticmethod
    def recommend_role(
        expression_willingness: int,
        logical_thinking: int,
        personality_type: Optional[str] = None,
    ) -> str:
        """
        Recommend a debate role from the submitted assessment.

        The current rule only uses expression and logic scores. The optional
        ``personality_type`` is kept for future expansion and API compatibility.
        """

        _ = personality_type

        if logical_thinking >= 8 and expression_willingness >= 7:
            return "debater_1"
        if logical_thinking >= 7 and expression_willingness >= 6:
            return "debater_2"
        if expression_willingness >= 7 and logical_thinking >= 6:
            return "debater_3"
        return "debater_4"

    @staticmethod
    def _merge_analysis_context(
        profile_payload: Dict[str, Any],
        evidence_basis: Dict[str, Any],
    ) -> Dict[str, Any]:
        data_sources = set(profile_payload.get("data_sources") or [])
        history_scores = evidence_basis.get("history_scores") or []
        speech_stats = evidence_basis.get("speech_stats") or []

        overall_history = next(
            (item for item in history_scores if item.get("scope") == "overall"),
            {},
        )
        overall_speech = next(
            (item for item in speech_stats if item.get("scope") == "overall"),
            {},
        )
        has_history = int(overall_history.get("count") or 0) > 0
        has_speech = int(overall_speech.get("speech_count") or 0) > 0

        if has_history:
            data_sources.add("history_scores")
        if has_speech:
            data_sources.add("speech_stats")

        has_self = "self_assessment" in data_sources
        if has_self and has_history and has_speech:
            analysis_basis = "self_assessment_history_speech"
            profile_confidence = "high"
        elif has_self and has_history:
            analysis_basis = "self_assessment_plus_history"
            profile_confidence = "high"
        elif has_self and has_speech:
            analysis_basis = "self_assessment_plus_speech"
            profile_confidence = "high"
        elif has_self:
            analysis_basis = "self_assessment_only"
            profile_confidence = profile_payload.get("profile_confidence", "medium")
        elif has_history or has_speech:
            analysis_basis = "fallback_rule_plus_behavior"
            profile_confidence = "medium"
        else:
            analysis_basis = profile_payload.get("analysis_basis", "fallback_rule_only")
            profile_confidence = profile_payload.get("profile_confidence", "low")

        return {
            "analysis_basis": analysis_basis,
            "data_sources": sorted(data_sources),
            "profile_confidence": profile_confidence,
            "history_scores": history_scores,
            "speech_stats": speech_stats,
        }

    @staticmethod
    def _serialize_assessment(db: Session, assessment: AbilityAssessment) -> Dict[str, Any]:
        result = {
            "id": str(assessment.id),
            "personality_type": assessment.personality_type,
            "expression_willingness": (
                assessment.expression_willingness_score
                if assessment.expression_willingness_score is not None
                else assessment.expression_willingness * 10
            ),
            "logical_thinking": (
                assessment.logical_thinking_score
                if assessment.logical_thinking_score is not None
                else assessment.logical_thinking * 10
            ),
            "stablecoin_knowledge": (
                assessment.stablecoin_knowledge_score
                if assessment.stablecoin_knowledge_score is not None
                else 50
            ),
            "financial_knowledge": (
                assessment.financial_knowledge_score
                if assessment.financial_knowledge_score is not None
                else 50
            ),
            "critical_thinking": (
                assessment.critical_thinking_score
                if assessment.critical_thinking_score is not None
                else 50
            ),
            "is_default": bool(getattr(assessment, "is_default", False)),
            "recommended_role": assessment.recommended_role,
            "role_description": AssessmentService.ROLE_DESCRIPTIONS.get(
                assessment.recommended_role, ""
            ),
            "created_at": assessment.created_at.isoformat()
            if assessment.created_at
            else None,
        }
        profile_payload = AssessmentService.build_standard_profile(result)
        from services.role_assignment_learning_service import (
            RoleAssignmentLearningService,
        )

        evidence_basis = RoleAssignmentLearningService.build_student_evidence_basis(
            db=db,
            user_id=str(assessment.user_id),
            recommended_role=assessment.recommended_role,
        )
        merged_context = AssessmentService._merge_analysis_context(
            profile_payload,
            evidence_basis,
        )
        result.update(profile_payload)
        result["analysis_basis"] = merged_context["analysis_basis"]
        result["data_sources"] = merged_context["data_sources"]
        result["profile_confidence"] = merged_context["profile_confidence"]
        result["role_fit"] = AssessmentService.build_role_fit_matrix(result)
        result["role_assignment_basis"] = {
            "self_reported": list(profile_payload["standard_profile"].keys()),
            "history_scores": merged_context["history_scores"],
            "speech_stats": merged_context["speech_stats"],
            "analysis_basis": merged_context["analysis_basis"],
        }
        return result

    @staticmethod
    def submit_assessment(
        db: Session,
        user_id: str,
        personality_type: Optional[str],
        expression_willingness: int,
        logical_thinking: int,
        stablecoin_knowledge: int,
        financial_knowledge: int,
        critical_thinking: int,
    ) -> Dict[str, Any]:
        """Create or update the student's real assessment record."""

        def validate_score(score: int, name: str) -> None:
            if not isinstance(score, int):
                raise ValueError(f"{name}必须为整数")
            if not (0 <= score <= 100):
                raise ValueError(f"{name}必须在 0-100 之间")

        validate_score(expression_willingness, "语言表达")
        validate_score(logical_thinking, "逻辑思维")
        validate_score(stablecoin_knowledge, "AI伦理与科技素养")
        validate_score(financial_knowledge, "AI通识知识水平")
        validate_score(critical_thinking, "批判思维")

        expression_willingness_10 = max(
            1,
            min(
                10,
                int(math.ceil(expression_willingness / 10))
                if expression_willingness > 0
                else 1,
            ),
        )
        logical_thinking_10 = max(
            1,
            min(
                10,
                int(math.ceil(logical_thinking / 10)) if logical_thinking > 0 else 1,
            ),
        )

        recommended_role = AssessmentService.recommend_role_from_profile(
            {
                "expression_willingness": expression_willingness,
                "logical_thinking": logical_thinking,
                "stablecoin_knowledge": stablecoin_knowledge,
                "financial_knowledge": financial_knowledge,
                "critical_thinking": critical_thinking,
            }
        )

        assessment = (
            db.query(AbilityAssessment)
            .filter(AbilityAssessment.user_id == uuid.UUID(user_id))
            .first()
        )

        if assessment is None:
            assessment = AbilityAssessment(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
            )
            db.add(assessment)

        assessment.personality_type = personality_type
        assessment.expression_willingness = expression_willingness_10
        assessment.logical_thinking = logical_thinking_10
        assessment.expression_willingness_score = expression_willingness
        assessment.logical_thinking_score = logical_thinking
        assessment.stablecoin_knowledge_score = stablecoin_knowledge
        assessment.financial_knowledge_score = financial_knowledge
        assessment.critical_thinking_score = critical_thinking
        assessment.is_default = False
        assessment.recommended_role = recommended_role

        db.commit()
        db.refresh(assessment)

        result = AssessmentService._serialize_assessment(db, assessment)
        result["message"] = "评估完成"
        return result

    @staticmethod
    def get_assessment(
        db: Session,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Return the student's saved assessment.

        Missing data now stays missing. We no longer create or expose default
        placeholder rows when the student has not actually completed the
        assessment yet.
        """

        assessment = (
            db.query(AbilityAssessment)
            .filter(AbilityAssessment.user_id == uuid.UUID(user_id))
            .first()
        )

        if assessment is None:
            return None

        if bool(getattr(assessment, "is_default", False)):
            return None

        return AssessmentService._serialize_assessment(db, assessment)
