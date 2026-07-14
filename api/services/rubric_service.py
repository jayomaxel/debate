"""
Rubric service for work package A.

The rubric keeps the legacy five score dimensions stable while adding the
three-layer semantics required by the A package contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping

from services.mode_policy_service import DEFAULT_MODE, ModePolicyService


RUBRIC_VERSION = "a.rubric.v1"
LEGACY_SCORE_FIELDS = (
    "logic_score",
    "argument_score",
    "response_score",
    "persuasion_score",
    "teamwork_score",
)
STANDARD_DIMENSIONS = ("logic", "argument", "response", "persuasion", "teamwork")
DEBATER_ROLES = ("debater_1", "debater_2", "debater_3", "debater_4")


@dataclass(frozen=True)
class ScoreLayerWeights:
    common_argument_weight: float = 0.55
    role_fulfillment_weight: float = 0.30
    team_process_weight: float = 0.15

    def to_dict(self) -> Dict[str, float]:
        return {
            "common_argument_weight": self.common_argument_weight,
            "role_fulfillment_weight": self.role_fulfillment_weight,
            "team_process_weight": self.team_process_weight,
        }

    def total(self) -> float:
        return (
            self.common_argument_weight
            + self.role_fulfillment_weight
            + self.team_process_weight
        )


@dataclass(frozen=True)
class FallbackPolicy:
    judge_retry_limit: int = 1
    repair_retry_limit: int = 1
    allow_partial: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "judge_retry_limit": self.judge_retry_limit,
            "repair_retry_limit": self.repair_retry_limit,
            "allow_partial": self.allow_partial,
        }


@dataclass(frozen=True)
class RoleRubric:
    role: str
    responsibilities: Dict[str, str]
    dimension_weights: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "responsibilities": dict(self.responsibilities),
            "dimension_weights": dict(self.dimension_weights),
        }


@dataclass(frozen=True)
class ScoringPolicy:
    mode: str = DEFAULT_MODE
    scale: str = "ordinal_1_4"
    final_score_mapping: str = "percent"
    version: str = RUBRIC_VERSION
    score_layers: ScoreLayerWeights = field(default_factory=ScoreLayerWeights)
    fallback_policy: FallbackPolicy = field(default_factory=FallbackPolicy)
    role_dimension_weights: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "scale": self.scale,
            "final_score_mapping": self.final_score_mapping,
            "version": self.version,
            "score_layers": self.score_layers.to_dict(),
            "fallback_policy": self.fallback_policy.to_dict(),
            "role_dimension_weights": {
                role: dict(weights)
                for role, weights in self.role_dimension_weights.items()
            },
        }


class RubricService:
    """Provides stable rubric, role weight, and score mapping helpers."""

    _ROLE_RUBRICS: Dict[str, RoleRubric] = {
        "debater_1": RoleRubric(
            role="debater_1",
            responsibilities={
                "definition": "define key concepts",
                "framework": "build the debate frame",
                "main_claim": "establish main claims",
            },
            dimension_weights={
                "logic": 0.32,
                "argument": 0.30,
                "response": 0.12,
                "persuasion": 0.16,
                "teamwork": 0.10,
            },
        ),
        "debater_2": RoleRubric(
            role="debater_2",
            responsibilities={
                "question_design": "design useful questions",
                "evidence_followup": "press evidence gaps",
                "weakness_detection": "identify weak assumptions",
            },
            dimension_weights={
                "logic": 0.20,
                "argument": 0.22,
                "response": 0.32,
                "persuasion": 0.14,
                "teamwork": 0.12,
            },
        ),
        "debater_3": RoleRubric(
            role="debater_3",
            responsibilities={
                "rebuttal_integration": "integrate rebuttals",
                "attack_defense_shift": "switch between attack and defense",
                "live_response": "respond to live clashes",
            },
            dimension_weights={
                "logic": 0.22,
                "argument": 0.20,
                "response": 0.34,
                "persuasion": 0.14,
                "teamwork": 0.10,
            },
        ),
        "debater_4": RoleRubric(
            role="debater_4",
            responsibilities={
                "summary": "summarize the debate",
                "weighing": "weigh values and impacts",
                "winner_reason": "explain decisive reasons",
            },
            dimension_weights={
                "logic": 0.26,
                "argument": 0.22,
                "response": 0.16,
                "persuasion": 0.24,
                "teamwork": 0.12,
            },
        ),
    }

    @classmethod
    def get_role_rubric(cls, speaker_role: str | None) -> RoleRubric:
        role = str(speaker_role or "debater_1").strip()
        return cls._ROLE_RUBRICS.get(role, cls._ROLE_RUBRICS["debater_1"])

    @classmethod
    def get_scoring_policy(cls, mode: str | None = None) -> ScoringPolicy:
        normalized_mode = ModePolicyService.normalize_mode(mode)
        return ScoringPolicy(
            mode=normalized_mode,
            role_dimension_weights={
                role: rubric.dimension_weights
                for role, rubric in cls._ROLE_RUBRICS.items()
            },
        )

    @classmethod
    def validate_policy(cls, policy: ScoringPolicy | None = None) -> Dict[str, Any]:
        policy = policy or cls.get_scoring_policy()
        errors = []
        if round(policy.score_layers.total(), 6) != 1.0:
            errors.append("score layer weights must sum to 1.0")

        for role in DEBATER_ROLES:
            if role not in policy.role_dimension_weights:
                errors.append(f"missing role weights: {role}")
                continue
            total = sum(float(value) for value in policy.role_dimension_weights[role].values())
            if round(total, 6) != 1.0:
                errors.append(f"role weights must sum to 1.0: {role}")

        return {"valid": not errors, "errors": errors}

    @classmethod
    def ordinal_to_percent(cls, value: float | int) -> float:
        score = max(1.0, min(4.0, float(value)))
        return round(25.0 + ((score - 1.0) / 3.0) * 75.0, 2)

    @classmethod
    def combine_layer_scores(
        cls,
        common_argument_score: float,
        role_fulfillment_score: float,
        team_process_score: float,
        policy: ScoringPolicy | None = None,
    ) -> float:
        policy = policy or cls.get_scoring_policy()
        weights = policy.score_layers
        combined = (
            float(common_argument_score) * weights.common_argument_weight
            + float(role_fulfillment_score) * weights.role_fulfillment_weight
            + float(team_process_score) * weights.team_process_weight
        )
        return round(max(0.0, min(100.0, combined)), 2)

    @classmethod
    def weighted_dimension_score(
        cls,
        scores: Mapping[str, Any],
        speaker_role: str | None = None,
    ) -> float:
        rubric = cls.get_role_rubric(speaker_role)
        total = 0.0
        for dimension, weight in rubric.dimension_weights.items():
            legacy_key = f"{dimension}_score"
            total += float(scores.get(legacy_key, scores.get(dimension, 0)) or 0) * weight
        return round(max(0.0, min(100.0, total)), 2)

    @classmethod
    def build_participant_score(
        cls,
        speaker_role: str,
        legacy_scores: Mapping[str, Any],
        *,
        role_fulfillment_score: float | None = None,
        team_process_score: float | None = None,
        mode: str | None = None,
    ) -> Dict[str, Any]:
        policy = cls.get_scoring_policy(mode)
        common_score = cls.weighted_dimension_score(legacy_scores, speaker_role)
        role_score = float(role_fulfillment_score if role_fulfillment_score is not None else common_score)
        team_score = float(team_process_score if team_process_score is not None else legacy_scores.get("teamwork_score", 0) or 0)
        final_score = cls.combine_layer_scores(common_score, role_score, team_score, policy)
        return {
            "speaker_role": speaker_role,
            "rubric_version": policy.version,
            "common_argument_score": round(common_score, 2),
            "role_fulfillment_score": round(max(0.0, min(100.0, role_score)), 2),
            "team_process_score": round(max(0.0, min(100.0, team_score)), 2),
            "overall_score": final_score,
            "legacy_scores": {key: legacy_scores.get(key, 0) for key in LEGACY_SCORE_FIELDS},
            "role_rubric": cls.get_role_rubric(speaker_role).to_dict(),
        }

    @classmethod
    def role_rubrics(cls) -> Iterable[RoleRubric]:
        return tuple(cls._ROLE_RUBRICS.values())


def get_scoring_policy(mode: str | None = None) -> ScoringPolicy:
    return RubricService.get_scoring_policy(mode)
