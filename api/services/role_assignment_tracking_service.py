"""
Persistent tracking for role assignment runs, items, and audit logs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.debate import (
    DebateRoleAssignmentAuditLog,
    DebateRoleAssignmentItem,
    DebateRoleAssignmentRun,
)


class RoleAssignmentTrackingService:
    """Store and read role assignment tracking records."""

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
    def create_assignment_run(
        db: Session,
        *,
        debate_id: Optional[str] = None,
        reservation_id: Optional[str] = None,
        class_id: Optional[str] = None,
        source: str,
        target_mode: Optional[str],
        assignment_mode: str,
        rotation_policy: Optional[str],
        model_version: Optional[str],
        created_by: Optional[str],
        results: List[Dict[str, Any]],
        summary: Optional[Dict[str, Any]] = None,
        parent_run_id: Optional[str] = None,
        is_temporary: bool = False,
        prompt_pack_version: Optional[str] = None,
        preview_token: Optional[str] = None,
        previous_snapshot_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> DebateRoleAssignmentRun:
        previous_snapshot_map = previous_snapshot_map or {}
        if is_temporary and not preview_token:
            preview_token = uuid.uuid4().hex
        run = DebateRoleAssignmentRun(
            parent_run_id=RoleAssignmentTrackingService._uuid(parent_run_id),
            debate_id=RoleAssignmentTrackingService._uuid(debate_id),
            reservation_id=RoleAssignmentTrackingService._uuid(reservation_id),
            class_id=RoleAssignmentTrackingService._uuid(class_id),
            source=str(source),
            target_mode=str(target_mode) if target_mode else None,
            assignment_mode=str(assignment_mode),
            rotation_policy=str(rotation_policy) if rotation_policy else None,
            model_version=str(model_version) if model_version else None,
            prompt_pack_version=str(prompt_pack_version) if prompt_pack_version else None,
            created_by=RoleAssignmentTrackingService._uuid(created_by),
            preview_token=preview_token,
            is_temporary=bool(is_temporary),
            summary=summary or {},
        )
        db.add(run)
        db.flush()

        for item_payload in results:
            user_id = RoleAssignmentTrackingService._uuid(item_payload.get("user_id"))
            if user_id is None:
                continue
            item = DebateRoleAssignmentItem(
                run_id=run.id,
                user_id=user_id,
                assignment_source=item_payload.get("assignment_source"),
                recommended_role=item_payload.get("recommended_role"),
                assigned_role=item_payload.get("assigned_role"),
                final_role=item_payload.get("assigned_role"),
                teacher_override=bool(item_payload.get("teacher_override")),
                override_reason=item_payload.get("override_reason"),
                fit_score=item_payload.get("fit_score"),
                rule_fit_score=item_payload.get("rule_fit_score"),
                final_score=item_payload.get("final_score"),
                fairness_penalty=(
                    float(item_payload.get("repeat_penalty") or 0.0)
                    + float(item_payload.get("imbalance_penalty") or 0.0)
                ),
                repeat_penalty=item_payload.get("repeat_penalty"),
                imbalance_penalty=item_payload.get("imbalance_penalty"),
                growth_bonus=item_payload.get("growth_bonus"),
                model_score=item_payload.get("model_score"),
                growth_score=item_payload.get("growth_score"),
                confidence=item_payload.get("confidence"),
                dimension_contribution=item_payload.get("dimension_contribution"),
                feature_importance=item_payload.get("feature_importance"),
                model_basis=item_payload.get("model_basis"),
                analysis_basis=item_payload.get("analysis_basis"),
                data_sources=item_payload.get("data_sources"),
                standard_profile=item_payload.get("standard_profile"),
                historical_role_distribution=item_payload.get("historical_role_distribution"),
            )
            db.add(item)
            db.flush()

            previous_snapshot = previous_snapshot_map.get(str(user_id), {})
            recommended_role = item_payload.get("recommended_role")
            assigned_role = item_payload.get("assigned_role")
            override_reason = item_payload.get("override_reason")
            if recommended_role and assigned_role and recommended_role != assigned_role:
                db.add(
                    DebateRoleAssignmentAuditLog(
                        run_id=run.id,
                        debate_id=run.debate_id,
                        reservation_id=run.reservation_id,
                        operator_id=run.created_by,
                        user_id=user_id,
                        from_role=recommended_role,
                        to_role=assigned_role,
                        reason=override_reason or "teacher_override",
                        action_type="teacher_override",
                        payload={
                            "assignment_source": item_payload.get("assignment_source"),
                            "model_basis": item_payload.get("model_basis"),
                        },
                    )
                )

            previous_final_role = previous_snapshot.get("assigned_role") or previous_snapshot.get("final_role")
            if previous_final_role and assigned_role and previous_final_role != assigned_role:
                db.add(
                    DebateRoleAssignmentAuditLog(
                        run_id=run.id,
                        debate_id=run.debate_id,
                        reservation_id=run.reservation_id,
                        operator_id=run.created_by,
                        user_id=user_id,
                        from_role=previous_final_role,
                        to_role=assigned_role,
                        reason=override_reason or "assignment_recomputed",
                        action_type="seat_reassignment",
                        payload={
                            "previous_snapshot": previous_snapshot,
                            "current_result": item_payload,
                        },
                    )
        )
        return run

    @staticmethod
    def get_run_by_id(
        db: Session,
        run_id: str,
        *,
        include_temporary: bool = True,
    ) -> Optional[DebateRoleAssignmentRun]:
        run_uuid = RoleAssignmentTrackingService._uuid(run_id)
        if run_uuid is None:
            return None
        query = db.query(DebateRoleAssignmentRun).filter(
            DebateRoleAssignmentRun.id == run_uuid,
        )
        if not include_temporary:
            query = query.filter(DebateRoleAssignmentRun.is_temporary.is_(False))
        return query.first()

    @staticmethod
    def get_latest_run(
        db: Session,
        *,
        debate_id: Optional[str] = None,
        reservation_id: Optional[str] = None,
        include_temporary: bool = False,
    ) -> Optional[DebateRoleAssignmentRun]:
        query = db.query(DebateRoleAssignmentRun)
        if debate_id:
            query = query.filter(DebateRoleAssignmentRun.debate_id == RoleAssignmentTrackingService._uuid(debate_id))
        if reservation_id:
            query = query.filter(DebateRoleAssignmentRun.reservation_id == RoleAssignmentTrackingService._uuid(reservation_id))
        if not include_temporary:
            query = query.filter(DebateRoleAssignmentRun.is_temporary.is_(False))
        return query.order_by(DebateRoleAssignmentRun.created_at.desc()).first()

    @staticmethod
    def list_audit_logs(
        db: Session,
        *,
        debate_id: Optional[str] = None,
        reservation_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[DebateRoleAssignmentAuditLog]:
        query = db.query(DebateRoleAssignmentAuditLog)
        if debate_id:
            query = query.filter(DebateRoleAssignmentAuditLog.debate_id == RoleAssignmentTrackingService._uuid(debate_id))
        if reservation_id:
            query = query.filter(DebateRoleAssignmentAuditLog.reservation_id == RoleAssignmentTrackingService._uuid(reservation_id))
        return query.order_by(DebateRoleAssignmentAuditLog.created_at.desc()).limit(max(1, int(limit or 50))).all()

    @staticmethod
    def cleanup_temporary_runs(
        db: Session,
        *,
        created_by: Optional[str] = None,
        class_id: Optional[str] = None,
        keep_latest: int = 12,
        max_age_hours: int = 24,
    ) -> int:
        query = db.query(DebateRoleAssignmentRun).filter(
            DebateRoleAssignmentRun.is_temporary.is_(True),
        )
        creator_uuid = RoleAssignmentTrackingService._uuid(created_by)
        if creator_uuid is not None:
            query = query.filter(DebateRoleAssignmentRun.created_by == creator_uuid)
        class_uuid = RoleAssignmentTrackingService._uuid(class_id)
        if class_uuid is not None:
            query = query.filter(DebateRoleAssignmentRun.class_id == class_uuid)

        runs = query.order_by(DebateRoleAssignmentRun.created_at.desc()).all()
        if not runs:
            return 0

        keep_latest = max(0, int(keep_latest or 0))
        cutoff = datetime.utcnow() - timedelta(hours=max(1, int(max_age_hours or 24)))
        deleted = 0
        for index, run in enumerate(runs):
            created_at = run.created_at or datetime.utcnow()
            should_delete = created_at < cutoff or index >= keep_latest
            if not should_delete:
                continue
            db.delete(run)
            deleted += 1
        return deleted

    @staticmethod
    def serialize_run(run: Optional[DebateRoleAssignmentRun]) -> Optional[Dict[str, Any]]:
        if run is None:
            return None
        return {
            "run_id": str(run.id),
            "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
            "debate_id": str(run.debate_id) if run.debate_id else None,
            "reservation_id": str(run.reservation_id) if run.reservation_id else None,
            "class_id": str(run.class_id) if run.class_id else None,
            "source": run.source,
            "target_mode": run.target_mode,
            "assignment_mode": run.assignment_mode,
            "rotation_policy": run.rotation_policy,
            "model_version": run.model_version,
            "prompt_pack_version": run.prompt_pack_version,
            "created_by": str(run.created_by) if run.created_by else None,
            "preview_token": run.preview_token,
            "is_temporary": bool(run.is_temporary),
            "summary": run.summary or {},
            "items": [RoleAssignmentTrackingService.serialize_item(item) for item in run.items],
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }

    @staticmethod
    def serialize_item(item: DebateRoleAssignmentItem) -> Dict[str, Any]:
        return {
            "item_id": str(item.id),
            "user_id": str(item.user_id),
            "assignment_source": item.assignment_source,
            "recommended_role": item.recommended_role,
            "assigned_role": item.assigned_role,
            "final_role": item.final_role,
            "teacher_override": bool(item.teacher_override),
            "override_reason": item.override_reason,
            "fit_score": item.fit_score,
            "rule_fit_score": item.rule_fit_score,
            "final_score": item.final_score,
            "fairness_penalty": item.fairness_penalty,
            "repeat_penalty": item.repeat_penalty,
            "imbalance_penalty": item.imbalance_penalty,
            "growth_bonus": item.growth_bonus,
            "model_score": item.model_score,
            "growth_score": item.growth_score,
            "confidence": item.confidence,
            "dimension_contribution": item.dimension_contribution,
            "feature_importance": item.feature_importance,
            "model_basis": item.model_basis,
            "analysis_basis": item.analysis_basis,
            "data_sources": item.data_sources,
            "standard_profile": item.standard_profile,
            "historical_role_distribution": item.historical_role_distribution,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    @staticmethod
    def serialize_audit_log(log: DebateRoleAssignmentAuditLog) -> Dict[str, Any]:
        return {
            "audit_log_id": str(log.id),
            "run_id": str(log.run_id) if log.run_id else None,
            "debate_id": str(log.debate_id) if log.debate_id else None,
            "reservation_id": str(log.reservation_id) if log.reservation_id else None,
            "operator_id": str(log.operator_id) if log.operator_id else None,
            "user_id": str(log.user_id),
            "from_role": log.from_role,
            "to_role": log.to_role,
            "reason": log.reason,
            "action_type": log.action_type,
            "payload": log.payload or {},
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
