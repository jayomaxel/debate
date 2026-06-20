"""
Role assignment learning and calibration service.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.debate import (
    Debate,
    DebateParticipation,
    DebateRoleAssignmentAuditLog,
    DebateRoleAssignmentItem,
    DebateRoleAssignmentRun,
    DebateRolePerformanceSample,
)
from models.score import Score
from models.speech import Speech
from services.assessment_service import AssessmentService


class RoleAssignmentLearningService:
    """Build data-driven calibration signals for role assignment."""

    MODEL_VERSION = "sample_calibration_v1"
    DEFAULT_MIN_SAMPLE_SIZE = 8
    RESPONSE_TOKENS = ("回应", "反驳", "质疑", "问题", "因此", "但是")
    NEGATED_MISTAKE_HINTS = (
        "无明显违规",
        "无违规",
        "未违规",
        "未见违规",
        "无明显失误",
        "未见明显失误",
        "无重大失误",
        "无明显问题",
    )
    OBVIOUS_MISTAKE_HINTS = (
        "违规",
        "离题",
        "跑题",
        "逻辑混乱",
        "逻辑断裂",
        "事实错误",
        "人身攻击",
        "偷换概念",
        "恶意打断",
        "回应失焦",
        "未回应",
    )

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp(value: Any, minimum: float = 0.0, maximum: float = 100.0) -> float:
        return round(max(minimum, min(maximum, RoleAssignmentLearningService._safe_float(value))), 2)

    @staticmethod
    def _uuid(value: Any) -> Optional[uuid.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _score_average(scores: List[float]) -> float:
        values = [RoleAssignmentLearningService._safe_float(item) for item in scores if item is not None]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 2)

    @staticmethod
    def _score_std(scores: List[float]) -> float:
        values = [RoleAssignmentLearningService._safe_float(item) for item in scores if item is not None]
        if len(values) <= 1:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return round(math.sqrt(variance), 2)

    @staticmethod
    def _role_target_gap(role: str, standard_profile: Dict[str, Any]) -> float:
        weights = AssessmentService.ROLE_ABILITY_MODEL.get(role, {})
        if not weights:
            return 0.0
        gap = 0.0
        for dimension, weight in weights.items():
            gap += (100 - RoleAssignmentLearningService._safe_float(standard_profile.get(dimension), 50.0)) * float(weight)
        return round(gap, 2)

    @staticmethod
    def _historical_role_distribution(
        db: Session,
        user_id: str,
        role_pool: Optional[List[str]] = None,
        *,
        window_size: int = 10,
    ) -> List[Dict[str, Any]]:
        role_pool = role_pool or list(AssessmentService.ROLE_ABILITY_MODEL.keys())
        participations = (
            db.query(DebateParticipation)
            .join(Debate, DebateParticipation.debate_id == Debate.id)
            .filter(
                DebateParticipation.user_id == uuid.UUID(str(user_id)),
                DebateParticipation.left_at.is_(None),
                Debate.status == "completed",
                DebateParticipation.role.in_(role_pool),
            )
            .order_by(DebateParticipation.joined_at.desc())
            .limit(max(1, int(window_size or 10)))
            .all()
        )
        counts = {role: 0 for role in role_pool}
        for participation in participations:
            counts[str(participation.role)] = counts.get(str(participation.role), 0) + 1
        return [{"role": role, "count": counts.get(role, 0)} for role in role_pool]

    @staticmethod
    def _student_score_summary(
        db: Session,
        user_id: str,
        *,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = (
            db.query(Score.overall_score)
            .join(DebateParticipation, Score.participation_id == DebateParticipation.id)
            .join(Debate, DebateParticipation.debate_id == Debate.id)
            .filter(
                DebateParticipation.user_id == uuid.UUID(str(user_id)),
                Debate.status == "completed",
            )
        )
        if role:
            query = query.filter(DebateParticipation.role == role)
        values = [RoleAssignmentLearningService._safe_float(item[0]) for item in query.all()]
        return {
            "count": len(values),
            "average": RoleAssignmentLearningService._score_average(values),
            "volatility": RoleAssignmentLearningService._score_std(values),
        }

    @staticmethod
    def _student_speech_stats(
        db: Session,
        user_id: str,
        *,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = (
            db.query(Speech)
            .join(Debate, Speech.debate_id == Debate.id)
            .filter(
                Speech.speaker_id == uuid.UUID(str(user_id)),
                Speech.is_valid_for_scoring.is_(True),
                Debate.status == "completed",
            )
            .order_by(Speech.timestamp.desc())
        )
        if role:
            query = query.filter(Speech.speaker_role == role)
        speeches = query.all()
        if not speeches:
            return {
                "speech_count": 0,
                "average_duration": 0.0,
                "average_length": 0.0,
                "active_rounds": 0,
                "response_success_rate": 0.0,
            }
        durations = [RoleAssignmentLearningService._safe_float(getattr(item, "duration", 0.0)) for item in speeches]
        lengths = [len(str(getattr(item, "content", "") or "")) for item in speeches]
        response_like = [
            item
            for item in speeches
            if str(getattr(item, "phase", "") or "") in {"questioning", "free_debate"}
        ]
        response_hits = [
            item
            for item in response_like
            if any(
                token in str(getattr(item, "content", "") or "")
                for token in RoleAssignmentLearningService.RESPONSE_TOKENS
            )
        ]
        return {
            "speech_count": len(speeches),
            "average_duration": RoleAssignmentLearningService._score_average(durations),
            "average_length": RoleAssignmentLearningService._score_average(lengths),
            "active_rounds": len({str(getattr(item, "phase", "") or "") for item in speeches}),
            "response_success_rate": round((len(response_hits) / len(response_like)) * 100, 2) if response_like else 0.0,
        }

    @staticmethod
    def build_student_evidence_basis(
        db: Session,
        user_id: str,
        *,
        recommended_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        overall_history = RoleAssignmentLearningService._student_score_summary(
            db,
            user_id,
        )
        overall_speech = RoleAssignmentLearningService._student_speech_stats(
            db,
            user_id,
        )
        history_scores = [
            {
                "scope": "overall",
                **overall_history,
            }
        ]
        speech_stats = [
            {
                "scope": "overall",
                **overall_speech,
            }
        ]
        if recommended_role:
            history_scores.append(
                {
                    "scope": "recommended_role",
                    "role": recommended_role,
                    **RoleAssignmentLearningService._student_score_summary(
                        db,
                        user_id,
                        role=recommended_role,
                    ),
                }
            )
            speech_stats.append(
                {
                    "scope": "recommended_role",
                    "role": recommended_role,
                    **RoleAssignmentLearningService._student_speech_stats(
                        db,
                        user_id,
                        role=recommended_role,
                    ),
                }
            )
        return {
            "history_scores": history_scores,
            "speech_stats": speech_stats,
        }

    @staticmethod
    def _count_obvious_mistakes(score_rows: List[Score]) -> int:
        count = 0
        for score in score_rows:
            feedback = str(getattr(score, "feedback", "") or "").strip()
            if not feedback:
                continue
            if any(token in feedback for token in RoleAssignmentLearningService.NEGATED_MISTAKE_HINTS):
                continue
            if any(token in feedback for token in RoleAssignmentLearningService.OBVIOUS_MISTAKE_HINTS):
                count += 1
        return count

    @staticmethod
    def _teacher_override_rate(db: Session, user_id: str) -> float:
        total = (
            db.query(DebateRoleAssignmentItem)
            .join(DebateRoleAssignmentRun, DebateRoleAssignmentItem.run_id == DebateRoleAssignmentRun.id)
            .filter(
                DebateRoleAssignmentItem.user_id == uuid.UUID(str(user_id)),
                DebateRoleAssignmentRun.is_temporary.is_(False),
            )
            .count()
        )
        if total <= 0:
            return 0.0
        overridden = (
            db.query(DebateRoleAssignmentItem)
            .join(DebateRoleAssignmentRun, DebateRoleAssignmentItem.run_id == DebateRoleAssignmentRun.id)
            .filter(
                DebateRoleAssignmentItem.user_id == uuid.UUID(str(user_id)),
                DebateRoleAssignmentItem.teacher_override.is_(True),
                DebateRoleAssignmentRun.is_temporary.is_(False),
            )
            .count()
        )
        return round((overridden / total) * 100, 2)

    @staticmethod
    def build_feature_vector(
        db: Session,
        user_id: str,
        role: str,
        *,
        assignment_mode: str,
        role_rotation_policy: str,
        role_pool: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        assessment = AssessmentService.get_assessment(db=db, user_id=user_id) or {}
        profile_payload = AssessmentService.build_standard_profile(assessment)
        standard_profile = profile_payload["standard_profile"]
        historical_distribution = RoleAssignmentLearningService._historical_role_distribution(
            db,
            user_id,
            role_pool,
        )
        overall_summary = RoleAssignmentLearningService._student_score_summary(db, user_id)
        role_summary = RoleAssignmentLearningService._student_score_summary(db, user_id, role=role)
        overall_speech_stats = RoleAssignmentLearningService._student_speech_stats(db, user_id)
        role_speech_stats = RoleAssignmentLearningService._student_speech_stats(db, user_id, role=role)
        return {
            "standard_profile": standard_profile,
            "analysis_basis": profile_payload.get("analysis_basis"),
            "data_sources": profile_payload.get("data_sources", []),
            "profile_confidence": profile_payload.get("profile_confidence"),
            "historical_role_distribution": historical_distribution,
            "historical_score_average": overall_summary["average"],
            "historical_score_volatility": overall_summary["volatility"],
            "historical_role_score_average": role_summary["average"],
            "historical_role_score_count": role_summary["count"],
            "speech_stats": overall_speech_stats,
            "role_speech_stats": role_speech_stats,
            "teacher_override_rate": RoleAssignmentLearningService._teacher_override_rate(db, user_id),
            "training_goal_mode": assignment_mode,
            "rotation_policy": role_rotation_policy,
            "role_target_gap": RoleAssignmentLearningService._role_target_gap(role, standard_profile),
        }

    @staticmethod
    def _profile_similarity(current_profile: Dict[str, Any], sample_profile: Dict[str, Any]) -> float:
        dimensions = AssessmentService.STANDARD_PROFILE_FIELDS
        distance = 0.0
        for dimension in dimensions:
            distance += abs(
                RoleAssignmentLearningService._safe_float(current_profile.get(dimension), 50.0)
                - RoleAssignmentLearningService._safe_float(sample_profile.get(dimension), 50.0)
            )
        max_distance = len(dimensions) * 100.0
        return round(max(0.0, 1.0 - (distance / max_distance)), 4)

    @staticmethod
    def _similar_role_prior(
        db: Session,
        role: str,
        standard_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        samples = (
            db.query(DebateRolePerformanceSample)
            .filter(
                DebateRolePerformanceSample.role == role,
                DebateRolePerformanceSample.overall_score.isnot(None),
            )
            .order_by(DebateRolePerformanceSample.created_at.desc())
            .limit(200)
            .all()
        )
        if not samples:
            return {
                "role_sample_count": 0,
                "predicted_performance_score": 0.0,
                "predicted_growth_gain": 0.0,
                "feature_importance": [],
                "model_basis": {"source": "no_sample"},
            }

        weighted_scores: List[float] = []
        weighted_growth: List[float] = []
        weights: List[float] = []
        for sample in samples:
            sample_profile = sample.standard_profile if isinstance(sample.standard_profile, dict) else {}
            similarity = RoleAssignmentLearningService._profile_similarity(standard_profile, sample_profile) or 0.1
            weighted_scores.append(RoleAssignmentLearningService._safe_float(sample.overall_score) * similarity)
            growth_proxy = RoleAssignmentLearningService._safe_float(
                (sample.label_vector or {}).get("growth_proxy"),
                RoleAssignmentLearningService._safe_float(sample.response_success_rate, 0.0) * 0.4
                + max(0.0, 100.0 - RoleAssignmentLearningService._safe_float(sample.logic_score, 0.0)) * 0.1,
            )
            weighted_growth.append(growth_proxy * similarity)
            weights.append(similarity)

        weight_total = sum(weights) or 1.0
        predicted_performance = round(sum(weighted_scores) / weight_total, 2)
        predicted_growth = round(sum(weighted_growth) / weight_total, 2)

        role_weights = AssessmentService.ROLE_ABILITY_MODEL.get(role, {})
        feature_importance = [
            {"feature": dimension, "weight": round(float(weight), 4)}
            for dimension, weight in sorted(role_weights.items(), key=lambda item: item[1], reverse=True)
        ]
        return {
            "role_sample_count": len(samples),
            "predicted_performance_score": RoleAssignmentLearningService._clamp(predicted_performance),
            "predicted_growth_gain": RoleAssignmentLearningService._clamp(predicted_growth),
            "feature_importance": feature_importance,
            "model_basis": {
                "source": "similar_role_samples",
                "sample_count": len(samples),
                "weight_total": round(weight_total, 4),
            },
        }

    @staticmethod
    def predict_role_scores(
        db: Session,
        user_id: str,
        role: str,
        *,
        assignment_mode: str,
        role_rotation_policy: str,
        role_pool: Optional[List[str]],
        rule_fit_score: float,
    ) -> Dict[str, Any]:
        feature_vector = RoleAssignmentLearningService.build_feature_vector(
            db,
            user_id,
            role,
            assignment_mode=assignment_mode,
            role_rotation_policy=role_rotation_policy,
            role_pool=role_pool,
        )
        standard_profile = feature_vector["standard_profile"]
        role_prior = RoleAssignmentLearningService._similar_role_prior(db, role, standard_profile)
        own_role_average = RoleAssignmentLearningService._safe_float(feature_vector.get("historical_role_score_average"), 0.0)
        own_role_count = int(feature_vector.get("historical_role_score_count") or 0)

        if own_role_count > 0:
            predicted_performance = (
                own_role_average * 0.55
                + RoleAssignmentLearningService._safe_float(role_prior["predicted_performance_score"], rule_fit_score) * 0.45
            )
        elif int(role_prior.get("role_sample_count") or 0) > 0:
            predicted_performance = (
                RoleAssignmentLearningService._safe_float(role_prior["predicted_performance_score"], rule_fit_score) * 0.65
                + RoleAssignmentLearningService._safe_float(rule_fit_score) * 0.35
            )
        else:
            predicted_performance = RoleAssignmentLearningService._safe_float(rule_fit_score)

        gap_score = RoleAssignmentLearningService._safe_float(feature_vector.get("role_target_gap"), 0.0)
        distribution_gap = max(
            0.0,
            4.0 - max((item.get("count", 0) for item in feature_vector.get("historical_role_distribution", [])), default=0),
        ) * 6.0
        predicted_growth = (
            RoleAssignmentLearningService._safe_float(role_prior["predicted_growth_gain"], 0.0) * 0.45
            + gap_score * 0.35
            + distribution_gap * 0.20
        )

        sample_count = int(role_prior.get("role_sample_count") or 0) + own_role_count
        confidence = min(100.0, 20.0 + sample_count * 6.5)
        if own_role_count <= 0 and int(role_prior.get("role_sample_count") or 0) <= 0:
            confidence = 15.0

        model_basis = {
            **(role_prior.get("model_basis") or {}),
            "own_role_sample_count": own_role_count,
            "own_role_average": own_role_average,
            "historical_score_average": feature_vector.get("historical_score_average"),
            "historical_score_volatility": feature_vector.get("historical_score_volatility"),
            "teacher_override_rate": feature_vector.get("teacher_override_rate"),
            "assignment_mode": assignment_mode,
            "rotation_policy": role_rotation_policy,
            "model_version": RoleAssignmentLearningService.MODEL_VERSION,
        }
        return {
            "model_version": RoleAssignmentLearningService.MODEL_VERSION,
            "predicted_performance_score": RoleAssignmentLearningService._clamp(predicted_performance),
            "predicted_growth_gain": RoleAssignmentLearningService._clamp(predicted_growth),
            "confidence": RoleAssignmentLearningService._clamp(confidence),
            "feature_importance": role_prior.get("feature_importance", []),
            "model_basis": model_basis,
            "feature_vector": feature_vector,
        }

    @staticmethod
    def materialize_debate_samples(db: Session, debate_id: str) -> List[Dict[str, Any]]:
        debate_uuid = RoleAssignmentLearningService._uuid(debate_id)
        if debate_uuid is None:
            raise ValueError("invalid debate_id")
        debate = db.query(Debate).filter(Debate.id == debate_uuid).first()
        if not debate or str(debate.status) != "completed":
            return []

        latest_run = (
            db.query(DebateRoleAssignmentRun)
            .filter(
                DebateRoleAssignmentRun.debate_id == debate_uuid,
                DebateRoleAssignmentRun.is_temporary.is_(False),
            )
            .order_by(DebateRoleAssignmentRun.created_at.desc())
            .first()
        )
        item_by_user_id: Dict[str, DebateRoleAssignmentItem] = {}
        if latest_run:
            item_by_user_id = {
                str(item.user_id): item
                for item in latest_run.items
                if item.user_id is not None
            }

        participations = (
            db.query(DebateParticipation)
            .filter(
                DebateParticipation.debate_id == debate_uuid,
                DebateParticipation.user_id.isnot(None),
            )
            .all()
        )
        results: List[Dict[str, Any]] = []
        for participation in participations:
            if not participation.user_id:
                continue
            user_id = str(participation.user_id)
            score_rows = (
                db.query(Score)
                .filter(Score.participation_id == participation.id)
                .all()
            )
            speeches = (
                db.query(Speech)
                .filter(
                    Speech.debate_id == debate_uuid,
                    Speech.speaker_id == participation.user_id,
                    Speech.is_valid_for_scoring.is_(True),
                )
                .all()
            )
            if not score_rows and not speeches:
                continue

            item = item_by_user_id.get(user_id)
            feature_vector = RoleAssignmentLearningService.build_feature_vector(
                db,
                user_id,
                str(participation.role),
                assignment_mode=(latest_run.assignment_mode if latest_run else "strength_first"),
                role_rotation_policy=(latest_run.rotation_policy if latest_run else "balanced_rotation"),
                role_pool=list(AssessmentService.ROLE_ABILITY_MODEL.keys()),
            )
            stage_scores: Dict[str, List[float]] = defaultdict(list)
            speech_by_id = {str(speech.id): speech for speech in speeches}
            for score_row in score_rows:
                speech = speech_by_id.get(str(score_row.speech_id))
                if speech is None:
                    continue
                stage_scores[str(speech.phase)].append(RoleAssignmentLearningService._safe_float(score_row.overall_score))

            label_vector = {
                "phase_scores": {
                    phase: RoleAssignmentLearningService._score_average(values)
                    for phase, values in stage_scores.items()
                },
                "growth_proxy": round(
                    RoleAssignmentLearningService._safe_float(feature_vector.get("role_target_gap"), 0.0) * 0.30
                    + RoleAssignmentLearningService._safe_float(feature_vector.get("role_speech_stats", {}).get("response_success_rate"), 0.0) * 0.35
                    + RoleAssignmentLearningService._safe_float(feature_vector.get("speech_stats", {}).get("active_rounds"), 0.0) * 5.0,
                    2,
                ),
            }
            score_values = {
                "overall_score": RoleAssignmentLearningService._score_average([score.overall_score for score in score_rows]),
                "logic_score": RoleAssignmentLearningService._score_average([score.logic_score for score in score_rows]),
                "argument_score": RoleAssignmentLearningService._score_average([score.argument_score for score in score_rows]),
                "response_score": RoleAssignmentLearningService._score_average([score.response_score for score in score_rows]),
                "persuasion_score": RoleAssignmentLearningService._score_average([score.persuasion_score for score in score_rows]),
                "teamwork_score": RoleAssignmentLearningService._score_average([score.teamwork_score for score in score_rows]),
            }
            speech_stats = RoleAssignmentLearningService._student_speech_stats(db, user_id, role=str(participation.role))
            existing = (
                db.query(DebateRolePerformanceSample)
                .filter(
                    DebateRolePerformanceSample.debate_id == debate_uuid,
                    DebateRolePerformanceSample.user_id == participation.user_id,
                    DebateRolePerformanceSample.role == str(participation.role),
                )
                .first()
            )
            sample = existing or DebateRolePerformanceSample(
                debate_id=debate_uuid,
                participation_id=participation.id,
                user_id=participation.user_id,
                class_id=debate.class_id,
                role=str(participation.role),
            )
            sample.class_id = debate.class_id
            sample.assignment_run_id = latest_run.id if latest_run else None
            sample.assignment_item_id = item.id if item else None
            sample.assignment_mode = latest_run.assignment_mode if latest_run else None
            sample.rotation_policy = latest_run.rotation_policy if latest_run else None
            sample.rule_fit_score = item.rule_fit_score if item else None
            sample.model_score = item.model_score if item else None
            sample.growth_score = item.growth_score if item else None
            sample.final_assignment_score = item.final_score if item else None
            sample.overall_score = score_values["overall_score"]
            sample.logic_score = score_values["logic_score"]
            sample.argument_score = score_values["argument_score"]
            sample.response_score = score_values["response_score"]
            sample.persuasion_score = score_values["persuasion_score"]
            sample.teamwork_score = score_values["teamwork_score"]
            sample.speech_count = speech_stats["speech_count"]
            sample.total_duration_sec = int(round(sum(RoleAssignmentLearningService._safe_float(getattr(speech, "duration", 0.0)) for speech in speeches)))
            sample.average_speech_length = speech_stats["average_length"]
            sample.response_success_rate = speech_stats["response_success_rate"]
            sample.active_rounds = speech_stats["active_rounds"]
            sample.obvious_mistake_count = RoleAssignmentLearningService._count_obvious_mistakes(score_rows)
            sample.teacher_feedback = None
            sample.student_reflection = None
            sample.mentor_feedback = None
            sample.report_summary = (
                (debate.report or {}).get("winning_reason")
                if isinstance(debate.report, dict)
                else None
            )
            sample.standard_profile = feature_vector.get("standard_profile")
            sample.historical_role_distribution = feature_vector.get("historical_role_distribution")
            sample.feature_vector = feature_vector
            sample.label_vector = label_vector
            if existing is None:
                db.add(sample)
            results.append(
                {
                    "user_id": user_id,
                    "role": str(participation.role),
                    "overall_score": sample.overall_score,
                }
            )

        db.commit()
        return results
