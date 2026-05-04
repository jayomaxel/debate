"""
辩论房间管理器
负责管理辩论房间的创建、状态同步、成员管理
"""

from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select

from models.debate import Debate, DebateParticipation, DebateReservationInvitation
from models.user import User
from utils.websocket_manager import websocket_manager
from logging_config import get_logger

logger = get_logger(__name__)

TEACHER_MODERATOR_ROLE = "teacher_moderator"
ROOM_META_KEY = "__room_meta"
ROOM_ROLE_ORDER = ("debater_1", "debater_2", "debater_3", "debater_4")
WAITING_CHECKLIST_ITEM_COUNT = 4
WAITING_CHECKLIST_META_KEY = "waiting_checklists"


class DebatePhase(str, Enum):
    """辩论环节"""

    WAITING = "waiting"  # 等待开始
    OPENING = "opening"  # 立论阶段
    QUESTIONING = "questioning"  # 盘问阶段
    FREE_DEBATE = "free_debate"  # 自由辩论
    CLOSING = "closing"  # 总结陈词
    FINISHED = "finished"  # 已结束


class RoomState:
    """房间状态"""

    def __init__(
        self,
        room_id: str,
        debate_id: str,
        current_phase: DebatePhase = DebatePhase.WAITING,
        phase_start_time: Optional[datetime] = None,
        time_remaining: int = 0,
        current_speaker: Optional[str] = None,
        segment_index: int = 0,
        segment_id: Optional[str] = None,
        segment_title: Optional[str] = None,
        segment_start_time: Optional[datetime] = None,
        segment_time_remaining: int = 0,
        speaker_mode: Optional[str] = None,
        speaker_options: Optional[List[str]] = None,
        mic_owner_user_id: Optional[str] = None,
        mic_owner_role: Optional[str] = None,
        mic_expires_at: Optional[datetime] = None,
        free_debate_next_side: Optional[str] = None,
        free_debate_last_side: Optional[str] = None,
        turn_processing_status: str = "idle",
        turn_processing_kind: Optional[str] = None,
        turn_processing_error: Optional[str] = None,
        turn_speech_committed: bool = False,
        turn_speech_user_id: Optional[str] = None,
        turn_speech_role: Optional[str] = None,
        turn_speech_timestamp: Optional[datetime] = None,
        pending_advance_reason: Optional[str] = None,
        ai_turn_status: str = "idle",
        ai_turn_segment_id: Optional[str] = None,
        ai_turn_segment_title: Optional[str] = None,
        ai_turn_speaker_role: Optional[str] = None,
        playback_gate_status: str = "idle",
        playback_gate_speech_id: Optional[str] = None,
        playback_gate_segment_id: Optional[str] = None,
        playback_gate_speaker_role: Optional[str] = None,
        playback_gate_controller_user_id: Optional[str] = None,
        playback_gate_started_at: Optional[datetime] = None,
        playback_gate_deadline_at: Optional[datetime] = None,
        pending_post_playback_action: Optional[str] = None,
        room_capacity: int = 4,
        required_roles: Optional[List[str]] = None,
        waiting_checklists: Optional[Dict[str, dict]] = None,
        room_mode: str = "teacher_assigned",
        visibility: str = "public",
        host_user_id: Optional[str] = None,
        host_role: Optional[str] = None,
        scheduled_start_time: Optional[str] = None,
        checkin_open_time: Optional[str] = None,
        checkin_close_time: Optional[str] = None,
        room_status: str = "waiting",
        moderator_missing: bool = False,
        flow_segments: Optional[List[dict]] = None,
        participants: Optional[List[dict]] = None,
        ai_debaters: Optional[List[dict]] = None,
    ):
        self.room_id = room_id
        self.debate_id = debate_id
        self.current_phase = current_phase
        self.phase_start_time = phase_start_time
        self.time_remaining = time_remaining
        self.current_speaker = current_speaker
        self.segment_index = segment_index
        self.segment_id = segment_id
        self.segment_title = segment_title
        self.segment_start_time = segment_start_time
        self.segment_time_remaining = segment_time_remaining
        self.speaker_mode = speaker_mode
        self.speaker_options = speaker_options or []
        self.mic_owner_user_id = mic_owner_user_id
        self.mic_owner_role = mic_owner_role
        self.mic_expires_at = mic_expires_at
        self.free_debate_next_side = free_debate_next_side or "human"
        self.free_debate_last_side = free_debate_last_side
        self.turn_processing_status = turn_processing_status
        self.turn_processing_kind = turn_processing_kind
        self.turn_processing_error = turn_processing_error
        self.turn_speech_committed = turn_speech_committed
        self.turn_speech_user_id = turn_speech_user_id
        self.turn_speech_role = turn_speech_role
        self.turn_speech_timestamp = turn_speech_timestamp
        self.pending_advance_reason = pending_advance_reason
        self.ai_turn_status = ai_turn_status
        self.ai_turn_segment_id = ai_turn_segment_id
        self.ai_turn_segment_title = ai_turn_segment_title
        self.ai_turn_speaker_role = ai_turn_speaker_role
        self.playback_gate_status = playback_gate_status
        self.playback_gate_speech_id = playback_gate_speech_id
        self.playback_gate_segment_id = playback_gate_segment_id
        self.playback_gate_speaker_role = playback_gate_speaker_role
        self.playback_gate_controller_user_id = playback_gate_controller_user_id
        self.playback_gate_started_at = playback_gate_started_at
        self.playback_gate_deadline_at = playback_gate_deadline_at
        self.pending_post_playback_action = pending_post_playback_action
        self.room_capacity = room_capacity
        self.required_roles = required_roles or list(
            ROOM_ROLE_ORDER[: max(1, min(len(ROOM_ROLE_ORDER), int(room_capacity or 4)))]
        )
        self.waiting_checklists = waiting_checklists or {}
        self.room_mode = room_mode
        self.visibility = visibility
        self.host_user_id = host_user_id
        self.host_role = host_role
        self.scheduled_start_time = scheduled_start_time
        self.checkin_open_time = checkin_open_time
        self.checkin_close_time = checkin_close_time
        self.room_status = room_status
        self.moderator_missing = moderator_missing
        self.flow_segments = flow_segments or []
        self.participants = participants or []
        self.ai_debaters = ai_debaters or [
            {
                "id": "ai_1",
                "role": "debater_1",
                "stance": "negative",
                "name": "AI辩手1",
            },
            {
                "id": "ai_2",
                "role": "debater_2",
                "stance": "negative",
                "name": "AI辩手2",
            },
            {
                "id": "ai_3",
                "role": "debater_3",
                "stance": "negative",
                "name": "AI辩手3",
            },
            {
                "id": "ai_4",
                "role": "debater_4",
                "stance": "negative",
                "name": "AI辩手4",
            },
        ]

    @staticmethod
    def normalize_role(role: object | None) -> Optional[str]:
        value = str(role or "").strip()
        if not value:
            return None
        for candidate in ROOM_ROLE_ORDER:
            if value == candidate or value.endswith(f".{candidate}"):
                return candidate
        return None

    @staticmethod
    def normalize_checklist_items(items: object | None) -> List[bool]:
        raw_items = list(items) if isinstance(items, (list, tuple)) else []
        normalized = [bool(item) for item in raw_items[:WAITING_CHECKLIST_ITEM_COUNT]]
        if len(normalized) < WAITING_CHECKLIST_ITEM_COUNT:
            normalized.extend(
                [False] * (WAITING_CHECKLIST_ITEM_COUNT - len(normalized))
            )
        return normalized

    def get_required_roles(self) -> List[str]:
        roles: List[str] = []
        for role in self.required_roles or []:
            normalized = self.normalize_role(role)
            if normalized and normalized not in roles:
                roles.append(normalized)
        if roles:
            return roles

        try:
            room_capacity = int(self.room_capacity or len(ROOM_ROLE_ORDER))
        except Exception:
            room_capacity = len(ROOM_ROLE_ORDER)
        room_capacity = max(1, min(len(ROOM_ROLE_ORDER), room_capacity))
        return list(ROOM_ROLE_ORDER[:room_capacity])

    def get_waiting_participants_by_role(self) -> Dict[str, dict]:
        participants_by_role: Dict[str, dict] = {}
        required_roles = set(self.get_required_roles())

        for participant in self.participants or []:
            role = self.normalize_role(participant.get("role"))
            if not role or role not in required_roles:
                continue
            if participant.get("user_type") == "teacher":
                continue
            if participant.get("can_speak") is False:
                continue
            participants_by_role[role] = participant

        return participants_by_role

    def serialize_waiting_checklists(self) -> Dict[str, dict]:
        serialized: Dict[str, dict] = {}
        participant_by_user_id = {
            str(participant.get("user_id")): participant
            for participant in self.participants or []
            if participant.get("user_id")
        }
        required_roles = set(self.get_required_roles())

        for raw_user_id, raw_entry in (self.waiting_checklists or {}).items():
            user_id = str(raw_user_id or "").strip()
            if not user_id:
                continue

            entry = raw_entry if isinstance(raw_entry, dict) else {"items": raw_entry}
            participant = participant_by_user_id.get(user_id)
            role = self.normalize_role(
                (participant or {}).get("role") or entry.get("role")
            )
            if role and role not in required_roles:
                continue

            items = self.normalize_checklist_items(entry.get("items"))
            serialized[user_id] = {
                "items": items,
                "ready": all(items),
                "completed_count": sum(1 for item in items if item),
                "updated_at": entry.get("updated_at"),
                "role": role,
                "name": (participant or {}).get("name") or entry.get("name"),
                "online": bool(participant),
            }

        for role, participant in self.get_waiting_participants_by_role().items():
            user_id = str(participant.get("user_id") or "").strip()
            if not user_id:
                continue
            existing = serialized.get(user_id) or {
                "items": [False] * WAITING_CHECKLIST_ITEM_COUNT,
                "ready": False,
                "completed_count": 0,
                "updated_at": None,
            }
            existing["role"] = role
            existing["name"] = participant.get("name")
            existing["online"] = True
            serialized[user_id] = existing

        return serialized

    def get_waiting_status(self) -> dict:
        required_roles = self.get_required_roles()
        participants_by_role = self.get_waiting_participants_by_role()
        waiting_checklists = self.serialize_waiting_checklists()

        online_roles: List[str] = []
        ready_roles: List[str] = []
        online_user_ids: List[str] = []
        ready_user_ids: List[str] = []

        for role in required_roles:
            participant = participants_by_role.get(role)
            if not participant:
                continue
            user_id = str(participant.get("user_id") or "").strip()
            if not user_id:
                continue
            online_roles.append(role)
            online_user_ids.append(user_id)
            if waiting_checklists.get(user_id, {}).get("ready") is True:
                ready_roles.append(role)
                ready_user_ids.append(user_id)

        missing_roles = [role for role in required_roles if role not in online_roles]
        all_online = len(online_roles) == len(required_roles) and not missing_roles
        ready_to_start = all_online and len(ready_roles) == len(required_roles)

        return {
            "required_roles": required_roles,
            "required_count": len(required_roles),
            "online_count": len(online_roles),
            "ready_count": len(ready_roles),
            "online_roles": online_roles,
            "ready_roles": ready_roles,
            "online_user_ids": online_user_ids,
            "ready_user_ids": ready_user_ids,
            "missing_roles": missing_roles,
            "all_online": all_online,
            "all_ready": ready_to_start,
            "ready_to_start": ready_to_start,
        }

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "room_id": self.room_id,
            "debate_id": self.debate_id,
            "current_phase": self.current_phase,
            "phase_start_time": (
                self.phase_start_time.isoformat() if self.phase_start_time else None
            ),
            "time_remaining": self.time_remaining,
            "current_speaker": self.current_speaker,
            "segment_index": self.segment_index,
            "segment_id": self.segment_id,
            "segment_title": self.segment_title,
            "segment_start_time": (
                self.segment_start_time.isoformat() if self.segment_start_time else None
            ),
            "segment_time_remaining": self.segment_time_remaining,
            "speaker_mode": self.speaker_mode,
            "speaker_options": self.speaker_options,
            "mic_owner_user_id": self.mic_owner_user_id,
            "mic_owner_role": self.mic_owner_role,
            "mic_expires_at": (
                self.mic_expires_at.isoformat() if self.mic_expires_at else None
            ),
            "free_debate_next_side": self.free_debate_next_side,
            "free_debate_last_side": self.free_debate_last_side,
            "turn_processing_status": self.turn_processing_status,
            "turn_processing_kind": self.turn_processing_kind,
            "turn_processing_error": self.turn_processing_error,
            "turn_speech_committed": self.turn_speech_committed,
            "turn_speech_user_id": self.turn_speech_user_id,
            "turn_speech_role": self.turn_speech_role,
            "turn_speech_timestamp": (
                self.turn_speech_timestamp.isoformat()
                if self.turn_speech_timestamp
                else None
            ),
            "pending_advance_reason": self.pending_advance_reason,
            "ai_turn_status": self.ai_turn_status,
            "ai_turn_segment_id": self.ai_turn_segment_id,
            "ai_turn_segment_title": self.ai_turn_segment_title,
            "ai_turn_speaker_role": self.ai_turn_speaker_role,
            "playback_gate_status": self.playback_gate_status,
            "playback_gate_speech_id": self.playback_gate_speech_id,
            "playback_gate_segment_id": self.playback_gate_segment_id,
            "playback_gate_speaker_role": self.playback_gate_speaker_role,
            "playback_gate_controller_user_id": self.playback_gate_controller_user_id,
            "playback_gate_started_at": (
                self.playback_gate_started_at.isoformat()
                if self.playback_gate_started_at
                else None
            ),
            "playback_gate_deadline_at": (
                self.playback_gate_deadline_at.isoformat()
                if self.playback_gate_deadline_at
                else None
            ),
            "pending_post_playback_action": self.pending_post_playback_action,
            "room_mode": self.room_mode,
            "visibility": self.visibility,
            "host_user_id": self.host_user_id,
            "host_role": self.host_role,
            "scheduled_start_time": self.scheduled_start_time,
            "checkin_open_time": self.checkin_open_time,
            "checkin_close_time": self.checkin_close_time,
            "room_status": self.room_status,
            "room_capacity": self.room_capacity,
            "required_roles": self.get_required_roles(),
            "waiting_checklists": self.serialize_waiting_checklists(),
            "waiting_status": self.get_waiting_status(),
            "moderator_missing": self.moderator_missing,
            "flow_segments": self.flow_segments,
            "participants": self.participants,
            "ai_debaters": self.ai_debaters,
        }


