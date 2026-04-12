"""
Ability assessment service.
"""

from typing import Any, Dict, Optional

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
    def _serialize_assessment(assessment: AbilityAssessment) -> Dict[str, Any]:
        return {
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

        recommended_role = AssessmentService.recommend_role(
            expression_willingness=expression_willingness_10,
            logical_thinking=logical_thinking_10,
            personality_type=personality_type,
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

        result = AssessmentService._serialize_assessment(assessment)
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

        return AssessmentService._serialize_assessment(assessment)
