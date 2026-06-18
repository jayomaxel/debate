"""
辩论管理服务
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import itertools
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.debate import Debate, DebateParticipation, DebateReservationInvitation
from models.user import User
from models.class_model import Class
from services.assessment_service import AssessmentService
from services.avatar_service import AvatarService
from services.config_service import ConfigService
from services.room_manager import room_manager
from config import settings
from logging_config import get_logger
from utils.security import hash_password, verify_password
import uuid
import random
import string
import json
import httpx
from copy import deepcopy

logger = get_logger(__name__)


class DebateService:
    """辩论管理服务类"""

    ROOM_META_KEY = "__room_meta"
    DEBATE_CONFIG_META_KEY = "debate_config_meta"
    DEFAULT_ROOM_CAPACITY = 4
    ROLE_ORDER = ["debater_1", "debater_2", "debater_3", "debater_4"]
    ROLE_REASON = {
        "debater_1": "立论陈词,奠定基调",
        "debater_2": "补充论据,强化逻辑",
        "debater_3": "反驳对方,抓住漏洞",
        "debater_4": "总结陈词,升华观点",
    }
    CONFIG_MODE_VALUES = {"competition", "teaching"}
    CONFIG_ROLE_ASSIGNMENT_MODE_VALUES = {"strength_first", "growth_first"}
    CONFIG_ROLE_ROTATION_POLICY_VALUES = {"balanced_rotation", "strength_priority", "growth_priority"}
    CONFIG_ASSIGNMENT_POLICY_VALUES = {"ai_auto_assign", "ai_recommend_then_confirm"}
    CONFIG_DIFFICULTY_ROUNDS_MIN = 1
    CONFIG_DIFFICULTY_ROUNDS_MAX = 20
    CONFIG_LIST_FIELDS = {
        "knowledge_points",
        "objective",
        "evaluation_focus",
        "forbidden_moves",
        "support_document_ids",
    }
    CONFIG_OPTIONAL_STRING_FIELDS = {
        "domain_pack_id",
        "teaching_design_version_id",
    }
    CONFIG_ACTIVITY_FOCUS_FIELDS = {
        "chapter_focus",
        "training_focus",
        "classroom_scene",
    }
    DEFAULT_DEBATE_CONFIG_META = {
        "mode": "competition",
        "role_assignment_mode": "strength_first",
        "role_rotation_policy": "balanced_rotation",
        "assignment_policy": "ai_recommend_then_confirm",
        "fairness_window_size": 5,
        "same_role_max_streak": 2,
        "rounds": 1,
        "knowledge_points": [],
        "objective": [],
        "evaluation_focus": [],
        "forbidden_moves": [],
        "support_document_ids": [],
        "domain_pack_id": None,
        "teaching_design_version_id": None,
        "activity_focus": {
            "chapter_focus": None,
            "training_focus": None,
            "classroom_scene": None,
        },
    }

    @staticmethod
    def _room_source_value(mode: str) -> str:
        return "student_created" if str(mode) == "student_lobby" else "teacher_created"

    @staticmethod
    def _config_source_value(mode: str) -> str:
        return "teacher_preset" if str(mode) == "teacher_reserved" else "room_owner_preset"

    @staticmethod
    def _preparation_page_type(mode: str) -> str:
        return "teacher_reserved_preparation" if str(mode) == "teacher_reserved" else "student_lobby_preparation"
    
    @staticmethod
    def generate_invitation_code() -> str:
        """
        生成唯一的6位邀请码
        
        Returns:
            6位字母数字组合的邀请码
        """
        characters = string.ascii_uppercase + string.digits
        return ''.join(random.choices(characters, k=6))

    @staticmethod
    def _generate_unique_invitation_code(db: Session) -> str:
        max_attempts = 10
        for _ in range(max_attempts):
            code = DebateService.generate_invitation_code()
            existing = db.query(Debate).filter(Debate.invitation_code == code).first()
            if not existing:
                return code
        raise ValueError("生成邀请码失败，请重试")

    @staticmethod
    def _get_room_meta(debate: Debate) -> Dict[str, Any]:
        report = debate.report if isinstance(debate.report, dict) else {}
        meta = report.get(DebateService.ROOM_META_KEY)
        return dict(meta) if isinstance(meta, dict) else {}

    @staticmethod
    def _set_room_meta(debate: Debate, meta: Dict[str, Any]) -> None:
        report = dict(debate.report) if isinstance(debate.report, dict) else {}
        report[DebateService.ROOM_META_KEY] = dict(meta)
        debate.report = report

    @staticmethod
    def _clean_optional_string(value: Any) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _clean_string_list(value: Any, *, field_name: str) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"{field_name} 必须是字符串数组")
        result: List[str] = []
        seen = set()
        for item in value:
            cleaned = DebateService._clean_optional_string(item)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
        return result

    @staticmethod
    def _parse_legacy_debate_config_meta(description: Optional[str]) -> Optional[Dict[str, Any]]:
        """Best-effort parser for old descriptions that were stored as JSON."""
        text = (description or "").strip()
        if not text or not text.startswith("{"):
            return None
        try:
            parsed = json.loads(text)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        for key in ("config_meta", "debate_config_meta", "DebateConfigMeta"):
            value = parsed.get(key)
            if isinstance(value, dict):
                return value
        known_keys = set(DebateService.DEFAULT_DEBATE_CONFIG_META.keys())
        if known_keys.intersection(parsed.keys()):
            return parsed
        return None

    @staticmethod
    def _apply_debate_config_patch(
        target: Dict[str, Any],
        patch: Dict[str, Any],
        *,
        strict: bool,
    ) -> None:
        if not isinstance(patch, dict):
            if strict:
                raise ValueError("config_meta 必须是对象")
            return

        known_keys = set(DebateService.DEFAULT_DEBATE_CONFIG_META.keys())
        unknown_keys = set(patch.keys()) - known_keys
        if unknown_keys and strict:
            unknown = ", ".join(sorted(unknown_keys))
            raise ValueError(f"config_meta 包含未知字段: {unknown}")

        if "mode" in patch:
            mode = DebateService._clean_optional_string(patch.get("mode")) or "competition"
            if mode not in DebateService.CONFIG_MODE_VALUES:
                raise ValueError("config_meta.mode 仅支持 competition 或 teaching")
            target["mode"] = mode

        if "role_assignment_mode" in patch:
            value = DebateService._clean_optional_string(patch.get("role_assignment_mode")) or "strength_first"
            if value not in DebateService.CONFIG_ROLE_ASSIGNMENT_MODE_VALUES:
                raise ValueError("config_meta.role_assignment_mode 仅支持 strength_first 或 growth_first")
            target["role_assignment_mode"] = value

        if "role_rotation_policy" in patch:
            value = DebateService._clean_optional_string(patch.get("role_rotation_policy")) or "balanced_rotation"
            if value not in DebateService.CONFIG_ROLE_ROTATION_POLICY_VALUES:
                raise ValueError("config_meta.role_rotation_policy 仅支持 balanced_rotation、strength_priority 或 growth_priority")
            target["role_rotation_policy"] = value

        if "assignment_policy" in patch:
            value = DebateService._clean_optional_string(patch.get("assignment_policy")) or "ai_recommend_then_confirm"
            if value not in DebateService.CONFIG_ASSIGNMENT_POLICY_VALUES:
                raise ValueError("config_meta.assignment_policy 仅支持 ai_auto_assign 或 ai_recommend_then_confirm")
            target["assignment_policy"] = value

        if "rounds" in patch:
            try:
                rounds = int(patch.get("rounds"))
            except (TypeError, ValueError) as exc:
                raise ValueError("config_meta.rounds 必须是整数") from exc
            if rounds < DebateService.CONFIG_DIFFICULTY_ROUNDS_MIN or rounds > DebateService.CONFIG_DIFFICULTY_ROUNDS_MAX:
                raise ValueError("config_meta.rounds 必须在 1 到 20 之间")
            target["rounds"] = rounds

        for field_name in ("fairness_window_size", "same_role_max_streak"):
            if field_name in patch:
                try:
                    value = int(patch.get(field_name))
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"config_meta.{field_name} 必须是整数") from exc
                if value < 0:
                    raise ValueError(f"config_meta.{field_name} 不能小于 0")
                target[field_name] = value

        for field_name in DebateService.CONFIG_LIST_FIELDS:
            if field_name in patch:
                target[field_name] = DebateService._clean_string_list(
                    patch.get(field_name),
                    field_name=f"config_meta.{field_name}",
                )

        for field_name in DebateService.CONFIG_OPTIONAL_STRING_FIELDS:
            if field_name in patch:
                target[field_name] = DebateService._clean_optional_string(patch.get(field_name))

        if "activity_focus" in patch:
            activity_focus = patch.get("activity_focus") or {}
            if not isinstance(activity_focus, dict):
                raise ValueError("config_meta.activity_focus 必须是对象")
            unknown_focus_keys = set(activity_focus.keys()) - DebateService.CONFIG_ACTIVITY_FOCUS_FIELDS
            if unknown_focus_keys and strict:
                unknown = ", ".join(sorted(unknown_focus_keys))
                raise ValueError(f"config_meta.activity_focus 包含未知字段: {unknown}")
            target_focus = dict(target.get("activity_focus") or {})
            for field_name in DebateService.CONFIG_ACTIVITY_FOCUS_FIELDS:
                if field_name in activity_focus:
                    target_focus[field_name] = DebateService._clean_optional_string(activity_focus.get(field_name))
            for field_name in DebateService.CONFIG_ACTIVITY_FOCUS_FIELDS:
                target_focus.setdefault(field_name, None)
            target["activity_focus"] = target_focus

    @staticmethod
    def normalize_debate_config_meta(
        config_meta: Optional[Dict[str, Any]] = None,
        *,
        description: Optional[str] = None,
        base_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = deepcopy(DebateService.DEFAULT_DEBATE_CONFIG_META)
        legacy_meta = DebateService._parse_legacy_debate_config_meta(description)
        if legacy_meta:
            DebateService._apply_debate_config_patch(normalized, legacy_meta, strict=False)
        if base_meta:
            DebateService._apply_debate_config_patch(normalized, base_meta, strict=False)
        if config_meta is not None:
            DebateService._apply_debate_config_patch(normalized, config_meta, strict=True)
        return normalized

    @staticmethod
    def _deserialize_debate_config_meta(debate: Debate) -> Dict[str, Any]:
        """Read persisted config from room metadata, with legacy description fallback."""
        meta = DebateService._get_room_meta(debate)
        stored_meta = meta.get(DebateService.DEBATE_CONFIG_META_KEY)
        try:
            return DebateService.normalize_debate_config_meta(
                stored_meta if isinstance(stored_meta, dict) else None,
                description=debate.description,
            )
        except ValueError as exc:
            logger.warning(f"辩论结构化配置解析失败，使用默认配置: {exc}")
            return DebateService.normalize_debate_config_meta(description=debate.description)

    @staticmethod
    def _serialize_debate_config_meta(debate: Debate) -> Dict[str, Any]:
        """Return the API-safe DebateConfigMeta payload."""
        return deepcopy(DebateService._deserialize_debate_config_meta(debate))

    @staticmethod
    def _persist_debate_config_meta(debate: Debate, config_meta: Dict[str, Any]) -> None:
        """Merge and persist a DebateConfigMeta patch into room metadata."""
        meta = DebateService._get_room_meta(debate)
        stored_meta = meta.get(DebateService.DEBATE_CONFIG_META_KEY)
        meta[DebateService.DEBATE_CONFIG_META_KEY] = DebateService.normalize_debate_config_meta(
            config_meta,
            description=debate.description,
            base_meta=stored_meta if isinstance(stored_meta, dict) else None,
        )
        DebateService._set_room_meta(debate, meta)

    @staticmethod
    def _get_debate_config_meta(debate: Debate) -> Dict[str, Any]:
        return DebateService._serialize_debate_config_meta(debate)

    @staticmethod
    def _set_debate_config_meta(debate: Debate, config_meta: Dict[str, Any]) -> None:
        DebateService._persist_debate_config_meta(debate, config_meta)

    @staticmethod
    def _serialize_debate_base(debate: Debate) -> Dict[str, Any]:
        return {
            "topic": debate.topic,
            "description": debate.description,
            "config_meta": DebateService._serialize_debate_config_meta(debate),
            "duration": debate.duration,
        }

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
    def _normalize_datetime(value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("时间格式不正确") from exc
        else:
            raise ValueError("时间格式不正确")
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    @staticmethod
    def _datetime_to_iso(value: Any) -> Optional[str]:
        dt = DebateService._normalize_datetime(value)
        return dt.isoformat() if dt else None

    @staticmethod
    def _parse_meta_datetime(meta: Dict[str, Any], key: str) -> Optional[datetime]:
        return DebateService._normalize_datetime(meta.get(key))

    @staticmethod
    def _debate_datetime(debate: Debate, field_name: str, meta: Optional[Dict[str, Any]] = None) -> Optional[datetime]:
        value = getattr(debate, field_name, None)
        if value:
            return DebateService._normalize_datetime(value)
        meta = meta if meta is not None else DebateService._get_room_meta(debate)
        return DebateService._parse_meta_datetime(meta, field_name)

    @staticmethod
    def _debate_datetime_iso(
        debate: Debate,
        field_name: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        value = DebateService._debate_datetime(debate, field_name, meta)
        return value.isoformat() if value else None

    @staticmethod
    def _get_student_with_class(db: Session, student_id: str) -> tuple[User, Class]:
        try:
            student_uuid = uuid.UUID(str(student_id))
        except ValueError as exc:
            raise ValueError("无效的学生ID格式") from exc

        student = db.query(User).filter(
            User.id == student_uuid,
            User.user_type == "student",
        ).first()
        if not student:
            raise ValueError("学生不存在")
        if not student.class_id:
            raise ValueError("学生未绑定班级，无法创建或加入房间")

        cls = db.query(Class).filter(Class.id == student.class_id).first()
        if not cls:
            raise ValueError("学生班级不存在")
        return student, cls

    @staticmethod
    def _participant_count(db: Session, debate_id: uuid.UUID) -> int:
        return db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_id,
            DebateParticipation.left_at.is_(None),
        ).count()

    @staticmethod
    def _room_mode(debate: Debate, meta: Optional[Dict[str, Any]] = None) -> str:
        meta = meta if meta is not None else DebateService._get_room_meta(debate)
        return str(getattr(debate, "mode", None) or meta.get("mode") or "teacher_assigned")

    @staticmethod
    def _room_visibility(debate: Debate, meta: Optional[Dict[str, Any]] = None) -> str:
        meta = meta if meta is not None else DebateService._get_room_meta(debate)
        return str(getattr(debate, "visibility", None) or meta.get("visibility") or "private")

    @staticmethod
    def _room_capacity(debate: Debate, meta: Optional[Dict[str, Any]] = None) -> int:
        meta = meta if meta is not None else DebateService._get_room_meta(debate)
        try:
            return max(
                1,
                int(getattr(debate, "capacity", None) or meta.get("capacity") or DebateService.DEFAULT_ROOM_CAPACITY),
            )
        except Exception:
            return DebateService.DEFAULT_ROOM_CAPACITY

    @staticmethod
    def _room_host_user_id(debate: Debate, meta: Optional[Dict[str, Any]] = None) -> Optional[str]:
        meta = meta if meta is not None else DebateService._get_room_meta(debate)
        host_user_id = getattr(debate, "host_user_id", None) or meta.get("host_user_id") or meta.get("moderator_user_id")
        return str(host_user_id) if host_user_id else None

    @staticmethod
    def _join_password_hash(debate: Debate, meta: Optional[Dict[str, Any]] = None) -> Optional[str]:
        meta = meta if meta is not None else DebateService._get_room_meta(debate)
        return getattr(debate, "join_password_hash", None) or meta.get("join_password_hash")

    @staticmethod
    def resolve_reservation_status(debate: Debate, now: Optional[datetime] = None) -> str:
        meta = DebateService._get_room_meta(debate)
        reservation_status = str(getattr(debate, "reservation_status", None) or meta.get("reservation_status") or "")
        mode = DebateService._room_mode(debate, meta)
        if reservation_status == "cancelled" or getattr(debate, "cancelled_at", None):
            return "cancelled"
        if mode != "teacher_reserved":
            return reservation_status or str(debate.status or "published")
        if str(debate.status) == "completed":
            return "completed"
        if str(debate.status) == "in_progress":
            return "in_progress"

        now = now or datetime.utcnow()
        scheduled_start_time = DebateService._debate_datetime(debate, "scheduled_start_time", meta)
        checkin_open_time = DebateService._debate_datetime(debate, "checkin_open_time", meta)
        checkin_close_time = DebateService._debate_datetime(debate, "checkin_close_time", meta)

        if checkin_open_time and now >= checkin_open_time:
            if not checkin_close_time or now <= checkin_close_time:
                return "checkin_open"
            if scheduled_start_time and now < scheduled_start_time:
                return "waiting"
        if scheduled_start_time and now >= scheduled_start_time:
            return "waiting"
        return reservation_status or "scheduled"

    @staticmethod
    def resolve_room_status(
        debate: Debate,
        participant_count: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> str:
        meta = DebateService._get_room_meta(debate)
        if DebateService.resolve_reservation_status(debate, now=now) == "cancelled":
            return "cancelled"
        if str(debate.status) == "completed":
            return "finished"
        if str(debate.status) == "in_progress":
            return "ongoing"
        if participant_count is not None and participant_count >= DebateService._room_capacity(debate, meta):
            return "full"
        if DebateService._room_mode(debate, meta) == "teacher_reserved":
            reservation_status = DebateService.resolve_reservation_status(debate, now=now)
            if reservation_status == "cancelled":
                return "cancelled"
            if reservation_status == "in_progress":
                return "ongoing"
        return "waiting"

    @staticmethod
    def _is_invited(meta: Dict[str, Any], student_id: str) -> bool:
        invitations = meta.get("invitations")
        return isinstance(invitations, dict) and str(student_id) in invitations

    @staticmethod
    def _student_can_see_reservation(db: Session, debate: Debate, student_id: str) -> bool:
        if DebateService._get_active_invitation(db, debate.id, student_id):
            return True
        return DebateService._is_invited(DebateService._get_room_meta(debate), student_id)

    @staticmethod
    def _active_invitation_query(db: Session, debate_id: uuid.UUID, student_id: Optional[str] = None):
        query = db.query(DebateReservationInvitation).filter(
            DebateReservationInvitation.debate_id == debate_id,
            DebateReservationInvitation.revoked_at.is_(None),
        )
        if student_id is not None:
            try:
                student_uuid = uuid.UUID(str(student_id))
            except ValueError:
                return query.filter(False)
            query = query.filter(DebateReservationInvitation.student_id == student_uuid)
        return query

    @staticmethod
    def _get_active_invitation(
        db: Session,
        debate_id: uuid.UUID,
        student_id: str,
    ) -> Optional[DebateReservationInvitation]:
        return DebateService._active_invitation_query(db, debate_id, student_id).first()

    @staticmethod
    def _invitation_to_payload(invitation: DebateReservationInvitation) -> Dict[str, Any]:
        return {
            "invitation_id": str(invitation.id),
            "student_id": str(invitation.student_id),
            "invited_by_teacher_id": str(invitation.invited_by_teacher_id),
            "assigned_role": str(invitation.assigned_role) if invitation.assigned_role else None,
            "assigned_stance": str(invitation.assigned_stance) if invitation.assigned_stance else None,
            "role": str(invitation.assigned_role) if invitation.assigned_role else None,
            "stance": str(invitation.assigned_stance) if invitation.assigned_stance else None,
            "is_designated_moderator": bool(invitation.is_designated_moderator),
            "is_backup_moderator": bool(invitation.is_backup_moderator),
            "read_status": str(invitation.read_status),
            "response_status": str(invitation.response_status),
            "attendance_status": str(invitation.attendance_status),
            "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
            "revoked_at": invitation.revoked_at.isoformat() if invitation.revoked_at else None,
            "read_at": invitation.read_at.isoformat() if invitation.read_at else None,
            "responded_at": invitation.responded_at.isoformat() if invitation.responded_at else None,
            "checked_in_at": invitation.checked_in_at.isoformat() if invitation.checked_in_at else None,
            "created_at": invitation.created_at.isoformat() if invitation.created_at else None,
            "updated_at": invitation.updated_at.isoformat() if invitation.updated_at else None,
        }

    @staticmethod
    def _reservation_invitations_map(db: Session, debate_id: uuid.UUID, *, active_only: bool = True) -> Dict[str, Dict[str, Any]]:
        query = db.query(DebateReservationInvitation).filter(
            DebateReservationInvitation.debate_id == debate_id,
        )
        if active_only:
            query = query.filter(DebateReservationInvitation.revoked_at.is_(None))
        invitations = query.order_by(DebateReservationInvitation.created_at.asc()).all()
        return {
            str(invitation.student_id): DebateService._invitation_to_payload(invitation)
            for invitation in invitations
        }

    @staticmethod
    def _invitation_student_ids(db: Session, debate_id: uuid.UUID) -> set[str]:
        return {
            str(row[0])
            for row in DebateService._active_invitation_query(db, debate_id)
            .with_entities(DebateReservationInvitation.student_id)
            .all()
        }

    @staticmethod
    def _role_assignment_snapshot_map(meta: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
        meta = meta or {}
        snapshot = meta.get("role_assignment_snapshot")
        if not isinstance(snapshot, list):
            return {}
        result: Dict[str, Dict[str, Any]] = {}
        for item in snapshot:
            if not isinstance(item, dict):
                continue
            user_id = str(item.get("user_id") or "").strip()
            if not user_id:
                continue
            result[user_id] = dict(item)
        return result

    @staticmethod
    def _assignment_role_pool(student_count: int) -> List[str]:
        return DebateService.ROLE_ORDER[: max(0, min(student_count, len(DebateService.ROLE_ORDER)))]

    @staticmethod
    def _role_rotation_defaults(config_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config_meta = config_meta or {}
        return {
            "role_rotation_policy": config_meta.get("role_rotation_policy") or "balanced_rotation",
            "fairness_window_size": max(1, int(config_meta.get("fairness_window_size") or 5)),
            "same_role_max_streak": max(1, int(config_meta.get("same_role_max_streak") or 2)),
        }

    @staticmethod
    def _role_history_summary(
        db: Session,
        student_id: str,
        role_pool: List[str],
        *,
        window_size: int,
    ) -> Dict[str, Any]:
        if window_size <= 0:
            window_size = 5
        participations = db.query(DebateParticipation).join(
            Debate,
            DebateParticipation.debate_id == Debate.id,
        ).filter(
            DebateParticipation.user_id == uuid.UUID(student_id),
            DebateParticipation.left_at.is_(None),
            Debate.status == "completed",
            DebateParticipation.role.in_(role_pool),
        ).order_by(DebateParticipation.joined_at.desc()).limit(window_size).all()

        counts = {role: 0 for role in role_pool}
        streak_role = None
        streak_count = 0
        last_role = None
        last_assigned_roles: List[str] = []
        for participation in participations:
            role = str(participation.role)
            counts[role] = counts.get(role, 0) + 1
            last_assigned_roles.append(role)
        if last_assigned_roles:
            last_role = last_assigned_roles[0]
            streak_role = last_role
            for role in last_assigned_roles:
                if role == streak_role:
                    streak_count += 1
                else:
                    break
        distribution = [
            {
                "role": role,
                "count": counts.get(role, 0),
            }
            for role in role_pool
        ]
        return {
            "window_size": window_size,
            "total": len(participations),
            "distribution": distribution,
            "last_role": last_role,
            "streak_role": streak_role,
            "streak_count": streak_count,
        }

    @staticmethod
    def _calculate_fairness_adjustment(
        role: str,
        *,
        history_summary: Dict[str, Any],
        role_rotation_policy: str,
        same_role_max_streak: int,
    ) -> Dict[str, Any]:
        distribution = history_summary.get("distribution") or []
        total = int(history_summary.get("total") or 0)
        role_count = 0
        for item in distribution:
            if item.get("role") == role:
                role_count = int(item.get("count") or 0)
                break
        repeat_penalty = 0.0
        training_bonus = 0.0
        imbalance_penalty = 0.0

        if total > 0:
            role_ratio = role_count / total
            expected_ratio = 1 / max(1, len(distribution) or 1)
            imbalance_penalty = round(max(0.0, role_ratio - expected_ratio) * 20, 2)

        if history_summary.get("streak_role") == role:
            streak_count = int(history_summary.get("streak_count") or 0)
            if streak_count >= same_role_max_streak:
                repeat_penalty = round((streak_count - same_role_max_streak + 1) * 8, 2)

        if role_rotation_policy == "growth_priority":
            training_bonus = round(max(0.0, 10 - role_count) * 0.8, 2)
        elif role_rotation_policy == "balanced_rotation":
            training_bonus = round(max(0.0, 5 - role_count) * 0.5, 2)
        else:
            training_bonus = 0.0

        final_adjustment = round(training_bonus - repeat_penalty - imbalance_penalty, 2)
        return {
            "repeat_penalty": repeat_penalty,
            "training_bonus": training_bonus,
            "imbalance_penalty": imbalance_penalty,
            "final_adjustment": final_adjustment,
            "rotation_reason": "",
        }

    @staticmethod
    def _build_role_assignment_plan(
        db: Session,
        student_ids: List[str],
        *,
        role_assignments: Optional[List[Dict[str, Any]]] = None,
        assignment_mode: str = "strength_first",
        config_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not student_ids:
            return {
                "assignment_mode": assignment_mode,
                "assignment_source": "rule_model",
                "role_pool": [],
                "results": [],
                "assignment_map": {},
                "role_rotation_policy": "balanced_rotation",
            }

        users = db.query(User).filter(User.id.in_([uuid.UUID(student_id) for student_id in student_ids])).all()
        user_by_id = {str(user.id): user for user in users}
        role_pool = DebateService._assignment_role_pool(len(student_ids))
        rotation_defaults = DebateService._role_rotation_defaults(config_meta)
        role_rotation_policy = rotation_defaults["role_rotation_policy"]
        fairness_window_size = rotation_defaults["fairness_window_size"]
        same_role_max_streak = rotation_defaults["same_role_max_streak"]

        fit_matrices: Dict[str, Dict[str, Dict[str, Any]]] = {}
        history_summaries: Dict[str, Dict[str, Any]] = {}
        for student_id in student_ids:
            assessment = AssessmentService.get_assessment(db=db, user_id=student_id) or {}
            history_summaries[student_id] = DebateService._role_history_summary(
                db,
                student_id,
                role_pool,
                window_size=fairness_window_size,
            )
            fit_matrices[student_id] = AssessmentService.build_role_fit_matrix(
                assessment,
                roles=role_pool,
                assignment_mode=assignment_mode,
            )

        best_assignment: Dict[str, str] = {}
        best_score = float("-inf")
        for perm in itertools.permutations(role_pool, len(student_ids)):
            current_score = 0.0
            for index, student_id in enumerate(student_ids):
                role = perm[index]
                fit_payload = fit_matrices[student_id][role]
                fairness_payload = DebateService._calculate_fairness_adjustment(
                    role,
                    history_summary=history_summaries.get(student_id, {}),
                    role_rotation_policy=role_rotation_policy,
                    same_role_max_streak=same_role_max_streak,
                )
                current_score += float(fit_payload["fit_score"]) + float(fairness_payload["final_adjustment"])
            if current_score > best_score:
                best_score = current_score
                best_assignment = {
                    student_id: perm[index]
                    for index, student_id in enumerate(student_ids)
                }

        teacher_assignment_map: Dict[str, str] = {}
        teacher_override = False
        if role_assignments is not None:
            if len(role_assignments) != len(student_ids):
                raise ValueError("role_assignments 必须完整覆盖全部学生")
            allowed_student_ids = set(student_ids)
            allowed_roles = set(role_pool)
            seen_student_ids: set[str] = set()
            seen_roles: set[str] = set()
            for item in role_assignments:
                if not isinstance(item, dict):
                    raise ValueError("role_assignments 格式不正确")
                student_id = str(item.get("user_id") or "").strip()
                role = str(item.get("role") or "").strip()
                if student_id not in allowed_student_ids:
                    raise ValueError("role_assignments 包含无效学生")
                if role not in allowed_roles:
                    raise ValueError("role_assignments 包含无效辩位")
                if student_id in seen_student_ids or role in seen_roles:
                    raise ValueError("role_assignments 不能重复分配")
                seen_student_ids.add(student_id)
                seen_roles.add(role)
                teacher_assignment_map[student_id] = role
            teacher_override = True

        assignment_map = teacher_assignment_map or best_assignment
        results: List[Dict[str, Any]] = []
        for student_id in student_ids:
            user = user_by_id.get(student_id)
            recommended_role = best_assignment.get(student_id)
            assigned_role = assignment_map.get(student_id, recommended_role)
            fit_payload = fit_matrices[student_id].get(recommended_role, {})
            history_summary = history_summaries.get(student_id, {})
            fairness_payload = DebateService._calculate_fairness_adjustment(
                recommended_role,
                history_summary=history_summary,
                role_rotation_policy=role_rotation_policy,
                same_role_max_streak=same_role_max_streak,
            )
            teacher_changed = assigned_role != recommended_role
            repeat_penalty = fairness_payload["repeat_penalty"] if recommended_role == assigned_role else 0.0
            training_bonus = fairness_payload["training_bonus"] if recommended_role == assigned_role else 0.0
            imbalance_penalty = fairness_payload["imbalance_penalty"] if recommended_role == assigned_role else 0.0
            final_adjustment = fairness_payload["final_adjustment"] if recommended_role == assigned_role else 0.0
            rotation_reason = ""
            if history_summary.get("streak_role") == recommended_role and int(history_summary.get("streak_count") or 0) >= same_role_max_streak:
                rotation_reason = "近期同一辩位连续出现次数较多，系统优先进行轮换"
            elif history_summary.get("total"):
                rotation_reason = "综合历史辩位分布后进行均衡分配"
            else:
                rotation_reason = "当前无足够历史记录，按能力适配优先"
            results.append(
                {
                    "user_id": student_id,
                    "name": user.name if user else "",
                    "avatar": AvatarService.build_avatar_payload(user)["avatar"] if user else None,
                    "recommended_role": recommended_role,
                    "assigned_role": assigned_role,
                    "assignment_source": "teacher_override" if teacher_override and teacher_changed else (
                        "teacher_confirmed" if teacher_override else "rule_model"
                    ),
                    "teacher_override": teacher_changed,
                    "fit_score": fit_payload.get("fit_score"),
                    "role_fit_score": fit_payload.get("role_fit_score", fit_payload.get("fit_score")),
                    "strength_score": fit_payload.get("strength_score"),
                    "final_score": round(float(fit_payload.get("fit_score") or 0) + final_adjustment, 2),
                    "repeat_penalty": repeat_penalty,
                    "training_bonus": training_bonus,
                    "imbalance_penalty": imbalance_penalty,
                    "rotation_reason": rotation_reason,
                    "historical_role_distribution": history_summary.get("distribution", []),
                    "dimension_contribution": fit_payload.get("dimension_contribution"),
                    "assignment_reason": fit_payload.get("assignment_reason"),
                    "data_basis": fit_payload.get("data_basis"),
                    "analysis_basis": fit_payload.get("analysis_basis"),
                    "data_sources": fit_payload.get("data_sources"),
                    "profile_confidence": fit_payload.get("profile_confidence"),
                    "standard_profile": fit_payload.get("standard_profile"),
                }
            )

        return {
            "assignment_mode": assignment_mode,
            "assignment_source": "teacher_override" if teacher_override else "rule_model",
            "role_pool": role_pool,
            "role_rotation_policy": role_rotation_policy,
            "results": results,
            "assignment_map": {item["user_id"]: item["assigned_role"] for item in results},
        }

    @staticmethod
    def _persist_role_assignment_snapshot(
        debate: Debate,
        snapshot: List[Dict[str, Any]],
        *,
        assignment_mode: str,
        assignment_source: str,
        role_rotation_policy: str = "balanced_rotation",
    ) -> None:
        meta = DebateService._get_room_meta(debate)
        meta["role_assignment_snapshot"] = snapshot
        meta["role_assignment_mode"] = assignment_mode
        meta["role_assignment_source"] = assignment_source
        meta["role_rotation_policy"] = role_rotation_policy
        meta["role_assignment_updated_at"] = datetime.utcnow().isoformat()
        DebateService._set_room_meta(debate, meta)

    @staticmethod
    def _ensure_active_participation_available(
        db: Session,
        debate_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        stance: str,
        seat_order: Optional[int],
    ) -> None:
        if db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_id,
            DebateParticipation.user_id == user_id,
            DebateParticipation.left_at.is_(None),
        ).first():
            raise ValueError("您已在该房间中")

        if seat_order is not None and db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_id,
            DebateParticipation.seat_order == seat_order,
            DebateParticipation.left_at.is_(None),
        ).first():
            raise ValueError("该座位已被占用")

        if db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_id,
            DebateParticipation.stance == stance,
            DebateParticipation.role == role,
            DebateParticipation.left_at.is_(None),
        ).first():
            raise ValueError("该辩手位已被占用")

    @staticmethod
    def _seat_order_for_role(role: Optional[str]) -> Optional[int]:
        if role not in DebateService.ROLE_ORDER:
            return None
        return DebateService.ROLE_ORDER.index(str(role)) + 1

    @staticmethod
    def _role_for_seat_order(seat_order: int) -> str:
        index = max(0, min(len(DebateService.ROLE_ORDER) - 1, seat_order - 1))
        return DebateService.ROLE_ORDER[index]

    @staticmethod
    def _next_available_seat(db: Session, debate_id: uuid.UUID, capacity: int) -> int:
        occupied = {
            int(row[0])
            for row in db.query(DebateParticipation.seat_order)
            .filter(
                DebateParticipation.debate_id == debate_id,
                DebateParticipation.left_at.is_(None),
                DebateParticipation.seat_order.isnot(None),
            )
            .all()
            if row[0] is not None
        }
        for seat_order in range(1, min(capacity, len(DebateService.ROLE_ORDER)) + 1):
            if seat_order not in occupied:
                return seat_order
        raise ValueError("房间已满")

    @staticmethod
    def _create_participation(
        db: Session,
        *,
        debate: Debate,
        user_id: uuid.UUID,
        role: str,
        stance: str = "positive",
        invitation: Optional[DebateReservationInvitation] = None,
        invited_by: Optional[uuid.UUID] = None,
        is_moderator: bool = False,
        is_room_owner: bool = False,
        attendance_status: Optional[str] = None,
        checked_in_at: Optional[datetime] = None,
        seat_order: Optional[int] = None,
    ) -> DebateParticipation:
        if seat_order is None:
            seat_order = DebateService._seat_order_for_role(role)
        DebateService._ensure_active_participation_available(
            db=db,
            debate_id=debate.id,
            user_id=user_id,
            role=role,
            stance=stance,
            seat_order=seat_order,
        )
        participation = DebateParticipation(
            id=uuid.uuid4(),
            debate_id=debate.id,
            user_id=user_id,
            role=role,
            stance=stance,
            role_reason=DebateService.ROLE_REASON.get(role),
            is_moderator=is_moderator,
            is_room_owner=is_room_owner,
            invitation_id=invitation.id if invitation else None,
            invited_by=invited_by,
            attendance_status=attendance_status,
            checked_in_at=checked_in_at,
            seat_order=seat_order,
            joined_at=checked_in_at or datetime.utcnow(),
        )
        db.add(participation)
        return participation

    @staticmethod
    def _serialize_participation(
        participation: DebateParticipation,
        user: Optional[User],
        debate: Optional[Debate] = None,
        meta: Optional[Dict[str, Any]] = None,
        online_user_ids: Optional[set[str]] = None,
        ready_user_ids: Optional[set[str]] = None,
    ) -> Dict[str, Any]:
        user_id = str(participation.user_id) if participation.user_id else None
        meta = meta or {}
        mode = DebateService._room_mode(debate, meta) if debate else str(meta.get("mode") or "teacher_assigned")
        host_user_id = DebateService._room_host_user_id(debate, meta) if debate else str(meta.get("host_user_id") or meta.get("moderator_user_id") or "")
        can_moderate = bool(user_id and host_user_id == user_id)
        if bool(getattr(participation, "is_moderator", False)):
            can_moderate = True
        online_user_ids = online_user_ids or set()
        ready_user_ids = ready_user_ids or set()
        is_online_in_room = bool(user_id and user_id in online_user_ids)
        is_ready = bool(user_id and user_id in ready_user_ids)
        return {
            "user_id": user_id,
            "name": user.name if user else "",
            "avatar": AvatarService.build_avatar_payload(user)["avatar"] if user else None,
            "role": str(participation.role),
            "stance": str(participation.stance),
            "role_reason": participation.role_reason,
            "seat_order": participation.seat_order,
            "is_room_owner": bool(participation.is_room_owner),
            "can_speak": True,
            "can_moderate": can_moderate,
            "joined_at": participation.joined_at.isoformat() if participation.joined_at else None,
            "membership_status": "joined",
            "presence_status": "online_in_room" if is_online_in_room else "online_out_of_room_page",
            "online_status": "online_in_room" if is_online_in_room else "offline",
            "ready_status": "ready" if is_ready else "not_ready",
        }

    @staticmethod
    def _room_members(db: Session, debate: Debate, meta: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        meta = meta or {}
        participations = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id,
            DebateParticipation.left_at.is_(None),
        ).all()
        room_state = room_manager.get_room_state(str(debate.id))
        online_user_ids = {
            str(participant.get("user_id"))
            for participant in (room_state.participants if room_state else [])
            if participant.get("user_id")
        }
        ready_user_ids = set()
        if room_state:
            waiting_status = room_state.get_waiting_status()
            ready_user_ids = {
                str(user_id)
                for user_id in (waiting_status.get("ready_user_ids") or [])
            }
        user_ids = [p.user_id for p in participations if p.user_id]
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        user_by_id = {u.id: u for u in users}
        role_rank = {role: index for index, role in enumerate(DebateService.ROLE_ORDER)}
        return [
            DebateService._serialize_participation(
                p,
                user_by_id.get(p.user_id),
                debate,
                meta,
                online_user_ids=online_user_ids,
                ready_user_ids=ready_user_ids,
            )
            for p in sorted(participations, key=lambda p: role_rank.get(str(p.role), 99))
        ]

    @staticmethod
    def _available_roles(members: List[Dict[str, Any]]) -> List[str]:
        occupied = {str(member.get("role")) for member in members}
        return [role for role in DebateService.ROLE_ORDER if role not in occupied]

    @staticmethod
    def _get_host_name(db: Session, debate: Debate, meta: Dict[str, Any]) -> str:
        host_user_id = DebateService._room_host_user_id(debate, meta)
        if host_user_id:
            try:
                host = db.query(User).filter(User.id == uuid.UUID(str(host_user_id))).first()
                if host:
                    return host.name
            except ValueError:
                pass
        if debate.teacher:
            return debate.teacher.name
        return ""

    @staticmethod
    def _current_user_permissions(
        members: List[Dict[str, Any]],
        student_id: str,
    ) -> Dict[str, Any]:
        current = next(
            (member for member in members if str(member.get("user_id")) == str(student_id)),
            None,
        )
        if not current:
            return {
                "role": None,
                "can_speak": False,
                "can_moderate": False,
                "is_joined": False,
                "membership_status": "not_joined",
                "presence_status": "not_in_room",
                "ready_status": "not_ready",
            }
        return {
            "role": current.get("role"),
            "can_speak": bool(current.get("can_speak")),
            "can_moderate": bool(current.get("can_moderate")),
            "is_joined": True,
            "membership_status": current.get("membership_status", "joined"),
            "presence_status": current.get("presence_status", "online_in_room"),
            "ready_status": current.get("ready_status", "not_ready"),
        }

    @staticmethod
    def _serialize_lobby_room(
        db: Session,
        debate: Debate,
        *,
        student_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        meta = DebateService._get_room_meta(debate)
        mode = DebateService._room_mode(debate, meta)
        participant_count = DebateService._participant_count(db, debate.id)
        realtime_room_state = room_manager.get_room_state(str(debate.id))
        if realtime_room_state:
            participant_count = room_manager.get_waiting_online_count(str(debate.id))
        members = None
        current_permissions = None
        if student_id:
            members = DebateService._room_members(db, debate, meta)
            current_permissions = DebateService._current_user_permissions(members, student_id)
        return {
            "room_id": str(debate.id),
            "debate_id": str(debate.id),
            "room_name": debate.room_name or meta.get("room_name") or debate.topic[:30],
            **DebateService._serialize_debate_base(debate),
            "current_count": participant_count,
            "capacity": DebateService._room_capacity(debate, meta),
            "visibility": DebateService._room_visibility(debate, meta),
            "has_password": bool(DebateService._join_password_hash(debate, meta)),
            "host_user_id": DebateService._room_host_user_id(debate, meta),
            "host_name": DebateService._get_host_name(db, debate, meta),
            "mode": mode,
            "room_source": DebateService._room_source_value(mode),
            "config_source": DebateService._config_source_value(mode),
            "preparation_page_type": DebateService._preparation_page_type(mode),
            "status": DebateService.resolve_room_status(debate, participant_count),
            "scheduled_start_time": DebateService._debate_datetime_iso(debate, "scheduled_start_time", meta),
            "allow_spectators": bool(getattr(debate, "allow_spectators", False) or meta.get("allow_spectators", False)),
            "created_at": debate.created_at.isoformat() if debate.created_at else None,
            **({"members": members, "current_user_permissions": current_permissions} if student_id else {}),
        }

    @staticmethod
    def _ensure_private_password(debate: Debate, meta: Dict[str, Any], password: Optional[str]) -> None:
        if DebateService._room_visibility(debate, meta) != "private":
            return
        password_hash = DebateService._join_password_hash(debate, meta)
        if not password_hash:
            raise ValueError("房间密码未设置")
        if not password:
            raise ValueError("请输入房间密码")
        if not verify_password(password, str(password_hash)):
            raise ValueError("密码错误或已失效")

    @staticmethod
    def leave_lobby_room(
        db: Session,
        student_id: str,
        room_id: str,
        *,
        permanent: bool,
    ) -> Dict[str, Any]:
        DebateService._get_student_with_class(db, student_id)
        try:
            room_uuid = uuid.UUID(str(room_id))
            student_uuid = uuid.UUID(str(student_id))
        except ValueError as exc:
            raise ValueError("房间ID格式不正确") from exc

        debate = db.query(Debate).filter(Debate.id == room_uuid).first()
        if not debate:
            raise ValueError("房间不存在")

        meta = DebateService._get_room_meta(debate)
        mode = DebateService._room_mode(debate, meta)
        if mode not in {"student_lobby", "teacher_reserved"}:
            raise ValueError("该房间不支持此操作")

        participation = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id,
            DebateParticipation.user_id == student_uuid,
            DebateParticipation.left_at.is_(None),
        ).first()
        if not participation:
            raise ValueError("您当前不在该房间中")

        if permanent:
            now = datetime.utcnow()
            participation.left_at = now
            participation.last_seen_at = now
            participation.is_moderator = False
            participation.is_room_owner = False

            if mode == "teacher_reserved":
                invitation = db.query(DebateReservationInvitation).filter(
                    DebateReservationInvitation.debate_id == debate.id,
                    DebateReservationInvitation.student_id == student_uuid,
                    DebateReservationInvitation.revoked_at.is_(None),
                ).first()
                if invitation:
                    invitation.attendance_status = "absent"
                    invitation.updated_at = now

            remaining = db.query(DebateParticipation).filter(
                DebateParticipation.debate_id == debate.id,
                DebateParticipation.left_at.is_(None),
                DebateParticipation.user_id != student_uuid,
            ).order_by(DebateParticipation.seat_order.asc(), DebateParticipation.joined_at.asc()).all()

            if mode == "student_lobby":
                next_owner = remaining[0] if remaining else None
                debate.owner_user_id = next_owner.user_id if next_owner else None
                debate.host_user_id = next_owner.user_id if next_owner else None
                for row in remaining:
                    row.is_room_owner = bool(next_owner and row.user_id == next_owner.user_id)
                    row.is_moderator = bool(next_owner and row.user_id == next_owner.user_id)

            db.commit()
            return {
                "room_id": str(debate.id),
                "debate_id": str(debate.id),
                "membership_status": "permanently_left",
                "presence_status": "not_in_room",
                "room_source": DebateService._room_source_value(mode),
            }

        participation.last_seen_at = datetime.utcnow()
        db.commit()
        return {
            "room_id": str(debate.id),
            "debate_id": str(debate.id),
            "membership_status": "joined",
            "presence_status": "online_out_of_room_page",
            "room_source": DebateService._room_source_value(mode),
        }

    @staticmethod
    def _invitation_payload(
        *,
        response_status: str = "pending",
        read_status: str = "unread",
        attendance_status: str = "not_checked_in",
        role: Optional[str] = None,
        stance: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "read_status": read_status,
            "response_status": response_status,
            "attendance_status": attendance_status,
            "role": role,
            "stance": stance,
            "responded_at": None,
            "checked_in_at": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _extract_first_json(text: str) -> Any:
        if not text:
            raise ValueError("LLM返回为空")
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass

        start_positions = [i for i, ch in enumerate(text) if ch in ["{", "["]]
        if not start_positions:
            raise ValueError("LLM返回不包含JSON")
        for start in start_positions:
            for end in range(len(text) - 1, start, -1):
                if text[end] not in ["}", "]"]:
                    continue
                snippet = text[start : end + 1]
                try:
                    return json.loads(snippet)
                except Exception:
                    continue
        raise ValueError("无法解析LLM返回JSON")

    @staticmethod
    def _fallback_assign_roles(assessments: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
        remaining = list(assessments.keys())
        fit_by_user = {
            user_id: AssessmentService.build_role_fit_matrix(assessments.get(user_id) or {})
            for user_id in remaining
        }

        def score(user_id: str, role: str) -> float:
            return float(fit_by_user[user_id][role]["fit_score"])

        assignments: Dict[str, str] = {}
        for role in DebateService.ROLE_ORDER[: len(remaining)]:
            best_user_id = max(remaining, key=lambda uid: score(uid, role))
            assignments[best_user_id] = role
            remaining.remove(best_user_id)
        return assignments

    @staticmethod
    async def _openai_assign_roles(
        db: Session,
        students: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        config_service = ConfigService(db)
        model_config = await config_service.get_model_config()
        api_key = (model_config.api_key or "").strip() or (settings.OPENAI_API_KEY or "").strip()
        if not api_key:
            raise ValueError("OpenAI API key not configured")

        api_endpoint = (model_config.api_endpoint or "").strip()
        if not api_endpoint:
            api_endpoint = f"{settings.OPENAI_BASE_URL}/chat/completions"

        if api_endpoint.endswith("/chat/completions"):
            endpoint = api_endpoint
        elif api_endpoint.endswith("/v1") or api_endpoint.endswith("/compatible-mode/v1"):
            endpoint = f"{api_endpoint}/chat/completions"
        else:
            endpoint = f"{api_endpoint.rstrip('/')}/chat/completions"

        model_name = (model_config.model_name or "").strip() or settings.OPENAI_MODEL_NAME

        system_prompt = (
            "你是辩论教练。请基于学生能力评估，为本场辩论分配角色：debater_1(一辩)、debater_2(二辩)、debater_3(三辩)、debater_4(四辩)。"
            "你必须保证：每个学生最多一个角色、每个角色最多分配给一名学生。"
            "严禁按输入顺序直接分配（例如第1个学生=debater_1等），必须依据能力数值做判断。"
            "你只输出JSON，不要输出任何额外文字。"
            "输出格式：{\"assignments\":[{\"user_id\":\"...\",\"role\":\"debater_1\"},...]}"
        )

        role_name = {
            "debater_1": "一辩",
            "debater_2": "二辩",
            "debater_3": "三辩",
            "debater_4": "四辩",
        }

        students_cn = []
        for s in students:
            uid = s.get("user_id")
            if not uid:
                continue
            students_cn.append(
                {
                    "user_id": uid,
                    "姓名": s.get("name") or "",
                    "表达意愿": s.get("expression_willingness", 50),
                    "逻辑建构力": s.get("logical_thinking", 50),
                    "AI伦理与科技素养": s.get("stablecoin_knowledge", 50),
                    "AI通识知识水平": s.get("financial_knowledge", 50),
                    "批判性思维": s.get("critical_thinking", 50),
                    "系统推荐角色": role_name.get(s.get("recommended_role"), "") if s.get("recommended_role") else "",
                }
            )

        user_payload = {
            "评分说明": "所有能力维度取值范围为0-100，数值越高代表该能力越强。",
            "角色说明": {
                "debater_1": "一辩：立论陈词，奠定基调（适合表达强、主题把控强）",
                "debater_2": "二辩：攻辩反击，强化论据（适合逻辑强、论证细致）",
                "debater_3": "三辩：快速反驳，抓漏洞（适合反应快、批判强）",
                "debater_4": "四辩：总结升华，收束全场（适合综合能力强、总结能力强）",
            },
            "可用角色列表": [{"role": r, "名称": role_name[r]} for r in DebateService.ROLE_ORDER[: len(students_cn)]],
            "学生列表": students_cn,
        }

        print(f"students_cn:{students_cn}")

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": 0.2,
            "max_tokens": min(int(model_config.max_tokens or 300), 600),
        }

        def parse_assignments(data: Dict[str, Any]) -> Dict[str, str]:
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            parsed = DebateService._extract_first_json(content)
            assignments = parsed.get("assignments") if isinstance(parsed, dict) else None
            if not isinstance(assignments, list):
                raise ValueError("OpenAI返回格式不正确")

            valid_user_ids = {s["user_id"] for s in students if s.get("user_id")}
            valid_roles = set(DebateService.ROLE_ORDER[: len(students_cn)])
            result: Dict[str, str] = {}
            used_roles = set()
            for item in assignments:
                if not isinstance(item, dict):
                    continue
                user_id = item.get("user_id")
                role = item.get("role")
                if user_id in valid_user_ids and role in valid_roles and role not in used_roles and user_id not in result:
                    result[user_id] = role
                    used_roles.add(role)
            if len(result) != len(students_cn):
                raise ValueError("OpenAI分配结果不完整")
            return result

        async def call_once(extra_system: Optional[str] = None) -> Dict[str, str]:
            req_payload = payload
            if extra_system:
                req_payload = {
                    **payload,
                    "messages": [
                        {"role": "system", "content": system_prompt + extra_system},
                        payload["messages"][1],
                    ],
                    "temperature": 0.0,
                }

            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=req_payload,
                )
            if response.status_code != 200:
                raise ValueError(f"OpenAI调用失败: {response.status_code} - {response.text}")
            return parse_assignments(response.json())

        def is_trivial_by_input_order(result: Dict[str, str]) -> bool:
            ordered_ids = [s.get("user_id") for s in students_cn]
            expected = {uid: DebateService.ROLE_ORDER[i] for i, uid in enumerate(ordered_ids) if uid}
            return result == expected

        llm_result = await call_once()
        if is_trivial_by_input_order(llm_result):
            deterministic = DebateService._fallback_assign_roles(
                {s["user_id"]: {
                    "expression_willingness": s.get("表达意愿", 50),
                    "logical_thinking": s.get("逻辑建构力", 50),
                    "stablecoin_knowledge": s.get("AI伦理与科技素养", 50),
                    "financial_knowledge": s.get("AI通识知识水平", 50),
                    "critical_thinking": s.get("批判性思维", 50),
                } for s in students_cn}
            )
            if deterministic != llm_result:
                try:
                    llm_result = await call_once(extra_system="如果你发现自己倾向于按输入顺序分配，请立即改为按能力最匹配的方式重新分配。")
                except Exception as e:
                    logger.warning(f"OpenAI重试分组失败，使用兜底规则: {e}")
                    llm_result = deterministic
            else:
                logger.info("OpenAI分配结果与兜底一致，虽按顺序但仍接受该结果")

        return llm_result

    @staticmethod
    def _get_teacher_class(db: Session, teacher_id: str, class_id: str) -> Class:
        try:
            class_uuid = uuid.UUID(class_id)
        except ValueError as exc:
            raise ValueError("无效的班级ID格式") from exc

        cls = db.query(Class).filter(
            Class.id == class_uuid,
            Class.teacher_id == uuid.UUID(teacher_id)
        ).first()


        if not cls:
            raise ValueError("班级不存在或无权限")

        return cls

    @staticmethod
    def _validate_selected_student_ids(
        db: Session,
        class_id: str,
        student_ids: Optional[List[str]],
    ) -> List[str]:
        if not student_ids:
            return []

        normalized_ids: List[str] = []
        seen_ids = set()
        for student_id in student_ids:
            normalized_id = str(student_id).strip()
            if not normalized_id or normalized_id in seen_ids:
                continue
            try:
                uuid.UUID(normalized_id)
            except ValueError as exc:
                raise ValueError("无效的学生ID格式") from exc
            seen_ids.add(normalized_id)
            normalized_ids.append(normalized_id)
            if len(normalized_ids) >= 4:
                break

        class_uuid = uuid.UUID(class_id)
        matched_students = (
            db.query(User)
            .filter(
                User.id.in_([uuid.UUID(student_id) for student_id in normalized_ids]),
                User.user_type == "student",
                User.class_id == class_uuid,
            )
            .all()
        )

        if len(matched_students) != len(normalized_ids):
            raise ValueError("所选学生必须属于当前班级")

        return normalized_ids

    @staticmethod
    def _normalize_editable_status(status: Optional[str], *, default: str = "published") -> str:
        normalized_status = (status or default).strip()
        if normalized_status not in {"draft", "published"}:
            raise ValueError("辩论状态仅支持 draft 或 published")
        return normalized_status

    @staticmethod
    def _serialize_assignment_preview_result(item: Dict[str, Any]) -> Dict[str, Any]:
        assigned_role = item.get("assigned_role")
        recommended_role = item.get("recommended_role")
        return {
            "user_id": item.get("user_id"),
            "name": item.get("name"),
            "avatar": item.get("avatar"),
            "recommended_role": recommended_role,
            "assigned_role": assigned_role,
            "role": assigned_role,
            "role_reason": DebateService.ROLE_REASON.get(assigned_role),
            "original_recommended_role": recommended_role,
            "teacher_override": bool(item.get("teacher_override")),
            "assignment_source": item.get("assignment_source"),
            "fit_score": item.get("fit_score"),
            "role_fit_score": item.get("role_fit_score"),
            "strength_score": item.get("strength_score"),
            "final_score": item.get("final_score"),
            "repeat_penalty": item.get("repeat_penalty"),
            "training_bonus": item.get("training_bonus"),
            "imbalance_penalty": item.get("imbalance_penalty"),
            "rotation_reason": item.get("rotation_reason"),
            "historical_role_distribution": item.get("historical_role_distribution"),
            "dimension_contribution": item.get("dimension_contribution"),
            "assignment_reason": item.get("assignment_reason"),
            "data_basis": item.get("data_basis"),
            "analysis_basis": item.get("analysis_basis"),
            "data_sources": item.get("data_sources"),
            "profile_confidence": item.get("profile_confidence"),
            "standard_profile": item.get("standard_profile"),
        }

    @staticmethod
    def _build_grouping_from_participations(
        db: Session,
        participations: List[DebateParticipation],
        snapshot_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if not participations:
            return []
        users = db.query(User).filter(User.id.in_([p.user_id for p in participations])).all()
        user_by_id = {u.id: u for u in users}
        role_rank = {r: i for i, r in enumerate(DebateService.ROLE_ORDER)}
        participations_sorted = sorted(participations, key=lambda p: role_rank.get(p.role, 99))
        snapshot_map = snapshot_map or {}
        results: List[Dict[str, Any]] = []
        for participation in participations_sorted:
            user_id = str(participation.user_id)
            snapshot = snapshot_map.get(user_id, {})
            user = user_by_id.get(participation.user_id)
            results.append(
                {
                    "user_id": user_id,
                    "name": user.name if user else "",
                    "avatar": (
                        AvatarService.build_avatar_payload(user)["avatar"]
                        if user
                        else None
                    ),
                    "role": participation.role,
                    "role_reason": participation.role_reason,
                    "recommended_role": snapshot.get("recommended_role", participation.role),
                    "assigned_role": participation.role,
                    "original_recommended_role": snapshot.get("recommended_role", participation.role),
                    "teacher_override": bool(snapshot.get("teacher_override")),
                    "assignment_source": snapshot.get("assignment_source", "rule_model"),
                    "fit_score": snapshot.get("fit_score"),
                    "role_fit_score": snapshot.get("role_fit_score"),
                    "strength_score": snapshot.get("strength_score"),
                    "final_score": snapshot.get("final_score"),
                    "repeat_penalty": snapshot.get("repeat_penalty"),
                    "training_bonus": snapshot.get("training_bonus"),
                    "imbalance_penalty": snapshot.get("imbalance_penalty"),
                    "rotation_reason": snapshot.get("rotation_reason"),
                    "historical_role_distribution": snapshot.get("historical_role_distribution"),
                    "dimension_contribution": snapshot.get("dimension_contribution"),
                    "assignment_reason": snapshot.get("assignment_reason"),
                    "data_basis": snapshot.get("data_basis"),
                    "analysis_basis": snapshot.get("analysis_basis"),
                    "data_sources": snapshot.get("data_sources"),
                    "profile_confidence": snapshot.get("profile_confidence"),
                    "standard_profile": snapshot.get("standard_profile"),
                }
            )
        return results

    @staticmethod
    def preview_role_assignment(
        db: Session,
        teacher_id: str,
        class_id: str,
        student_ids: List[str],
        *,
        config_meta: Optional[Dict[str, Any]] = None,
        role_assignments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        DebateService._get_teacher_class(db=db, teacher_id=teacher_id, class_id=class_id)
        normalized_student_ids = DebateService._validate_selected_student_ids(
            db=db,
            class_id=class_id,
            student_ids=student_ids,
        )
        normalized_config_meta = DebateService.normalize_debate_config_meta(config_meta)
        assignment_mode = normalized_config_meta.get("role_assignment_mode") or "strength_first"
        plan = DebateService._build_role_assignment_plan(
            db=db,
            student_ids=normalized_student_ids,
            role_assignments=role_assignments,
            assignment_mode=assignment_mode,
            config_meta=normalized_config_meta,
        )
        return {
            "class_id": class_id,
            "student_ids": normalized_student_ids,
            "assignment_mode": assignment_mode,
            "assignment_source": plan["assignment_source"],
            "role_rotation_policy": plan["role_rotation_policy"],
            "role_pool": plan["role_pool"],
            "results": [
                DebateService._serialize_assignment_preview_result(item)
                for item in plan["results"]
            ],
        }

    @staticmethod
    async def _assign_students_to_debate(
        db: Session,
        debate: Debate,
        selected_student_ids: List[str],
        *,
        replace_existing: bool,
        role_assignments: Optional[List[Dict[str, Any]]] = None,
        assignment_mode: str = "strength_first",
        config_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if replace_existing:
            db.query(DebateParticipation).filter(
                DebateParticipation.debate_id == debate.id,
                DebateParticipation.left_at.is_(None),
            ).delete()

        if not selected_student_ids:
            DebateService._persist_role_assignment_snapshot(
                debate,
                [],
                assignment_mode=assignment_mode,
                assignment_source="rule_model",
                role_rotation_policy=DebateService._role_rotation_defaults(config_meta)["role_rotation_policy"],
            )
            return

        plan = DebateService._build_role_assignment_plan(
            db=db,
            student_ids=selected_student_ids,
            role_assignments=role_assignments,
            assignment_mode=assignment_mode,
            config_meta=config_meta,
        )
        role_by_user_id = plan["assignment_map"]
        DebateService._persist_role_assignment_snapshot(
            debate,
            plan["results"],
            assignment_mode=assignment_mode,
            assignment_source=plan["assignment_source"],
            role_rotation_policy=plan["role_rotation_policy"],
        )

        for student_id in selected_student_ids:
            role = role_by_user_id.get(student_id)
            if role not in DebateService.ROLE_ORDER:
                raise ValueError("智能分组失败")
            db.add(
                DebateParticipation(
                    id=uuid.uuid4(),
                    debate_id=debate.id,
                    user_id=uuid.UUID(student_id),
                    role=role,
                    stance="positive",
                    role_reason=DebateService.ROLE_REASON.get(role),
                    seat_order=DebateService._seat_order_for_role(role),
                )
            )
    
    @staticmethod
    async def create_debate(
        db: Session,
        teacher_id: str,
        class_id: str,
        topic: str,
        duration: int,
        description: Optional[str] = None,
        config_meta: Optional[Dict[str, Any]] = None,
        student_ids: Optional[List[str]] = None,
        role_assignments: Optional[List[Dict[str, Any]]] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建辩论任务
        
        Args:
            db: 数据库会话
            teacher_id: 教师ID
            class_id: 班级ID
            topic: 辩题
            duration: 时长（分钟）
            description: 描述（可选）
            config_meta: 结构化建赛配置（可选）
            student_ids: 学生ID列表（可选）
            
        Returns:
            包含辩论信息的字典
            
        Raises:
            ValueError: 如果班级不存在或邀请码生成失败
        """
        DebateService._get_teacher_class(db=db, teacher_id=teacher_id, class_id=class_id)
        normalized_status = DebateService._normalize_editable_status(status)
        normalized_config_meta = DebateService.normalize_debate_config_meta(
            config_meta,
            description=description,
        )
        assignment_mode = normalized_config_meta.get("role_assignment_mode") or "strength_first"
        selected_student_ids = DebateService._validate_selected_student_ids(
            db=db,
            class_id=class_id,
            student_ids=student_ids,
        )
        
        # 生成唯一的邀请码（最多尝试10次）
        max_attempts = 10
        invitation_code = None
        
        for _ in range(max_attempts):
            code = DebateService.generate_invitation_code()
            existing = db.query(Debate).filter(Debate.invitation_code == code).first()
            if not existing:
                invitation_code = code
                break
        
        if not invitation_code:
            raise ValueError("生成邀请码失败，请重试")
        
        # 创建辩论
        debate = Debate(
            id=uuid.uuid4(),
            topic=topic,
            description=description,
            duration=duration,
            invitation_code=invitation_code,
            class_id=uuid.UUID(class_id),
            teacher_id=uuid.UUID(teacher_id),
            status=normalized_status,
            mode="teacher_assigned",
            visibility="private",
            capacity=4,
            creator_user_id=uuid.UUID(teacher_id),
            owner_user_id=uuid.UUID(teacher_id),
            host_user_id=uuid.UUID(teacher_id),
        )
        DebateService._persist_debate_config_meta(debate, normalized_config_meta)
        
        try:
            db.add(debate)
            db.commit()
            db.refresh(debate)
            
            if selected_student_ids:
                await DebateService._assign_students_to_debate(
                    db=db,
                    debate=debate,
                    selected_student_ids=selected_student_ids,
                    replace_existing=False,
                    role_assignments=role_assignments,
                    assignment_mode=assignment_mode,
                    config_meta=normalized_config_meta,
                )
                db.commit()
            
        except IntegrityError:
            db.rollback()
            raise ValueError("创建辩论失败")
        
        participations = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id,
            DebateParticipation.left_at.is_(None),
        ).all()
        user_ids = [str(p.user_id) for p in participations]
        snapshot_map = DebateService._role_assignment_snapshot_map(DebateService._get_room_meta(debate))
        grouping = DebateService._build_grouping_from_participations(db, participations, snapshot_map)

        return {
            "id": str(debate.id),
            **DebateService._serialize_debate_base(debate),
            "invitation_code": debate.invitation_code,
            "class_id": str(debate.class_id),
            "teacher_id": str(debate.teacher_id),
            "status": debate.status,
            "student_ids": user_ids,
            "grouping": grouping,
            "created_at": debate.created_at.isoformat()
        }
    
    @staticmethod
    async def update_debate(
        db: Session,
        teacher_id: str,
        debate_id: str,
        class_id: Optional[str] = None,
        topic: Optional[str] = None,
        duration: Optional[int] = None,
        description: Optional[str] = None,
        config_meta: Optional[Dict[str, Any]] = None,
        student_ids: Optional[List[str]] = None,
        role_assignments: Optional[List[Dict[str, Any]]] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        更新辩论任务
        
        Args:
            db: 数据库会话
            teacher_id: 教师ID
            debate_id: 辩论ID
            topic: 辩题（可选）
            duration: 时长（可选）
            description: 描述（可选）
            config_meta: 结构化建赛配置（可选）
            student_ids: 学生ID列表（可选）
            
        Returns:
            更新后的辩论信息
            
        Raises:
            ValueError: 如果辩论不存在或无权限
        """
        debate = db.query(Debate).filter(
            Debate.id == uuid.UUID(debate_id),
            Debate.teacher_id == uuid.UUID(teacher_id)
        ).first()

        next_status = (
            DebateService._normalize_editable_status(status, default=str(debate.status))
            if status is not None and debate is not None
            else (str(debate.status) if debate is not None else "published")
        )
        
        if not debate:
            raise ValueError("辩论不存在或无权限")
        
        # 允许修改 draft 和 published 状态，但进行中和已完成的不建议大幅修改
        # 这里暂时不做严格限制，由前端控制，或者仅限制无法修改已开始的辩论的关键参数
        if debate.status in ['in_progress', 'completed']:
             # 如果已经开始，仅允许修改描述
             if topic is not None and topic != debate.topic:
                 raise ValueError("无法修改进行中或已完成辩论的主题")
             if duration is not None and duration != debate.duration:
                 raise ValueError("无法修改进行中或已完成辩论的时长")

        if debate.status in ['in_progress', 'completed'] and next_status != debate.status:
             raise ValueError("无法修改进行中或已完成辩论的状态")

        normalized_class_id = str(debate.class_id)
        class_changed = False
        if class_id is not None and class_id != normalized_class_id:
            if debate.status in ["in_progress", "completed"]:
                raise ValueError("无法修改进行中或已完成辩论的班级")
            DebateService._get_teacher_class(db=db, teacher_id=teacher_id, class_id=class_id)
            debate.class_id = uuid.UUID(class_id)
            normalized_class_id = class_id
            class_changed = True

        if class_changed and student_ids is None:
            raise ValueError("修改班级时请重新选择辩手")
        
        existing_config_meta = DebateService._deserialize_debate_config_meta(debate)

        # 更新基本字段
        if topic is not None:
            debate.topic = topic
        if duration is not None:
            debate.duration = duration
        if description is not None:
            debate.description = description
        DebateService._persist_debate_config_meta(
            debate,
            config_meta if config_meta is not None else existing_config_meta,
        )
        effective_config_meta = DebateService._deserialize_debate_config_meta(debate)
        assignment_mode = effective_config_meta.get("role_assignment_mode") or "strength_first"
            
        # 更新参与学生
        if status is not None:
            debate.status = next_status
        if student_ids is not None:
            if debate.status in ["in_progress", "completed"]:
                raise ValueError("无法修改进行中或已完成辩论的辩手")
            selected_student_ids = DebateService._validate_selected_student_ids(
                db=db,
                class_id=normalized_class_id,
                student_ids=student_ids,
            )
            await DebateService._assign_students_to_debate(
                db=db,
                debate=debate,
                selected_student_ids=selected_student_ids,
                replace_existing=True,
                role_assignments=role_assignments,
                assignment_mode=assignment_mode,
                config_meta=effective_config_meta,
            )
        elif role_assignments is not None:
            if debate.status in ["in_progress", "completed"]:
                raise ValueError("无法修改进行中或已完成辩论的辩手")
            active_student_ids = [
                str(p.user_id)
                for p in db.query(DebateParticipation).filter(
                    DebateParticipation.debate_id == debate.id,
                    DebateParticipation.left_at.is_(None),
                ).all()
                if p.user_id
            ]
            await DebateService._assign_students_to_debate(
                db=db,
                debate=debate,
                selected_student_ids=active_student_ids,
                replace_existing=True,
                role_assignments=role_assignments,
                assignment_mode=assignment_mode,
                config_meta=effective_config_meta,
            )
        
        try:
            db.commit()
            db.refresh(debate)
        except IntegrityError:
            db.rollback()
            raise ValueError("更新辩论失败")
        
        participations = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id,
            DebateParticipation.left_at.is_(None),
        ).all()
        user_ids = [str(p.user_id) for p in participations]
        snapshot_map = DebateService._role_assignment_snapshot_map(DebateService._get_room_meta(debate))
        grouping = DebateService._build_grouping_from_participations(db, participations, snapshot_map)

        return {
            "id": str(debate.id),
            **DebateService._serialize_debate_base(debate),
            "invitation_code": debate.invitation_code,
            "class_id": str(debate.class_id),
            "teacher_id": str(debate.teacher_id),
            "status": debate.status,
            "student_ids": user_ids,
            "grouping": grouping,
            "created_at": debate.created_at.isoformat()
        }
    
    @staticmethod
    def publish_debate(
        db: Session,
        debate_id: str
    ) -> Dict[str, Any]:
        """
        发布辩论任务
        
        Args:
            db: 数据库会话
            debate_id: 辩论ID
            
        Returns:
            更新后的辩论信息
            
        Raises:
            ValueError: 如果辩论不存在或状态不正确
        """
        debate = db.query(Debate).filter(Debate.id == uuid.UUID(debate_id)).first()
        
        if not debate:
            raise ValueError("辩论不存在")
        
        if debate.status != 'draft':
            raise ValueError("只能发布草稿状态的辩论")
        
        debate.status = 'published'
        db.commit()
        db.refresh(debate)
        
        return {
            "id": str(debate.id),
            "topic": debate.topic,
            "invitation_code": debate.invitation_code,
            "status": debate.status
        }
    
    @staticmethod
    def get_debates(
        db: Session,
        teacher_id: Optional[str] = None,
        class_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取辩论列表
        
        Args:
            db: 数据库会话
            teacher_id: 教师ID（可选）
            class_id: 班级ID（可选）
            status: 状态（可选）
            
        Returns:
            辩论列表
        """
        query = db.query(Debate)
        
        if teacher_id:
            query = query.filter(Debate.teacher_id == uuid.UUID(teacher_id))
        if class_id:
            query = query.filter(Debate.class_id == uuid.UUID(class_id))
        if status:
            query = query.filter(Debate.status == status)
        
        debates = query.order_by(Debate.created_at.desc()).all()
        
        result = []
        for debate in debates:
            # 获取参与学生
            participations = db.query(DebateParticipation).filter(
                DebateParticipation.debate_id == debate.id,
                DebateParticipation.left_at.is_(None),
            ).all()
            
            student_ids = [str(p.user_id) for p in participations]
            
            result.append({
                "id": str(debate.id),
                "room_id": str(debate.id),
                "debate_id": str(debate.id),
                **DebateService._serialize_debate_base(debate),
                "invitation_code": debate.invitation_code,
                "class_id": str(debate.class_id),
                "status": debate.status,
                "participant_count": len(participations),
                "student_ids": student_ids,
                "created_at": debate.created_at.isoformat()
            })
        
        return result

    @staticmethod
    def get_debate(
        db: Session,
        debate_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取单个辩论详情
        
        Args:
            db: 数据库会话
            debate_id: 辩论ID
            
        Returns:
            辩论详情，如果不存在返回None
        """
        debate = db.query(Debate).filter(Debate.id == uuid.UUID(debate_id)).first()
        
        if not debate:
            return None
            
        # 获取参与学生
        participations = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id,
            DebateParticipation.left_at.is_(None),
        ).all()
        
        student_ids = [str(p.user_id) for p in participations]
        snapshot_map = DebateService._role_assignment_snapshot_map(DebateService._get_room_meta(debate))
        grouping = DebateService._build_grouping_from_participations(db, participations, snapshot_map)
        
        return {
            "id": str(debate.id),
            **DebateService._serialize_debate_base(debate),
            "invitation_code": debate.invitation_code,
            "class_id": str(debate.class_id),
            "teacher_id": str(debate.teacher_id),
            "status": debate.status,
            "participant_count": len(participations),
            "student_ids": student_ids,
            "grouping": grouping,
            "created_at": debate.created_at.isoformat()
        }
    
    @staticmethod
    def get_available_debates(
        db: Session,
        student_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取学生可参与的辩论列表
        
        Args:
            db: 数据库会话
            student_id: 学生ID
            
        Returns:
            可参与的辩论列表
        """
        # 获取学生的班级
        student = db.query(User).filter(User.id == uuid.UUID(student_id)).first()
        if not student or not student.class_id:
            return []
        
        # 获取该班级已发布的辩论
        debates = db.query(Debate).filter(
            Debate.class_id == student.class_id,
            Debate.status.in_(['published', 'draft']),
            Debate.mode == 'teacher_assigned'
        ).order_by(Debate.created_at.desc()).all()
        
        result = []
        for debate in debates:
            # 检查学生是否已参与
            participation = db.query(DebateParticipation).filter(
                DebateParticipation.debate_id == debate.id,
                DebateParticipation.user_id == uuid.UUID(student_id),
                DebateParticipation.left_at.is_(None),
            ).first()
            
            # 统计当前参与人数
            participant_count = db.query(DebateParticipation).filter(
                DebateParticipation.debate_id == debate.id,
                DebateParticipation.left_at.is_(None),
            ).count()

            participants = None
            if participation is not None:
                all_participations = db.query(DebateParticipation).filter(
                    DebateParticipation.debate_id == debate.id,
                    DebateParticipation.left_at.is_(None),
                ).all()
                users = db.query(User).filter(User.id.in_([p.user_id for p in all_participations])).all()
                user_by_id = {u.id: u for u in users}
                role_rank = {r: i for i, r in enumerate(DebateService.ROLE_ORDER)}
                all_participations_sorted = sorted(all_participations, key=lambda p: role_rank.get(p.role, 99))

                def overall_score_for(uid: str) -> int:
                    assessment = AssessmentService.get_assessment(db=db, user_id=uid) or {}
                    values = [
                        float(assessment.get("logical_thinking", 50)),
                        float(assessment.get("expression_willingness", 50)),
                        float(assessment.get("stablecoin_knowledge", 50)),
                        float(assessment.get("financial_knowledge", 50)),
                        float(assessment.get("critical_thinking", 50)),
                    ]
                    return int(round(sum(values) / len(values)))

                participants = [
                    {
                        "user_id": str(p.user_id),
                        "name": (user_by_id.get(p.user_id).name if user_by_id.get(p.user_id) else ""),
                        "avatar": (
                            AvatarService.build_avatar_payload(user_by_id.get(p.user_id))["avatar"]
                            if user_by_id.get(p.user_id)
                            else None
                        ),
                        "role": p.role,
                        "role_reason": p.role_reason,
                        "overall_score": overall_score_for(str(p.user_id)),
                    }
                    for p in all_participations_sorted
                ]
            
            result.append({
                "id": str(debate.id),
                **DebateService._serialize_debate_base(debate),
                "mode": DebateService._room_mode(debate),
                "room_source": DebateService._room_source_value(DebateService._room_mode(debate)),
                "invitation_code": debate.invitation_code,
                "participant_count": participant_count,
                "is_joined": participation is not None,
                "role": participation.role if participation else None,
                "role_reason": participation.role_reason if participation else None,
                "participants": participants,
                "created_at": debate.created_at.isoformat()
            })
        
        return result

    @staticmethod
    def list_lobby_rooms(
        db: Session,
        student_id: str,
        keyword: Optional[str] = None,
        visibility: Optional[str] = None,
        status: Optional[str] = None,
        sort: str = "latest",
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        student, _ = DebateService._get_student_with_class(db, student_id)
        if visibility and visibility not in {"public", "private"}:
            raise ValueError("房间类型参数不正确")
        if status and status not in {"waiting", "full", "ongoing", "finished", "cancelled"}:
            raise ValueError("房间状态参数不正确")
        if sort not in {"latest", "hot", "start_soon"}:
            raise ValueError("排序参数不正确")
        page = max(1, int(page or 1))
        page_size = min(max(1, int(page_size or 20)), 100)

        debates = db.query(Debate).filter(
            Debate.class_id == student.class_id,
            Debate.mode.in_(["student_lobby", "teacher_reserved"]),
            Debate.status.in_(["published", "draft", "in_progress", "completed"]),
        ).order_by(Debate.created_at.desc()).all()

        rooms: List[Dict[str, Any]] = []
        normalized_keyword = (keyword or "").strip().lower()
        for debate in debates:
            meta = DebateService._get_room_meta(debate)
            mode = DebateService._room_mode(debate, meta)
            if mode not in {"student_lobby", "teacher_reserved"}:
                continue
            if mode == "teacher_reserved" and not DebateService._student_can_see_reservation(db, debate, student_id):
                continue
            room = DebateService._serialize_lobby_room(db, debate)
            if visibility and room["visibility"] != visibility:
                continue
            if status and room["status"] != status:
                continue
            if normalized_keyword and normalized_keyword not in str(room["topic"]).lower() and normalized_keyword not in str(room["room_name"]).lower():
                continue
            rooms.append(room)

        if sort == "hot":
            rooms.sort(key=lambda item: (int(item.get("current_count") or 0), item.get("created_at") or ""), reverse=True)
        elif sort == "start_soon":
            rooms.sort(key=lambda item: item.get("scheduled_start_time") or item.get("created_at") or "")
        else:
            rooms.sort(key=lambda item: item.get("created_at") or "", reverse=True)

        total = len(rooms)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": rooms[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def create_lobby_room(
        db: Session,
        student_id: str,
        room_name: Optional[str],
        topic: str,
        description: Optional[str] = None,
        capacity: int = DEFAULT_ROOM_CAPACITY,
        visibility: str = "public",
        password: Optional[str] = None,
        allow_spectators: bool = False,
    ) -> Dict[str, Any]:
        student, cls = DebateService._get_student_with_class(db, student_id)
        topic = (topic or "").strip()
        if not topic:
            raise ValueError("辩题不能为空")
        if visibility not in {"public", "private"}:
            raise ValueError("房间类型参数不正确")
        try:
            capacity = int(capacity or DebateService.DEFAULT_ROOM_CAPACITY)
        except Exception as exc:
            raise ValueError("人数上限不正确") from exc
        if capacity < 2 or capacity > 4:
            raise ValueError("人数上限必须在 2 到 4 之间")
        if visibility == "private" and not (password or "").strip():
            raise ValueError("私密房间必须设置密码")

        active_existing = (
            db.query(Debate)
            .filter(
                Debate.class_id == student.class_id,
                Debate.mode == "student_lobby",
                Debate.host_user_id == student.id,
                Debate.status.in_(["draft", "published", "in_progress"]),
            )
            .order_by(Debate.created_at.desc())
            .all()
        )
        for debate in active_existing:
            if str(debate.status) != "completed":
                raise ValueError("您已有未结束的自发组队房间")

        debate = Debate(
            id=uuid.uuid4(),
            topic=topic,
            description=description,
            duration=30,
            invitation_code=DebateService._generate_unique_invitation_code(db),
            class_id=student.class_id,
            teacher_id=cls.teacher_id,
            status="published",
            mode="student_lobby",
            room_name=(room_name or "").strip() or topic[:30],
            visibility=visibility,
            capacity=capacity,
            creator_user_id=student.id,
            owner_user_id=student.id,
            host_user_id=student.id,
            join_password_hash=hash_password(str(password)) if visibility == "private" else None,
            password_updated_at=datetime.utcnow() if visibility == "private" else None,
            allow_spectators=bool(allow_spectators),
        )

        participation = DebateParticipation(
            id=uuid.uuid4(),
            debate_id=debate.id,
            user_id=student.id,
            role="debater_1",
            stance="positive",
            role_reason=DebateService.ROLE_REASON.get("debater_1"),
            is_moderator=True,
            is_room_owner=True,
            seat_order=1,
            joined_at=datetime.utcnow(),
        )

        try:
            db.add(debate)
            db.flush()
            db.add(participation)
            db.commit()
            db.refresh(debate)
        except IntegrityError:
            db.rollback()
            raise ValueError("创建房间失败")

        return DebateService.get_lobby_room_detail(db, student_id, str(debate.id))

    @staticmethod
    def join_lobby_room(
        db: Session,
        student_id: str,
        room_id: str,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        DebateService._get_student_with_class(db, student_id)
        try:
            room_uuid = uuid.UUID(str(room_id))
            student_uuid = uuid.UUID(str(student_id))
        except ValueError as exc:
            raise ValueError("房间ID格式不正确") from exc

        debate = db.query(Debate).filter(Debate.id == room_uuid).first()
        if not debate:
            raise ValueError("房间不存在")
        meta = DebateService._get_room_meta(debate)
        if DebateService._room_mode(debate, meta) != "student_lobby":
            raise ValueError("该房间不支持大厅加入")

        existing = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id,
            DebateParticipation.user_id == student_uuid,
            DebateParticipation.left_at.is_(None),
        ).first()
        if existing:
            room = DebateService.get_lobby_room_detail(db, student_id, str(debate.id))
            room.update({
                "joined": True,
                "participant_role": str(existing.role),
                "is_moderator": bool(room.get("current_user_permissions", {}).get("can_moderate")),
            })
            return room

        room_status = DebateService.resolve_room_status(
            debate,
            DebateService._participant_count(db, debate.id),
        )
        if room_status == "ongoing":
            raise ValueError("房间已开始")
        if room_status == "finished":
            raise ValueError("房间已结束")
        if room_status == "full":
            raise ValueError("房间已满")

        DebateService._ensure_private_password(debate, meta, password)

        members = DebateService._room_members(db, debate, meta)
        available_roles = DebateService._available_roles(members)
        if not available_roles:
            raise ValueError("房间已满")
        capacity = DebateService._room_capacity(debate, meta)
        seat_order = DebateService._next_available_seat(db, debate.id, capacity)
        role = DebateService._role_for_seat_order(seat_order)
        try:
            DebateService._create_participation(
                db=db,
                debate=debate,
                user_id=student_uuid,
                role=role,
                stance="positive",
                seat_order=seat_order,
            )
            db.commit()
        except ValueError:
            db.rollback()
            raise
        except IntegrityError:
            db.rollback()
            raise ValueError("加入房间失败，座位已被占用")

        room = DebateService.get_lobby_room_detail(db, student_id, str(debate.id))
        room.update({
            "joined": True,
            "participant_role": role,
            "is_moderator": bool(room.get("current_user_permissions", {}).get("can_moderate")),
        })
        return room

    @staticmethod
    def get_lobby_room_detail(
        db: Session,
        student_id: str,
        room_id: str,
    ) -> Dict[str, Any]:
        DebateService._get_student_with_class(db, student_id)
        try:
            room_uuid = uuid.UUID(str(room_id))
        except ValueError as exc:
            raise ValueError("房间ID格式不正确") from exc

        debate = db.query(Debate).filter(Debate.id == room_uuid).first()
        if not debate:
            raise ValueError("房间不存在")
        meta = DebateService._get_room_meta(debate)
        mode = DebateService._room_mode(debate, meta)
        if mode not in {"student_lobby", "teacher_reserved"}:
            raise ValueError("房间不存在")
        if mode == "teacher_reserved" and not DebateService._student_can_see_reservation(db, debate, student_id):
            raise ValueError("无权查看该预约房间")

        room = DebateService._serialize_lobby_room(db, debate, student_id=student_id)
        members = room.get("members") or []
        available_roles = DebateService._available_roles(members)
        room.update({
            "available_roles": available_roles,
            "can_join": bool(available_roles) and room["status"] == "waiting",
            "join_block_reason": None,
            "is_current_user_joined": bool(room.get("current_user_permissions", {}).get("is_joined")),
            "current_user_role": room.get("current_user_permissions", {}).get("role"),
        })
        if room["status"] == "full":
            room["can_join"] = False
            room["join_block_reason"] = "房间已满"
        elif room["status"] == "ongoing":
            room["can_join"] = False
            room["join_block_reason"] = "房间已开始"
        elif room["status"] == "finished":
            room["can_join"] = False
            room["join_block_reason"] = "房间已结束"
        elif room["status"] == "cancelled":
            room["can_join"] = False
            room["join_block_reason"] = "预约已取消"
        return room

    @staticmethod
    async def create_reservation(
        db: Session,
        teacher_id: str,
        class_id: str,
        topic: str,
        duration: int,
        description: Optional[str] = None,
        config_meta: Optional[Dict[str, Any]] = None,
        scheduled_start_time: Any = None,
        checkin_open_time: Any = None,
        checkin_close_time: Any = None,
        student_ids: Optional[List[str]] = None,
        role_assignments: Optional[List[Dict[str, Any]]] = None,
        visibility: str = "private",
        password: Optional[str] = None,
        host_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        DebateService._get_teacher_class(db=db, teacher_id=teacher_id, class_id=class_id)
        topic = (topic or "").strip()
        if not topic:
            raise ValueError("辩题不能为空")
        if int(duration or 0) <= 0:
            raise ValueError("预计时长必须大于 0")
        if visibility not in {"public", "private"}:
            raise ValueError("房间类型参数不正确")
        normalized_config_meta = DebateService.normalize_debate_config_meta(
            config_meta,
            description=description,
        )
        assignment_mode = normalized_config_meta.get("role_assignment_mode") or "strength_first"
        scheduled_dt = DebateService._normalize_datetime(scheduled_start_time)
        if not scheduled_dt:
            raise ValueError("开赛时间不能为空")
        if scheduled_dt <= datetime.utcnow():
            raise ValueError("开赛时间必须晚于当前时间")
        checkin_open_dt = DebateService._normalize_datetime(checkin_open_time) if checkin_open_time else scheduled_dt - timedelta(minutes=15)
        checkin_close_dt = DebateService._normalize_datetime(checkin_close_time) if checkin_close_time else scheduled_dt + timedelta(minutes=5)
        if checkin_open_dt >= checkin_close_dt:
            raise ValueError("签到开始时间必须早于签到结束时间")

        selected_student_ids = DebateService._validate_selected_student_ids(
            db=db,
            class_id=class_id,
            student_ids=student_ids,
        )
        if not selected_student_ids:
            raise ValueError("预约至少需要邀请一名学生")
        host_uuid = uuid.UUID(str(teacher_id))
        if host_user_id:
            try:
                host_uuid = uuid.UUID(str(host_user_id))
            except ValueError as exc:
                raise ValueError("主持人ID格式不正确") from exc
            host = db.query(User).filter(
                User.id == host_uuid,
                User.user_type == "student",
                User.class_id == uuid.UUID(str(class_id)),
            ).first()
            if not host or str(host.id) not in selected_student_ids:
                raise ValueError("学生主持人必须来自本次受邀名单")

        debate = Debate(
            id=uuid.uuid4(),
            topic=topic,
            description=description,
            duration=int(duration),
            invitation_code=DebateService._generate_unique_invitation_code(db),
            class_id=uuid.UUID(str(class_id)),
            teacher_id=uuid.UUID(str(teacher_id)),
            status="published",
            mode="teacher_reserved",
            room_name=topic[:30],
            visibility=visibility,
            capacity=min(max(len(selected_student_ids), 1), 4),
            creator_user_id=uuid.UUID(str(teacher_id)),
            owner_user_id=uuid.UUID(str(teacher_id)),
            host_user_id=host_uuid,
            scheduled_start_time=scheduled_dt,
            checkin_open_time=checkin_open_dt,
            checkin_close_time=checkin_close_dt,
            join_password_hash=hash_password(str(password)) if visibility == "private" and password else None,
            password_updated_at=datetime.utcnow() if visibility == "private" and password else None,
            reservation_status="scheduled",
            reservation_published_at=datetime.utcnow(),
        )
        DebateService._persist_debate_config_meta(debate, normalized_config_meta)
        if not password:
            debate.join_password_hash = None
            debate.password_updated_at = None

        try:
            db.add(debate)
            db.flush()
            plan = DebateService._build_role_assignment_plan(
                db=db,
                student_ids=selected_student_ids,
                role_assignments=role_assignments,
                assignment_mode=assignment_mode,
                config_meta=normalized_config_meta,
            )
            DebateService._persist_role_assignment_snapshot(
                debate,
                plan["results"],
                assignment_mode=assignment_mode,
                assignment_source=plan["assignment_source"],
                role_rotation_policy=plan["role_rotation_policy"],
            )
            for item in plan["results"]:
                student_id = item["user_id"]
                role = item["assigned_role"]
                db.add(
                    DebateReservationInvitation(
                        id=uuid.uuid4(),
                        debate_id=debate.id,
                        student_id=uuid.UUID(str(student_id)),
                        invited_by_teacher_id=uuid.UUID(str(teacher_id)),
                        assigned_role=role,
                        assigned_stance="positive" if role else None,
                        is_designated_moderator=bool(host_user_id and str(host_user_id) == str(student_id)),
                        response_status="pending",
                        read_status="unread",
                        attendance_status="not_checked_in",
                    )
                )
            db.commit()
            db.refresh(debate)
        except IntegrityError:
            db.rollback()
            raise ValueError("创建预约失败")

        return DebateService.get_teacher_reservation(db, teacher_id, str(debate.id))

    @staticmethod
    def _reservation_counts(db: Session, debate_id: uuid.UUID) -> Dict[str, int]:
        values = db.query(DebateReservationInvitation).filter(
            DebateReservationInvitation.debate_id == debate_id,
        ).all()
        return {
            "invited_count": len(values),
            "accepted_count": len([
                item for item in values
                if item.revoked_at is None and str(item.response_status) == "accepted"
            ]),
            "rejected_count": len([
                item for item in values
                if item.revoked_at is None and str(item.response_status) == "rejected"
            ]),
            "checked_in_count": len([
                item for item in values
                if item.revoked_at is None and str(item.attendance_status) == "checked_in"
            ]),
            "revoked_count": len([item for item in values if item.revoked_at is not None]),
        }

    @staticmethod
    def _serialize_teacher_reservation(db: Session, debate: Debate) -> Dict[str, Any]:
        meta = DebateService._get_room_meta(debate)
        counts = DebateService._reservation_counts(db, debate.id)
        class_obj = db.query(Class).filter(Class.id == debate.class_id).first()
        return {
            "reservation_id": str(debate.id),
            "room_id": str(debate.id),
            **DebateService._serialize_debate_base(debate),
            "class_id": str(debate.class_id),
            "class_name": class_obj.name if class_obj else "",
            "scheduled_start_time": DebateService._debate_datetime_iso(debate, "scheduled_start_time", meta),
            "checkin_open_time": DebateService._debate_datetime_iso(debate, "checkin_open_time", meta),
            "checkin_close_time": DebateService._debate_datetime_iso(debate, "checkin_close_time", meta),
            "visibility": DebateService._room_visibility(debate, meta),
            "host_user_id": DebateService._room_host_user_id(debate, meta),
            "status": DebateService.resolve_reservation_status(debate),
            "room_status": DebateService.resolve_room_status(
                debate,
                DebateService._participant_count(db, debate.id),
            ),
            "invitations": DebateService._reservation_invitations_map(db, debate.id, active_only=False),
            "role_assignment_snapshot": meta.get("role_assignment_snapshot", []),
            "cancelled_at": debate.cancelled_at.isoformat() if debate.cancelled_at else meta.get("cancelled_at"),
            "cancel_reason": debate.cancel_reason or meta.get("cancel_reason"),
            **counts,
        }

    @staticmethod
    def get_teacher_reservation(
        db: Session,
        teacher_id: str,
        reservation_id: str,
    ) -> Dict[str, Any]:
        try:
            reservation_uuid = uuid.UUID(str(reservation_id))
        except ValueError as exc:
            raise ValueError("预约ID格式不正确") from exc
        debate = db.query(Debate).filter(
            Debate.id == reservation_uuid,
            Debate.teacher_id == uuid.UUID(str(teacher_id)),
        ).first()
        if not debate or DebateService._room_mode(debate) != "teacher_reserved":
            raise ValueError("预约不存在或无权限")
        return DebateService._serialize_teacher_reservation(db, debate)

    @staticmethod
    def list_teacher_reservations(
        db: Session,
        teacher_id: str,
        class_id: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[Any] = None,
        date_to: Optional[Any] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        if class_id:
            DebateService._get_teacher_class(db=db, teacher_id=teacher_id, class_id=class_id)
        date_from_dt = DebateService._normalize_datetime(date_from) if date_from else None
        date_to_dt = DebateService._normalize_datetime(date_to) if date_to else None
        page = max(1, int(page or 1))
        page_size = min(max(1, int(page_size or 20)), 100)

        query = db.query(Debate).filter(
            Debate.teacher_id == uuid.UUID(str(teacher_id)),
            Debate.mode == "teacher_reserved",
        )
        if class_id:
            query = query.filter(Debate.class_id == uuid.UUID(str(class_id)))
        if date_from_dt:
            query = query.filter(Debate.scheduled_start_time >= date_from_dt)
        if date_to_dt:
            query = query.filter(Debate.scheduled_start_time <= date_to_dt)
        debates = query.order_by(Debate.created_at.desc()).all()
        items = []
        for debate in debates:
            if DebateService._room_mode(debate) != "teacher_reserved":
                continue
            meta = DebateService._get_room_meta(debate)
            scheduled_dt = DebateService._debate_datetime(debate, "scheduled_start_time", meta)
            if date_from_dt and scheduled_dt and scheduled_dt < date_from_dt:
                continue
            if date_to_dt and scheduled_dt and scheduled_dt > date_to_dt:
                continue
            item = DebateService._serialize_teacher_reservation(db, debate)
            if status and item["status"] != status:
                continue
            items.append(item)

        total = len(items)
        start = (page - 1) * page_size
        return {
            "items": items[start:start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def update_reservation(
        db: Session,
        teacher_id: str,
        reservation_id: str,
        topic: Optional[str] = None,
        description: Optional[str] = None,
        config_meta: Optional[Dict[str, Any]] = None,
        duration: Optional[int] = None,
        scheduled_start_time: Any = None,
        checkin_open_time: Any = None,
        checkin_close_time: Any = None,
        student_ids: Optional[List[str]] = None,
        role_assignments: Optional[List[Dict[str, Any]]] = None,
        visibility: Optional[str] = None,
        password: Optional[str] = None,
        host_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            reservation_uuid = uuid.UUID(str(reservation_id))
        except ValueError as exc:
            raise ValueError("预约ID格式不正确") from exc
        debate = db.query(Debate).filter(
            Debate.id == reservation_uuid,
            Debate.teacher_id == uuid.UUID(str(teacher_id)),
        ).first()
        if not debate or DebateService._room_mode(debate) != "teacher_reserved":
            raise ValueError("预约不存在或无权限")
        if str(debate.status) in {"in_progress", "completed"}:
            raise ValueError("无法修改进行中或已完成预约")
        meta = DebateService._get_room_meta(debate)
        if DebateService.resolve_reservation_status(debate) == "cancelled":
            raise ValueError("无法修改已取消预约")
        existing_config_meta = DebateService._deserialize_debate_config_meta(debate)

        if topic is not None:
            topic = topic.strip()
            if not topic:
                raise ValueError("辩题不能为空")
            debate.topic = topic
            debate.room_name = debate.room_name or topic[:30]
        if description is not None:
            debate.description = description
        DebateService._persist_debate_config_meta(
            debate,
            config_meta if config_meta is not None else existing_config_meta,
        )
        effective_config_meta = DebateService._deserialize_debate_config_meta(debate)
        assignment_mode = effective_config_meta.get("role_assignment_mode") or "strength_first"
        if duration is not None:
            if int(duration) <= 0:
                raise ValueError("预计时长必须大于 0")
            debate.duration = int(duration)
        if visibility is not None:
            if visibility not in {"public", "private"}:
                raise ValueError("房间类型参数不正确")
            debate.visibility = visibility
        if password:
            debate.join_password_hash = hash_password(str(password))
            debate.password_updated_at = datetime.utcnow()
        if scheduled_start_time is not None:
            scheduled_dt = DebateService._normalize_datetime(scheduled_start_time)
            if not scheduled_dt:
                raise ValueError("开赛时间不能为空")
            if scheduled_dt <= datetime.utcnow():
                raise ValueError("开赛时间必须晚于当前时间")
            debate.scheduled_start_time = scheduled_dt
            if checkin_open_time is None and not debate.checkin_open_time:
                debate.checkin_open_time = scheduled_dt - timedelta(minutes=15)
            if checkin_close_time is None and not debate.checkin_close_time:
                debate.checkin_close_time = scheduled_dt + timedelta(minutes=5)
        if checkin_open_time is not None:
            debate.checkin_open_time = DebateService._normalize_datetime(checkin_open_time)
        if checkin_close_time is not None:
            debate.checkin_close_time = DebateService._normalize_datetime(checkin_close_time)

        selected_student_ids = None
        if student_ids is not None:
            selected_student_ids = DebateService._validate_selected_student_ids(
                db=db,
                class_id=str(debate.class_id),
                student_ids=student_ids,
            )
            if not selected_student_ids:
                raise ValueError("预约至少需要邀请一名学生")
            debate.capacity = min(max(len(selected_student_ids), 1), 4)
            selected_set = set(selected_student_ids)
            now = datetime.utcnow()
            existing_active = DebateService._active_invitation_query(db, debate.id).all()
            existing_by_student_id = {
                str(invitation.student_id): invitation
                for invitation in existing_active
            }
            plan = DebateService._build_role_assignment_plan(
                db=db,
                student_ids=selected_student_ids,
                role_assignments=role_assignments,
                assignment_mode=assignment_mode,
                config_meta=effective_config_meta,
            )
            DebateService._persist_role_assignment_snapshot(
                debate,
                plan["results"],
                assignment_mode=assignment_mode,
                assignment_source=plan["assignment_source"],
                role_rotation_policy=plan["role_rotation_policy"],
            )
            planned_role_by_student_id = {
                item["user_id"]: item["assigned_role"]
                for item in plan["results"]
            }
            for invitation in existing_active:
                if str(invitation.student_id) not in selected_set:
                    invitation.revoked_at = now
                    invitation.revoked_by_teacher_id = uuid.UUID(str(teacher_id))
                    invitation.revoke_reason = "teacher_update_removed"
                    invitation.updated_at = now

            for student_id in selected_student_ids:
                role = planned_role_by_student_id.get(student_id)
                invitation = existing_by_student_id.get(str(student_id))
                if invitation:
                    invitation.assigned_role = role
                    invitation.assigned_stance = "positive" if role else None
                    invitation.updated_at = now
                    continue
                db.add(
                    DebateReservationInvitation(
                        id=uuid.uuid4(),
                        debate_id=debate.id,
                        student_id=uuid.UUID(str(student_id)),
                        invited_by_teacher_id=uuid.UUID(str(teacher_id)),
                        assigned_role=role,
                        assigned_stance="positive" if role else None,
                        response_status="pending",
                        read_status="unread",
                        attendance_status="not_checked_in",
                    )
                )
        elif role_assignments is not None:
            active_student_ids = list(DebateService._invitation_student_ids(db, debate.id))
            plan = DebateService._build_role_assignment_plan(
                db=db,
                student_ids=active_student_ids,
                role_assignments=role_assignments,
                assignment_mode=assignment_mode,
                config_meta=effective_config_meta,
            )
            DebateService._persist_role_assignment_snapshot(
                debate,
                plan["results"],
                assignment_mode=assignment_mode,
                assignment_source=plan["assignment_source"],
                role_rotation_policy=plan["role_rotation_policy"],
            )
            planned_role_by_student_id = {
                item["user_id"]: item["assigned_role"]
                for item in plan["results"]
            }
            for invitation in DebateService._active_invitation_query(db, debate.id).all():
                role = planned_role_by_student_id.get(str(invitation.student_id))
                invitation.assigned_role = role
                invitation.assigned_stance = "positive" if role else None
                invitation.updated_at = datetime.utcnow()
        if host_user_id is not None:
            if host_user_id:
                valid_ids = set(selected_student_ids or DebateService._invitation_student_ids(db, debate.id))
                if str(host_user_id) not in valid_ids:
                    raise ValueError("学生主持人必须来自本次受邀名单")
                debate.host_user_id = uuid.UUID(str(host_user_id))
            else:
                debate.host_user_id = uuid.UUID(str(teacher_id))

        if debate.checkin_open_time and debate.checkin_close_time and debate.checkin_open_time >= debate.checkin_close_time:
            raise ValueError("签到开始时间必须早于签到结束时间")

        host_id = str(debate.host_user_id) if debate.host_user_id else None
        for invitation in DebateService._active_invitation_query(db, debate.id).all():
            invitation.is_designated_moderator = bool(host_id and str(invitation.student_id) == host_id)
            invitation.updated_at = datetime.utcnow()
        try:
            db.commit()
            db.refresh(debate)
        except IntegrityError:
            db.rollback()
            raise ValueError("更新预约失败")
        return DebateService.get_teacher_reservation(db, teacher_id, reservation_id)

    @staticmethod
    def cancel_reservation(
        db: Session,
        teacher_id: str,
        reservation_id: str,
        cancel_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            reservation_uuid = uuid.UUID(str(reservation_id))
        except ValueError as exc:
            raise ValueError("预约ID格式不正确") from exc
        debate = db.query(Debate).filter(
            Debate.id == reservation_uuid,
            Debate.teacher_id == uuid.UUID(str(teacher_id)),
        ).first()
        if not debate or DebateService._room_mode(debate) != "teacher_reserved":
            raise ValueError("预约不存在或无权限")
        if str(debate.status) in {"in_progress", "completed"}:
            raise ValueError("无法取消进行中或已完成预约")
        now = datetime.utcnow()
        debate.reservation_status = "cancelled"
        debate.cancelled_at = now
        debate.cancel_reason = cancel_reason
        for invitation in DebateService._active_invitation_query(db, debate.id).all():
            if str(invitation.response_status) == "pending":
                invitation.response_status = "expired"
                invitation.updated_at = now
        db.commit()
        return DebateService.get_teacher_reservation(db, teacher_id, reservation_id)

    @staticmethod
    def _serialize_student_reservation(
        db: Session,
        debate: Debate,
        student_id: str,
        invitation: Optional[DebateReservationInvitation] = None,
    ) -> Dict[str, Any]:
        meta = DebateService._get_room_meta(debate)
        invitation = invitation or DebateService._get_active_invitation(db, debate.id, student_id)
        legacy_invitation = (meta.get("invitations") or {}).get(str(student_id), {}) if not invitation else {}
        response_status = str(invitation.response_status) if invitation else legacy_invitation.get("response_status", "pending")
        attendance_status = str(invitation.attendance_status) if invitation else legacy_invitation.get("attendance_status", "not_checked_in")
        assigned_role = str(invitation.assigned_role) if invitation and invitation.assigned_role else legacy_invitation.get("role")
        status_value = DebateService.resolve_reservation_status(debate)
        can_check_in = (
            response_status == "accepted"
            and attendance_status != "checked_in"
            and status_value == "checkin_open"
        )
        room_entry_enabled = (
            response_status == "accepted"
            and attendance_status == "checked_in"
            and status_value not in {"cancelled", "completed"}
        )
        return {
            "reservation_id": str(debate.id),
            "room_id": str(debate.id),
            "debate_id": str(debate.id),
            **DebateService._serialize_debate_base(debate),
            "teacher_id": str(debate.teacher_id),
            "teacher_name": debate.teacher.name if debate.teacher else "",
            "scheduled_start_time": DebateService._debate_datetime_iso(debate, "scheduled_start_time", meta),
            "checkin_open_time": DebateService._debate_datetime_iso(debate, "checkin_open_time", meta),
            "checkin_close_time": DebateService._debate_datetime_iso(debate, "checkin_close_time", meta),
            "role": assigned_role,
            "invitation_status": response_status,
            "read_status": str(invitation.read_status) if invitation else legacy_invitation.get("read_status", "unread"),
            "checkin_status": attendance_status,
            "checked_in_at": (
                invitation.checked_in_at.isoformat()
                if invitation and invitation.checked_in_at
                else legacy_invitation.get("checked_in_at")
            ),
            "status": status_value,
            "room_status": DebateService.resolve_room_status(
                debate,
                DebateService._participant_count(db, debate.id),
            ),
            "can_check_in": can_check_in,
            "checkin_block_reason": None if can_check_in else "当前不可签到",
            "room_entry_enabled": room_entry_enabled,
        }

    @staticmethod
    def list_student_reservations(
        db: Session,
        student_id: str,
        status: Optional[str] = None,
        include_cancelled: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        DebateService._get_student_with_class(db, student_id)
        page = max(1, int(page or 1))
        page_size = min(max(1, int(page_size or 20)), 100)
        query = (
            db.query(DebateReservationInvitation)
            .join(Debate, DebateReservationInvitation.debate_id == Debate.id)
            .filter(
                DebateReservationInvitation.student_id == uuid.UUID(str(student_id)),
                DebateReservationInvitation.revoked_at.is_(None),
                Debate.mode == "teacher_reserved",
                Debate.status.in_(["draft", "published", "in_progress", "completed"]),
            )
            .order_by(Debate.scheduled_start_time.desc(), Debate.created_at.desc())
        )
        items = []
        for invitation in query.all():
            debate = invitation.debate
            if not debate:
                continue
            item = DebateService._serialize_student_reservation(db, debate, student_id, invitation)
            if not include_cancelled and item["status"] == "cancelled":
                continue
            if status and item["status"] != status:
                continue
            items.append(item)
        total = len(items)
        start = (page - 1) * page_size
        return {
            "items": items[start:start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def respond_reservation_invitation(
        db: Session,
        student_id: str,
        reservation_id: str,
        action: str,
    ) -> Dict[str, Any]:
        if action not in {"accept", "reject"}:
            raise ValueError("邀请响应动作不正确")
        try:
            reservation_uuid = uuid.UUID(str(reservation_id))
            student_uuid = uuid.UUID(str(student_id))
        except ValueError as exc:
            raise ValueError("预约ID或学生ID格式不正确") from exc
        debate = db.query(Debate).filter(Debate.id == reservation_uuid).first()
        if not debate:
            raise ValueError("预约不存在")
        if DebateService._room_mode(debate) != "teacher_reserved":
            raise ValueError("预约不存在或无权限")
        invitation = DebateService._get_active_invitation(db, debate.id, student_id)
        if not invitation:
            raise ValueError("预约不存在或无权限")
        if DebateService.resolve_reservation_status(debate) == "cancelled":
            raise ValueError("预约已取消")
        if str(invitation.response_status) == "expired":
            raise ValueError("邀请已过期")
        desired_status = "accepted" if action == "accept" else "rejected"
        current_status = str(invitation.response_status)
        if current_status in {"accepted", "rejected"} and current_status != desired_status:
            raise ValueError("邀请已响应，不能重复修改")
        now = datetime.utcnow()
        invitation.response_status = desired_status
        invitation.read_status = "read"
        invitation.read_at = invitation.read_at or now
        invitation.responded_at = invitation.responded_at or now
        invitation.updated_at = now
        if action == "reject":
            invitation.attendance_status = "not_checked_in"
        db.commit()
        db.refresh(invitation)
        return DebateService._serialize_student_reservation(db, debate, str(student_uuid), invitation)

    @staticmethod
    def check_in_reservation(
        db: Session,
        student_id: str,
        reservation_id: str,
    ) -> Dict[str, Any]:
        try:
            reservation_uuid = uuid.UUID(str(reservation_id))
            student_uuid = uuid.UUID(str(student_id))
        except ValueError as exc:
            raise ValueError("预约ID或学生ID格式不正确") from exc
        debate = db.query(Debate).filter(Debate.id == reservation_uuid).first()
        if not debate:
            raise ValueError("预约不存在")
        if DebateService._room_mode(debate) != "teacher_reserved":
            raise ValueError("预约不存在或无权限")
        invitation = DebateService._get_active_invitation(db, debate.id, student_id)
        if not invitation:
            raise ValueError("预约不存在或无权限")
        status_value = DebateService.resolve_reservation_status(debate)
        if status_value == "cancelled":
            raise ValueError("预约已取消")
        if str(invitation.response_status) != "accepted":
            raise ValueError("请先接受邀请")
        if str(invitation.attendance_status) == "checked_in":
            result = DebateService._serialize_student_reservation(db, debate, student_id, invitation)
            result.update({"checked_in": True})
            return result
        if status_value != "checkin_open":
            raise ValueError("当前不在签到窗口内")
        now = datetime.utcnow()
        invitation.attendance_status = "checked_in"
        invitation.checked_in_at = now
        invitation.updated_at = now
        role = str(invitation.assigned_role) if invitation.assigned_role else None
        if role not in DebateService.ROLE_ORDER:
            seat_order = DebateService._next_available_seat(
                db,
                debate.id,
                DebateService._room_capacity(debate),
            )
            role = DebateService._role_for_seat_order(seat_order)
        else:
            seat_order = DebateService._seat_order_for_role(role)
        stance = str(invitation.assigned_stance or "positive")
        existing = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id,
            DebateParticipation.user_id == student_uuid,
            DebateParticipation.left_at.is_(None),
        ).first()
        try:
            if not existing:
                DebateService._create_participation(
                    db=db,
                    debate=debate,
                    user_id=student_uuid,
                    role=role,
                    stance=stance,
                    invitation=invitation,
                    invited_by=invitation.invited_by_teacher_id,
                    is_moderator=bool(invitation.is_designated_moderator),
                    attendance_status="checked_in",
                    checked_in_at=now,
                    seat_order=seat_order,
                )
            else:
                existing.invitation_id = invitation.id
                existing.attendance_status = "checked_in"
                existing.checked_in_at = existing.checked_in_at or now
                existing.last_seen_at = now
                if invitation.is_designated_moderator:
                    existing.is_moderator = True
            db.commit()
        except ValueError:
            db.rollback()
            raise
        except IntegrityError:
            db.rollback()
            raise ValueError("签到失败，座位已被占用")
        result = DebateService._serialize_student_reservation(db, debate, student_id, invitation)
        result.update({
            "checked_in": True,
            "participant_role": result.get("role"),
            "can_speak": True,
            "can_moderate": bool(invitation.is_designated_moderator),
        })
        return result

    @staticmethod
    def list_student_reservation_reminders(
        db: Session,
        student_id: str,
        now: Optional[datetime] = None,
        unread_only: bool = False,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        now = now or datetime.utcnow()
        reservations = DebateService.list_student_reservations(
            db=db,
            student_id=student_id,
            include_cancelled=False,
            page=1,
            page_size=100,
        )["items"]
        reminders = []
        for reservation in reservations:
            scheduled = DebateService._normalize_datetime(reservation.get("scheduled_start_time"))
            if not scheduled:
                continue
            delta = scheduled - now
            reminder_type = None
            title = None
            if timedelta(0) <= delta <= timedelta(hours=24):
                reminder_type = "before_24h"
                title = "预约辩论即将开始"
            if timedelta(0) <= delta <= timedelta(minutes=15):
                reminder_type = "before_15m"
                title = "请准备进入候场"
            if now > scheduled + timedelta(minutes=5) and reservation.get("checkin_status") != "checked_in":
                reminder_type = "missed_checkin"
                title = "预约辩论尚未签到"
            if not reminder_type:
                continue
            reminders.append({
                "reminder_id": f"{reservation['reservation_id']}:{reminder_type}",
                "reservation_id": reservation["reservation_id"],
                "type": reminder_type,
                "title": title,
                "content": reservation["topic"],
                "scheduled_start_time": reservation.get("scheduled_start_time"),
                "created_at": now.isoformat(),
                "read": False,
            })
        if unread_only:
            reminders = [reminder for reminder in reminders if not reminder.get("read")]
        return reminders[: max(1, int(limit or 20))]

    @staticmethod
    def get_debate_participants_for_student(
        db: Session,
        debate_id: str,
        student_id: str
    ) -> List[Dict[str, Any]]:
        try:
            debate_uuid = uuid.UUID(debate_id)
            student_uuid = uuid.UUID(student_id)
        except ValueError as e:
            raise ValueError("Invalid debate_id or student_id") from e

        participation = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_uuid,
            DebateParticipation.user_id == student_uuid
        ).first()
        if not participation:
            raise ValueError("您未参与该辩论")

        all_participations = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_uuid
        ).all()

        users = db.query(User).filter(User.id.in_([p.user_id for p in all_participations])).all()
        user_by_id = {u.id: u for u in users}
        role_rank = {r: i for i, r in enumerate(DebateService.ROLE_ORDER)}
        all_participations_sorted = sorted(all_participations, key=lambda p: role_rank.get(p.role, 99))

        def overall_score_for(uid: str) -> int:
            assessment = AssessmentService.get_assessment(db=db, user_id=uid) or {}
            values = [
                float(assessment.get("logical_thinking", 50)),
                float(assessment.get("expression_willingness", 50)),
                float(assessment.get("stablecoin_knowledge", 50)),
                float(assessment.get("financial_knowledge", 50)),
                float(assessment.get("critical_thinking", 50)),
            ]
            return int(round(sum(values) / len(values)))

        return [
            {
                "user_id": str(p.user_id),
                "name": (user_by_id.get(p.user_id).name if user_by_id.get(p.user_id) else ""),
                "avatar": (
                    AvatarService.build_avatar_payload(user_by_id.get(p.user_id))["avatar"]
                    if user_by_id.get(p.user_id)
                    else None
                ),
                "role": p.role,
                "role_reason": p.role_reason,
                "overall_score": overall_score_for(str(p.user_id)),
            }
            for p in all_participations_sorted
        ]

    @staticmethod
    def get_debate_participants_for_teacher(
        db: Session,
        debate_id: str,
    ) -> List[Dict[str, Any]]:
        try:
            debate_uuid = uuid.UUID(debate_id)
        except ValueError as e:
            raise ValueError("Invalid debate_id") from e

        all_participations = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate_uuid
        ).all()

        user_ids = [p.user_id for p in all_participations if p.user_id]
        users = []
        if user_ids:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_by_id = {u.id: u for u in users}

        role_rank = {r: i for i, r in enumerate(DebateService.ROLE_ORDER)}
        all_participations_sorted = sorted(all_participations, key=lambda p: role_rank.get(p.role, 99))

        def overall_score_for(uid: str) -> int:
            assessment = AssessmentService.get_assessment(db=db, user_id=uid) or {}
            values = [
                float(assessment.get("logical_thinking", 50)),
                float(assessment.get("expression_willingness", 50)),
                float(assessment.get("stablecoin_knowledge", 50)),
                float(assessment.get("financial_knowledge", 50)),
                float(assessment.get("critical_thinking", 50)),
            ]
            return int(round(sum(values) / len(values)))

        return [
            {
                "user_id": str(p.user_id),
                "name": (user_by_id.get(p.user_id).name if user_by_id.get(p.user_id) else ""),
                "avatar": (
                    AvatarService.build_avatar_payload(user_by_id.get(p.user_id))["avatar"]
                    if user_by_id.get(p.user_id)
                    else None
                ),
                "role": p.role,
                "role_reason": p.role_reason,
                "overall_score": overall_score_for(str(p.user_id)) if p.user_id else 0,
            }
            for p in all_participations_sorted
        ]
    
    @staticmethod
    def join_debate_by_code(
        db: Session,
        student_id: str,
        invitation_code: str
    ) -> Dict[str, Any]:
        """
        通过邀请码加入辩论
        
        Args:
            db: 数据库会话
            student_id: 学生ID
            invitation_code: 邀请码
            
        Returns:
            辩论信息
            
        Raises:
            ValueError: 如果邀请码无效或已满员
        """
        # 查找辩论
        debate = db.query(Debate).filter(
            Debate.invitation_code == invitation_code,
            Debate.status.in_(["published", "draft"])
        ).first()

        if not debate:
            raise ValueError("邀请码无效或辩论未发布")

        mode = DebateService._room_mode(debate)
        if mode != "teacher_assigned":
            raise ValueError("该邀请码不属于教师发布的辩论")

        # 检查是否已参与
        existing = db.query(DebateParticipation).filter(
            DebateParticipation.debate_id == debate.id,
            DebateParticipation.user_id == uuid.UUID(student_id),
            DebateParticipation.left_at.is_(None),
        ).first()

        if existing:
            return {
                "id": str(debate.id),
                "topic": debate.topic,
                "description": debate.description,
                "duration": debate.duration,
                "status": debate.status,
                "mode": mode,
                "room_source": DebateService._room_source_value(mode),
                "invitation_code": debate.invitation_code,
                "role": existing.role,
                "role_reason": existing.role_reason,
                "is_joined": True,
                "message": "验证成功，进入辩论"
            }

        # 如果未参与，提示不在邀请名单中
        # 根据需求：老师创建房间并指定学生，学生只能验证进入，不能动态加入
        raise ValueError("您不在该辩论的邀请名单中")