class DebateRoomManager:
    """辩论房间管理器"""

    def __init__(self):
        # 存储房间状态: {room_id: RoomState}
        self.rooms: Dict[str, RoomState] = {}

    @staticmethod
    def get_room_meta(debate: Debate) -> dict:
        report = debate.report if isinstance(debate.report, dict) else {}
        meta = report.get(ROOM_META_KEY)
        return dict(meta) if isinstance(meta, dict) else {}

    @staticmethod
    def get_room_mode(debate: Debate) -> str:
        meta = DebateRoomManager.get_room_meta(debate)
        return str(getattr(debate, "mode", None) or meta.get("mode") or "teacher_assigned")

    @staticmethod
    def get_room_visibility(debate: Debate) -> str:
        meta = DebateRoomManager.get_room_meta(debate)
        return str(getattr(debate, "visibility", None) or meta.get("visibility") or "private")

    @staticmethod
    def get_room_capacity(debate: Debate, meta: Optional[dict] = None) -> int:
        meta = meta or DebateRoomManager.get_room_meta(debate)
        try:
            value = int(
                getattr(debate, "capacity", None)
                or meta.get("capacity")
                or len(ROOM_ROLE_ORDER)
            )
        except Exception:
            value = len(ROOM_ROLE_ORDER)
        return max(1, min(len(ROOM_ROLE_ORDER), value))

    @staticmethod
    def get_room_host_user_id(debate: Debate) -> Optional[str]:
        meta = DebateRoomManager.get_room_meta(debate)
        host_user_id = getattr(debate, "host_user_id", None) or meta.get("host_user_id") or meta.get("moderator_user_id")
        return str(host_user_id) if host_user_id else None

    @staticmethod
    def get_persisted_waiting_checklists(meta: dict) -> Dict[str, dict]:
        raw_checklists = meta.get(WAITING_CHECKLIST_META_KEY)
        if not isinstance(raw_checklists, dict):
            return {}

        normalized: Dict[str, dict] = {}
        for raw_user_id, raw_entry in raw_checklists.items():
            user_id = str(raw_user_id or "").strip()
            if not user_id:
                continue

            entry = raw_entry if isinstance(raw_entry, dict) else {"items": raw_entry}
            items = RoomState.normalize_checklist_items(entry.get("items"))
            normalized[user_id] = {
                "items": items,
                "ready": all(items),
                "updated_at": entry.get("updated_at"),
                "role": RoomState.normalize_role(entry.get("role")),
                "name": entry.get("name"),
            }

        return normalized

    @staticmethod
    def room_datetime_iso(debate: Debate, field_name: str, meta: dict) -> Optional[str]:
        value = getattr(debate, field_name, None) or meta.get(field_name)
        if not value:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def get_room_status(debate: Debate, meta: dict) -> str:
        reservation_status = str(getattr(debate, "reservation_status", None) or meta.get("reservation_status") or "")
        if reservation_status == "cancelled" or getattr(debate, "cancelled_at", None):
            return "cancelled"
        if str(debate.status) == "completed":
            return "finished"
        if str(debate.status) == "in_progress":
            return "ongoing"
        return "waiting"

    @staticmethod
    def build_teacher_moderator_participant(user: User) -> dict:
        return {
            "user_id": str(user.id),
            "name": user.name,
            "role": TEACHER_MODERATOR_ROLE,
            "stance": None,
            "user_type": "teacher",
            "can_moderate": True,
            "can_speak": False,
        }

    @staticmethod
    def build_student_participant(
        user: User, participation: DebateParticipation, debate: Optional[Debate] = None
    ) -> dict:
        mode = DebateRoomManager.get_room_mode(debate) if debate else "teacher_assigned"
        can_moderate = bool(getattr(participation, "is_moderator", False))
        if debate and DebateRoomManager.get_room_host_user_id(debate) == str(user.id):
            can_moderate = True
        return {
            "user_id": str(user.id),
            "name": user.name,
            "role": str(participation.role),
            "stance": str(participation.stance),
            "user_type": "student",
            "room_mode": mode,
            "seat_order": participation.seat_order,
            "is_room_owner": bool(participation.is_room_owner),
            "can_moderate": can_moderate,
            "can_speak": True,
        }

    def _sync_waiting_checklists_with_participants(self, room_state: RoomState) -> None:
        required_roles = set(room_state.get_required_roles())
        normalized: Dict[str, dict] = {}

        for raw_user_id, raw_entry in (room_state.waiting_checklists or {}).items():
            user_id = str(raw_user_id or "").strip()
            if not user_id:
                continue

            entry = raw_entry if isinstance(raw_entry, dict) else {"items": raw_entry}
            role = RoomState.normalize_role(entry.get("role"))
            if role and role not in required_roles:
                continue

            items = RoomState.normalize_checklist_items(entry.get("items"))
            normalized[user_id] = {
                "items": items,
                "ready": all(items),
                "updated_at": entry.get("updated_at"),
                "role": role,
                "name": entry.get("name"),
            }

        for participant in room_state.participants or []:
            user_id = str(participant.get("user_id") or "").strip()
            if not user_id:
                continue
            if participant.get("user_type") == "teacher":
                continue
            if participant.get("can_speak") is False:
                continue

            role = RoomState.normalize_role(participant.get("role"))
            if not role or role not in required_roles:
                continue

            existing = normalized.get(user_id) or {}
            items = RoomState.normalize_checklist_items(existing.get("items"))
            normalized[user_id] = {
                "items": items,
                "ready": all(items),
                "updated_at": existing.get("updated_at"),
                "role": role,
                "name": participant.get("name") or existing.get("name"),
            }

        room_state.waiting_checklists = normalized

    def _serialize_waiting_checklists_for_meta(self, room_state: RoomState) -> Dict[str, dict]:
        self._sync_waiting_checklists_with_participants(room_state)

        serialized: Dict[str, dict] = {}
        for user_id, entry in (room_state.waiting_checklists or {}).items():
            serialized[user_id] = {
                "items": RoomState.normalize_checklist_items(entry.get("items")),
                "updated_at": entry.get("updated_at"),
                "role": RoomState.normalize_role(entry.get("role")),
                "name": entry.get("name"),
            }

        return serialized

    def _persist_waiting_checklists(self, room_state: RoomState, db: Optional[Session]) -> None:
        if db is None:
            return

        try:
            debate_uuid = uuid.UUID(str(room_state.debate_id))
        except ValueError:
            return

        try:
            debate = db.execute(
                select(Debate).where(Debate.id == debate_uuid)
            ).scalar_one_or_none()
            if not debate:
                return

            report = dict(debate.report) if isinstance(debate.report, dict) else {}
            meta = self.get_room_meta(debate)
            meta[WAITING_CHECKLIST_META_KEY] = self._serialize_waiting_checklists_for_meta(
                room_state
            )
            report[ROOM_META_KEY] = meta
            debate.report = report
            db.commit()
        except Exception as exc:  # pragma: no cover - realtime best-effort sync
            db.rollback()
            logger.warning("Failed to persist waiting checklist state: %s", exc)

    def get_waiting_online_count(self, room_id: str) -> int:
        room_state = self.get_room_state(room_id)
        if not room_state:
            return 0

        self._sync_waiting_checklists_with_participants(room_state)
        waiting_status = room_state.get_waiting_status()
        try:
            return int(waiting_status.get("online_count") or 0)
        except Exception:
            return 0

    def is_waiting_ready(self, room_id: str) -> bool:
        room_state = self.get_room_state(room_id)
        if not room_state:
            return False

        self._sync_waiting_checklists_with_participants(room_state)
        return bool(room_state.get_waiting_status().get("ready_to_start"))

    def get_waiting_block_reason(self, room_id: str) -> Optional[str]:
        room_state = self.get_room_state(room_id)
        if not room_state:
            return "Waiting room not found."

        if room_state.current_phase != DebatePhase.WAITING:
            return "Debate has already started."

        self._sync_waiting_checklists_with_participants(room_state)
        waiting_status = room_state.get_waiting_status()
        required_count = int(waiting_status.get("required_count") or 0)
        online_count = int(waiting_status.get("online_count") or 0)
        ready_count = int(waiting_status.get("ready_count") or 0)

        if not waiting_status.get("all_online"):
            return (
                f"Waiting for all participants to enter the room "
                f"({online_count}/{required_count})."
            )

        if not waiting_status.get("ready_to_start"):
            return (
                f"Waiting for all participants to finish preparation "
                f"({ready_count}/{required_count})."
            )

        return None

    async def maybe_start_debate(self, room_id: str, db: Session) -> bool:
        room_state = self.get_room_state(room_id)
        if not room_state or room_state.current_phase != DebatePhase.WAITING:
            return False
        if not self.is_waiting_ready(room_id):
            return False
        return await self.start_debate(room_id, db)

    async def update_waiting_checklist(
        self,
        room_id: str,
        user_id: str,
        items: object,
        db: Session,
    ) -> bool:
        room_state = self.get_room_state(room_id)
        if not room_state:
            return False

        participant = next(
            (
                p
                for p in room_state.participants
                if str(p.get("user_id") or "").strip() == str(user_id)
            ),
            None,
        )
        if not participant:
            return False
        if participant.get("user_type") == "teacher":
            return False
        if participant.get("can_speak") is False:
            return False

        role = RoomState.normalize_role(participant.get("role"))
        if role not in set(room_state.get_required_roles()):
            return False

        normalized_items = RoomState.normalize_checklist_items(items)
        existing = (room_state.waiting_checklists or {}).get(str(user_id), {})
        room_state.waiting_checklists[str(user_id)] = {
            "items": normalized_items,
            "ready": all(normalized_items),
            "updated_at": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
            "role": role or existing.get("role"),
            "name": participant.get("name") or existing.get("name"),
        }

        self._sync_waiting_checklists_with_participants(room_state)
        self._persist_waiting_checklists(room_state, db)
        await self.broadcast_state_update(room_id)
        await self.maybe_start_debate(room_id, db)
        return True

    async def create_room(self, room_id: str, debate_id: str, db: Session) -> RoomState:
        """
        创建辩论房间

        Args:
            room_id: 房间ID
            debate_id: 辩论ID
            db: 数据库会话

        Returns:
            房间状态
        """
        try:
            debate_uuid = uuid.UUID(str(debate_id))
        except ValueError as e:
            raise ValueError(f"Invalid debate id: {debate_id}") from e

        # 检查辩论是否存在
        debate = db.execute(
            select(Debate).where(Debate.id == debate_uuid)
        ).scalar_one_or_none()

        if not debate:
            raise ValueError(f"Debate {debate_id} not found")

        # 创建房间状态
        meta = self.get_room_meta(debate)
        room_capacity = self.get_room_capacity(debate, meta)
        room_state = RoomState(
            room_id=room_id,
            debate_id=str(debate_uuid),
            current_phase=DebatePhase.WAITING,
            room_capacity=room_capacity,
            required_roles=list(ROOM_ROLE_ORDER[:room_capacity]),
            waiting_checklists=self.get_persisted_waiting_checklists(meta),
            room_mode=self.get_room_mode(debate),
            visibility=self.get_room_visibility(debate),
            host_user_id=self.get_room_host_user_id(debate),
            host_role=meta.get("host_role"),
            scheduled_start_time=self.room_datetime_iso(debate, "scheduled_start_time", meta),
            checkin_open_time=self.room_datetime_iso(debate, "checkin_open_time", meta),
            checkin_close_time=self.room_datetime_iso(debate, "checkin_close_time", meta),
            room_status=self.get_room_status(debate, meta),
        )

        self._sync_waiting_checklists_with_participants(room_state)
        self.rooms[room_id] = room_state

        logger.info(f"Created room {room_id} for debate {debate_id}")

        return room_state

    async def join_room(self, room_id: str, user_id: str, db: Session) -> bool:
        """
        加入辩论房间

        Args:
            room_id: 房间ID
            user_id: 用户ID
            db: 数据库会话

        Returns:
            是否成功加入
        """
        if room_id not in self.rooms:
            logger.error(f"Room {room_id} not found")
            return False

        room_state = self.rooms[room_id]

        try:
            user_uuid = uuid.UUID(str(user_id))
            debate_uuid = uuid.UUID(str(room_state.debate_id))
        except ValueError:
            logger.error(
                f"Invalid UUID: user_id={user_id} debate_id={room_state.debate_id}"
            )
            return False

        # 获取用户信息
        user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()

        if not user:
            logger.error(f"User {user_id} not found")
            return False

        # 获取参与信息
        debate = db.execute(
            select(Debate).where(Debate.id == debate_uuid)
        ).scalar_one_or_none()
        if not debate:
            logger.error(f"Debate {room_state.debate_id} not found")
            return False

        participation = db.execute(
            select(DebateParticipation).where(
                DebateParticipation.debate_id == debate_uuid,
                DebateParticipation.user_id == user_uuid,
                DebateParticipation.left_at.is_(None),
            )
        ).scalar_one_or_none()

        is_teacher_moderator = (
            str(getattr(debate, "teacher_id", "")) == str(user_uuid)
            and str(getattr(user, "user_type", "")) in {"teacher", "administrator"}
        )
        mode = self.get_room_mode(debate)
        if mode == "teacher_reserved" and not is_teacher_moderator:
            invitation = db.execute(
                select(DebateReservationInvitation).where(
                    DebateReservationInvitation.debate_id == debate_uuid,
                    DebateReservationInvitation.student_id == user_uuid,
                    DebateReservationInvitation.revoked_at.is_(None),
                )
            ).scalar_one_or_none()
            if (
                self.get_room_status(debate, self.get_room_meta(debate)) == "cancelled"
                or not invitation
                or str(invitation.response_status) != "accepted"
                or str(invitation.attendance_status) != "checked_in"
                or not participation
            ):
                logger.error(
                    "User %s failed reservation room guard for debate %s",
                    user_id,
                    room_state.debate_id,
                )
                return False
        elif mode == "student_lobby":
            if str(debate.status) == "completed" or self.get_room_status(debate, self.get_room_meta(debate)) == "cancelled":
                return False
            if not participation and not is_teacher_moderator:
                logger.error(
                    f"User {user_id} is not an active lobby participant of debate {room_state.debate_id}"
                )
                return False

        if not participation and not is_teacher_moderator:
            logger.error(
                f"User {user_id} is not a participant of debate {room_state.debate_id}"
            )
            return False

        # 检查用户是否已在房间
        if any(p["user_id"] == user_id for p in room_state.participants):
            logger.info(f"User {user_id} already in room {room_id}")
            self._sync_waiting_checklists_with_participants(room_state)
            # 即使已在房间，也发送当前状态
            await websocket_manager.send_to_user(
                user_id, {"type": "state_update", "data": room_state.to_dict()}
            )
            return True

        # 添加参与者
        participant_info = (
            self.build_teacher_moderator_participant(user)
            if is_teacher_moderator
            else self.build_student_participant(user, participation, debate)
        )
        room_state.participants.append(participant_info)
        if participant_info.get("can_moderate"):
            room_state.host_user_id = str(participant_info.get("user_id"))
            room_state.host_role = str(participant_info.get("role"))
            room_state.moderator_missing = False
        self._sync_waiting_checklists_with_participants(room_state)
        self._persist_waiting_checklists(room_state, db)

        logger.info(f"User {user_id} joined room {room_id}")

        # 1. 先向新用户发送当前房间状态（包括所有在线参与者）
        await websocket_manager.send_to_user(
            user_id, {"type": "state_update", "data": room_state.to_dict()}
        )

        # 2. 然后向其他用户广播user_joined事件（包含完整用户信息）
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "user_joined",
                "data": {
                    **participant_info,
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
            exclude_user=user_id,
        )

        # 3. 广播房间状态更新给所有人
        await self.broadcast_state_update(room_id)
        await self.maybe_start_debate(room_id, db)

        return True

    async def transfer_moderator_if_needed(
        self,
        room_id: str,
        departed_participant: Optional[dict],
        db: Optional[Session] = None,
    ) -> None:
        if room_id not in self.rooms or not departed_participant:
            return
        room_state = self.rooms[room_id]
        if not departed_participant.get("can_moderate") or departed_participant.get("user_type") != "student":
            return
        if room_state.room_mode != "student_lobby":
            return

        role_rank = {"debater_2": 0, "debater_3": 1, "debater_4": 2, "debater_1": 3}
        candidates = [
            participant
            for participant in room_state.participants
            if participant.get("user_type") == "student" and participant.get("can_speak")
        ]
        candidates.sort(key=lambda participant: role_rank.get(str(participant.get("role")), 99))
        if not candidates:
            room_state.host_user_id = None
            room_state.host_role = None
            room_state.moderator_missing = True
            self._sync_lobby_moderator_to_db(room_state, None, db)
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "moderator_missing",
                    "data": {
                        "room_id": room_id,
                        "old_moderator_user_id": departed_participant.get("user_id"),
                        "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                    },
                },
            )
            return

        next_moderator = candidates[0]
        for participant in room_state.participants:
            participant["can_moderate"] = participant.get("user_id") == next_moderator.get("user_id")
        room_state.host_user_id = str(next_moderator.get("user_id"))
        room_state.host_role = str(next_moderator.get("role"))
        room_state.moderator_missing = False
        self._sync_lobby_moderator_to_db(room_state, str(next_moderator.get("user_id")), db)
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "moderator_transferred",
                "data": {
                    "room_id": room_id,
                    "old_moderator_user_id": departed_participant.get("user_id"),
                    "new_moderator_user_id": next_moderator.get("user_id"),
                    "new_moderator_role": next_moderator.get("role"),
                    "reason": "moderator_left",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )

    @staticmethod
    def _sync_lobby_moderator_to_db(
        room_state: RoomState,
        moderator_user_id: Optional[str],
        db: Optional[Session],
    ) -> None:
        if db is None or room_state.room_mode != "student_lobby":
            return
        try:
            debate_uuid = uuid.UUID(str(room_state.debate_id))
            moderator_uuid = uuid.UUID(str(moderator_user_id)) if moderator_user_id else None
        except ValueError:
            return
        try:
            debate = db.execute(select(Debate).where(Debate.id == debate_uuid)).scalar_one_or_none()
            if debate:
                debate.host_user_id = moderator_uuid
            participations = db.execute(
                select(DebateParticipation).where(
                    DebateParticipation.debate_id == debate_uuid,
                    DebateParticipation.left_at.is_(None),
                )
            ).scalars().all()
            for participation in participations:
                participation.is_moderator = bool(
                    moderator_uuid and participation.user_id == moderator_uuid
                )
            db.commit()
        except Exception as exc:  # pragma: no cover - realtime best-effort sync
            db.rollback()
            logger.warning("Failed to sync lobby moderator to database: %s", exc)

    async def leave_room(self, room_id: str, user_id: str, db: Optional[Session] = None) -> bool:
        """
        离开辩论房间

        Args:
            room_id: 房间ID
            user_id: 用户ID

        Returns:
            是否成功离开
        """
        if room_id not in self.rooms:
            return False

        room_state = self.rooms[room_id]

        departed_participant = next(
            (p for p in room_state.participants if p["user_id"] == user_id),
            None,
        )

        # 移除参与者
        room_state.participants = [
            p for p in room_state.participants if p["user_id"] != user_id
        ]
        self._sync_waiting_checklists_with_participants(room_state)
        self._persist_waiting_checklists(room_state, db)

        logger.info(f"User {user_id} left room {room_id}")

        await self.transfer_moderator_if_needed(room_id, departed_participant, db)

        # 广播房间状态更新
        await self.broadcast_state_update(room_id)

        # 如果房间为空，删除房间
        if not room_state.participants:
            del self.rooms[room_id]
            logger.info(f"Room {room_id} deleted (empty)")

        return True

    def get_online_participants(self, room_id: str) -> List[dict]:
        """
        获取房间内在线参与者列表

        Args:
            room_id: 房间ID

        Returns:
            在线参与者列表，包含完整的用户信息
        """
        if room_id not in self.rooms:
            return []

        room_state = self.rooms[room_id]

        # 返回当前房间内所有在线参与者
        # 这些参与者已经在join_room时添加到participants列表中
        return room_state.participants.copy()

    def get_room_state(self, room_id: str) -> Optional[RoomState]:
        """
        获取房间状态

        Args:
            room_id: 房间ID

        Returns:
            房间状态，如果房间不存在则返回None
        """
        return self.rooms.get(room_id)

    async def update_room_state(self, room_id: str, **kwargs) -> bool:
        """
        更新房间状态

        Args:
            room_id: 房间ID
            **kwargs: 要更新的状态字段

        Returns:
            是否更新成功
        """
        if room_id not in self.rooms:
            return False

        room_state = self.rooms[room_id]

        # 更新状态
        for key, value in kwargs.items():
            if hasattr(room_state, key):
                setattr(room_state, key, value)

        # 广播状态更新
        await self.broadcast_state_update(room_id)

        return True

    async def start_debate(self, room_id: str, db: Session) -> bool:
        """
        开始辩论

        Args:
            room_id: 房间ID
            db: 数据库会话

        Returns:
            是否成功开始
        """
        if room_id not in self.rooms:
            return False

        room_state = self.rooms[room_id]

        try:
            debate_uuid = uuid.UUID(str(room_state.debate_id))
        except ValueError:
            logger.error(f"Invalid debate UUID: {room_state.debate_id}")
            return False
        if room_state.current_phase != DebatePhase.WAITING:
            return False
        self._sync_waiting_checklists_with_participants(room_state)
        if not self.is_waiting_ready(room_id):
            logger.info(
                "Debate in room %s cannot start yet: %s",
                room_id,
                self.get_waiting_block_reason(room_id),
            )
            return False

        # 更新辩论状态
        debate = db.execute(
            select(Debate).where(Debate.id == debate_uuid)
        ).scalar_one_or_none()

        if debate:
            debate.status = "in_progress"
            if self.get_room_mode(debate) == "teacher_reserved":
                debate.reservation_status = "in_progress"
            debate.start_time = (datetime.utcnow() + timedelta(hours=8))
            db.commit()

        # 更新房间状态
        room_state.current_phase = DebatePhase.OPENING
        room_state.phase_start_time = (datetime.utcnow() + timedelta(hours=8))
        room_state.time_remaining = 0
        room_state.current_speaker = None
        room_state.segment_index = 0
        room_state.segment_id = None
        room_state.segment_title = None
        room_state.segment_start_time = None
        room_state.segment_time_remaining = 0
        room_state.speaker_mode = None
        room_state.speaker_options = []
        room_state.room_status = "ongoing"
        room_state.ai_turn_status = "idle"
        room_state.ai_turn_segment_id = None
        room_state.ai_turn_segment_title = None
        room_state.ai_turn_speaker_role = None

        logger.info(f"Debate started in room {room_id}")

        # 初始化流程控制器（避免循环导入，在这里动态导入）
        from services.flow_controller import flow_controller

        await flow_controller.start_flow(room_id)

        # 广播辩论开始
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "debate_started",
                "data": {
                    "room_id": room_id,
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )

        # 广播状态更新
        await self.broadcast_state_update(room_id)

        return True

    async def end_debate(self, room_id: str, db: Session) -> bool:
        """
        结束辩论

        Args:
            room_id: 房间ID
            db: 数据库会话

        Returns:
            是否成功结束
        """
        if room_id not in self.rooms:
            return False

        room_state = self.rooms[room_id]

        # 更新辩论状态
        debate = None
        try:
            debate_uuid = uuid.UUID(str(room_state.debate_id))
        except ValueError:
            debate_uuid = None
        if debate_uuid:
            debate = db.execute(
                select(Debate).where(Debate.id == debate_uuid)
            ).scalar_one_or_none()

        if (
            room_state.current_phase == DebatePhase.FINISHED
            and (not debate or str(getattr(debate, "status", "") or "") == "completed")
        ):
            logger.info(f"Debate already ended in room {room_id}; skipping duplicate end flow")
            return True

        if debate:
            debate.status = "completed"
            if self.get_room_mode(debate) == "teacher_reserved":
                debate.reservation_status = "completed"
            debate.end_time = (datetime.utcnow() + timedelta(hours=8))
            db.commit()

        # 更新房间状态
        room_state.current_phase = DebatePhase.FINISHED
        room_state.current_speaker = None
        room_state.time_remaining = 0
        room_state.segment_time_remaining = 0
        room_state.speaker_mode = None
        room_state.speaker_options = []
        room_state.room_status = "finished"
        room_state.segment_id = None
        room_state.segment_title = None
        room_state.segment_start_time = None
        room_state.mic_owner_user_id = None
        room_state.mic_owner_role = None
        room_state.mic_expires_at = None
        room_state.turn_processing_status = "idle"
        room_state.turn_processing_kind = None
        room_state.turn_processing_error = None
        room_state.turn_speech_committed = False
        room_state.turn_speech_user_id = None
        room_state.turn_speech_role = None
        room_state.turn_speech_timestamp = None
        room_state.pending_advance_reason = None
        room_state.ai_turn_status = "idle"
        room_state.ai_turn_segment_id = None
        room_state.ai_turn_segment_title = None
        room_state.ai_turn_speaker_role = None
        room_state.playback_gate_status = "idle"
        room_state.playback_gate_speech_id = None
        room_state.playback_gate_segment_id = None
        room_state.playback_gate_speaker_role = None
        room_state.playback_gate_controller_user_id = None
        room_state.playback_gate_started_at = None
        room_state.playback_gate_deadline_at = None
        room_state.pending_post_playback_action = None

        logger.info(f"Debate ended in room {room_id}")

        try:
            from services.flow_controller import flow_controller

            await flow_controller.cleanup_room(room_id)
        except Exception:
            logger.exception(f"Failed to cleanup flow controller for room {room_id}")

        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "phase_change",
                "data": {
                    "phase": DebatePhase.FINISHED,
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )

        await self.broadcast_state_update(room_id)

        # 广播评分处理中
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "debate_processing",
                "data": {
                    "room_id": room_id,
                    "message": "正在生成辩论报告和评分...",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )

        if debate_uuid:
            asyncio.create_task(
                self._auto_score_and_generate_report_background(room_id, debate_uuid)
            )
        else:
            await self._broadcast_debate_ended(room_id)

        return True

    async def _broadcast_debate_ended(self, room_id: str) -> None:
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "debate_ended",
                "data": {
                    "room_id": room_id,
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )

    async def _auto_score_and_generate_report_background(
        self,
        room_id: str,
        debate_id: uuid.UUID,
    ) -> None:
        import database as db_module

        db = None
        try:
            if db_module.SessionLocal is None:
                db_module.init_engine()
            db = db_module.SessionLocal()
            await self._auto_score_and_generate_report(db, debate_id)
        except Exception as e:
            logger.error(f"自动评分和报告生成失败: {e}", exc_info=True)
        finally:
            if db is not None:
                db.close()
            await self._broadcast_debate_ended(room_id)

    async def _auto_score_and_generate_report(self, db: Session, debate_id: uuid.UUID) -> None:
        """
        自动评分和报告生成（后台任务）

        Args:
            db: 数据库会话
            debate_id: 辩论ID
        """
        from models.speech import Speech
        from services.scoring_service import ScoringService
        # from services.config_service import ConfigService
        # from utils.email_service import EmailService
        from models.debate import Debate, DebateParticipation
        from models.user import User

        logger.info(f"开始自动评分和报告生成: debate_id={debate_id}")

        try:
            # 获取所有可用于评分的发言（包括AI和人类）。
            # ASR 失败/空转写会保留 speech 供回放排查，但不能进入评分和报告上下文。
            speeches = db.execute(
                select(Speech)
                .where(Speech.debate_id == debate_id)
                .where(Speech.is_valid_for_scoring.is_(True))
                .order_by(Speech.timestamp)
            ).scalars().all()
            speeches = [
                speech
                for speech in speeches
                if str(getattr(speech, "content", "") or "").strip()
            ]

            logger.info(f"找到 {len(speeches)} 条发言需要评分")

            # 构建上下文
            context = []
            for speech in speeches:
                context.append({
                    "speech_id": str(speech.id),
                    "speaker_role": speech.speaker_role,
                    "speaker_type": speech.speaker_type,
                    "phase": speech.phase,
                    "content": speech.content,
                    "timestamp": speech.timestamp.isoformat()
                })

            # 批量评分
            logger.info("开始进行批量辩论评分...")
            report_data = await ScoringService.batch_score_debate(
                db=db,
                debate_id=str(debate_id),
                speeches=speeches,
                context=context
            )
            
            # 保存报告到数据库，保留房间/预约元数据。
            debate = db.execute(select(Debate).where(Debate.id == debate_id)).scalar_one()
            existing_report = debate.report if isinstance(debate.report, dict) else {}
            if isinstance(report_data, dict):
                debate.report = {
                    **report_data,
                    ROOM_META_KEY: existing_report.get(ROOM_META_KEY),
                } if existing_report.get(ROOM_META_KEY) else report_data
            else:
                debate.report = report_data
            db.commit()
            
            logger.info(f"批量评分和报告生成完成: {debate_id}")

            # 自动发送邮件逻辑（临时注释关闭）
            # try:
            #     config_service = ConfigService(db)
            #     email_config = await config_service.get_email_config()
            #
            #     if email_config.auto_send_enabled:
            #         logger.info("自动发送邮件功能已开启，开始发送报告邮件...")
            #
            #         participants = db.execute(
            #             select(DebateParticipation).where(DebateParticipation.debate_id == debate_id)
            #         ).scalars().all()
            #
            #         for p in participants:
            #             if not p.user_id:
            #                 continue
            #
            #             user = db.execute(select(User).where(User.id == p.user_id)).scalar_one_or_none()
            #             if user and user.email:
            #                 summary = "您的辩论报告已生成，请登录系统查看详情。"
            #
            #                 await EmailService.send_report_email(
            #                     db=db,
            #                     to_email=user.email,
            #                     student_name=user.name,
            #                     debate_topic=debate.topic,
            #                     report_summary=summary
            #                 )
            # except Exception as e:
            #     logger.error(f"自动发送邮件失败: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"自动评分和报告生成失败: {e}", exc_info=True)
            raise


    async def broadcast_state_update(self, room_id: str) -> None:
        """
        广播房间状态更新

        Args:
            room_id: 房间ID
        """
        if room_id not in self.rooms:
            return

        room_state = self.rooms[room_id]
        self._sync_waiting_checklists_with_participants(room_state)

        await websocket_manager.broadcast_to_room(
            room_id, {"type": "state_update", "data": room_state.to_dict()}
        )


# 创建全局房间管理器实例
room_manager = DebateRoomManager()
