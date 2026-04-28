"""
辩论流程控制器
负责控制辩论环节切换、发言权限管理、倒计时
"""

from typing import Optional, Dict, List, Any, AsyncIterator
from datetime import datetime, timedelta
import asyncio
import hashlib
import json
import time

from services.room_manager import room_manager, DebatePhase
from utils.websocket_manager import websocket_manager
import database as db_module
from sqlalchemy import select
import uuid
from models.debate import Debate
from models.config import CozeConfig
from models.speech import Speech
from agents.debater_agent import AIDebaterAgent
from services.config_service import ConfigService
from utils.voice_processor import voice_processor
from logging_config import get_logger

logger = get_logger(__name__)


class DebateFlowController:
    """辩论流程控制器"""

    CONTEXT_REACTIVE_SEGMENT_IDS = {
        "questioning_2_neg_answer",
        "questioning_3_ai3_ask",
        "questioning_4_neg_answer",
        "questioning_neg_summary",
        "closing_negative_4",
    }

    def __init__(self):
        # 存储定时器任务: {room_id: asyncio.Task}
        self.timer_tasks: Dict[str, asyncio.Task] = {}
        self.segments: Dict[str, List[Dict[str, Any]]] = {}
        self.segment_index: Dict[str, int] = {}
        self.ai_tasks: Dict[str, asyncio.Task] = {}
        # 存储AI草稿: {room_id: {"segment_id:speaker_role": draft}}
        self.ai_drafts: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.ai_draft_tasks: Dict[str, Dict[str, asyncio.Task]] = {}

    def initialize_flow(
        self, room_id: str, segments: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        初始化辩论流程

        Args:
            room_id: 房间ID
            segments: 段落配置（可选）
        """
        self.segments[room_id] = segments or self._build_default_segments()
        self.segment_index[room_id] = 0
        room_state = room_manager.get_room_state(room_id)
        if room_state:
            room_state.flow_segments = self._serialize_segments(self.segments[room_id])

        logger.info(f"Initialized flow for room {room_id}")

    async def start_flow(
        self, room_id: str, segments: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        self.initialize_flow(room_id, segments)
        await self._apply_current_segment(room_id)
        await self.start_timer(room_id)

    def _build_default_segments(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "opening_positive_1",
                "title": "立论阶段：正方一辩",
                "phase": DebatePhase.OPENING,
                "duration": 180,
                "mode": "fixed",
                "speaker_roles": ["debater_1"],
            },
            {
                "id": "opening_negative_1",
                "title": "立论阶段：反方一辩",
                "phase": DebatePhase.OPENING,
                "duration": 180,
                "mode": "fixed",
                "speaker_roles": ["ai_1"],
            },
            {
                "id": "questioning_1_ai2_ask",
                "title": "盘问第1轮：反方二辩提问",
                "phase": DebatePhase.QUESTIONING,
                "duration": 90,
                "mode": "fixed",
                "speaker_roles": ["ai_2"],
            },
            {
                "id": "questioning_1_pos_answer",
                "title": "盘问第1轮：正方回答（二辩或三辩）",
                "phase": DebatePhase.QUESTIONING,
                "duration": 90,
                "mode": "choice",
                "speaker_roles": ["debater_2", "debater_3"],
            },
            {
                "id": "questioning_2_pos2_ask",
                "title": "盘问第2轮：正方二辩提问",
                "phase": DebatePhase.QUESTIONING,
                "duration": 90,
                "mode": "fixed",
                "speaker_roles": ["debater_2"],
            },
            {
                "id": "questioning_2_neg_answer",
                "title": "盘问第2轮：反方回答（二辩或三辩）",
                "phase": DebatePhase.QUESTIONING,
                "duration": 90,
                "mode": "choice",
                "speaker_roles": ["ai_2", "ai_3"],
            },
            {
                "id": "questioning_3_ai3_ask",
                "title": "盘问第3轮：反方三辩提问",
                "phase": DebatePhase.QUESTIONING,
                "duration": 90,
                "mode": "fixed",
                "speaker_roles": ["ai_3"],
            },
            {
                "id": "questioning_3_pos_answer",
                "title": "盘问第3轮：正方回答（一辩或四辩）",
                "phase": DebatePhase.QUESTIONING,
                "duration": 90,
                "mode": "choice",
                "speaker_roles": ["debater_1", "debater_4"],
            },
            {
                "id": "questioning_4_pos3_ask",
                "title": "盘问第4轮：正方三辩提问",
                "phase": DebatePhase.QUESTIONING,
                "duration": 90,
                "mode": "fixed",
                "speaker_roles": ["debater_3"],
            },
            {
                "id": "questioning_4_neg_answer",
                "title": "盘问第4轮：反方回答（一辩或四辩）",
                "phase": DebatePhase.QUESTIONING,
                "duration": 90,
                "mode": "choice",
                "speaker_roles": ["ai_1", "ai_4"],
            },
            {
                "id": "questioning_neg_summary",
                "title": "攻辩小结：反方一辩总结",
                "phase": DebatePhase.QUESTIONING,
                "duration": 90,
                "mode": "fixed",
                "speaker_roles": ["ai_1"],
            },
            {
                "id": "questioning_pos_summary",
                "title": "攻辩小结：正方一辩总结",
                "phase": DebatePhase.QUESTIONING,
                "duration": 90,
                "mode": "fixed",
                "speaker_roles": ["debater_1"],
            },
            {
                "id": "free_debate",
                "title": "自由辩论：抢麦发言（每次≤30秒）",
                "phase": DebatePhase.FREE_DEBATE,
                "duration": 480,
                "mode": "free",
                "speaker_roles": [
                    "debater_1",
                    "debater_2",
                    "debater_3",
                    "debater_4",
                    "ai_1",
                    "ai_2",
                    "ai_3",
                    "ai_4",
                ],
            },
            {
                "id": "closing_negative_4",
                "title": "总结陈词：反方四辩",
                "phase": DebatePhase.CLOSING,
                "duration": 240,
                "mode": "fixed",
                "speaker_roles": ["ai_4"],
            },
            {
                "id": "closing_positive_4",
                "title": "总结陈词：正方四辩",
                "phase": DebatePhase.CLOSING,
                "duration": 240,
                "mode": "fixed",
                "speaker_roles": ["debater_4"],
            },
        ]

    def get_current_phase(self, room_id: str) -> Optional[DebatePhase]:
        """
        获取当前环节

        Args:
            room_id: 房间ID

        Returns:
            当前环节，如果房间不存在则返回None
        """
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return None

        return room_state.current_phase

    def get_segments(self, room_id: str) -> List[Dict[str, Any]]:
        return self.segments.get(room_id) or self._build_default_segments()

    def _serialize_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        serialized = []
        for segment in segments:
            phase = segment.get("phase")
            serialized.append(
                {
                    "id": str(segment.get("id") or ""),
                    "title": str(segment.get("title") or ""),
                    "phase": str(getattr(phase, "value", phase) or ""),
                    "duration": int(segment.get("duration") or 0),
                    "mode": str(segment.get("mode") or ""),
                }
            )
        return serialized

    def _now(self) -> datetime:
        return datetime.utcnow() + timedelta(hours=8)

    def _build_ai_draft_key(self, segment_id: Optional[str], speaker_role: Optional[str]) -> str:
        return f"{str(segment_id or '')}:{str(speaker_role or '')}"

    def _get_ai_draft(
        self,
        room_id: str,
        *,
        segment_id: Optional[str] = None,
        speaker_role: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        room_drafts = self.ai_drafts.get(room_id) or {}
        if segment_id is None or speaker_role is None:
            return None
        return room_drafts.get(self._build_ai_draft_key(segment_id, speaker_role))

    def _store_ai_draft(self, room_id: str, draft: Dict[str, Any]) -> Dict[str, Any]:
        segment_id = str(draft.get("segment_id") or "")
        speaker_role = str(draft.get("speaker_role") or "")
        room_drafts = self.ai_drafts.setdefault(room_id, {})
        room_drafts[self._build_ai_draft_key(segment_id, speaker_role)] = draft
        return draft

    def _clear_ai_draft(
        self,
        room_id: str,
        *,
        segment_id: Optional[str] = None,
        speaker_role: Optional[str] = None,
    ) -> None:
        if segment_id is None or speaker_role is None:
            self.ai_drafts.pop(room_id, None)
            return
        room_drafts = self.ai_drafts.get(room_id)
        if not room_drafts:
            return
        room_drafts.pop(self._build_ai_draft_key(segment_id, speaker_role), None)
        if not room_drafts:
            self.ai_drafts.pop(room_id, None)

    def _get_ai_draft_task(
        self,
        room_id: str,
        *,
        segment_id: Optional[str] = None,
        speaker_role: Optional[str] = None,
    ) -> Optional[asyncio.Task]:
        room_tasks = self.ai_draft_tasks.get(room_id) or {}
        if segment_id is None or speaker_role is None:
            return None
        key = self._build_ai_draft_key(segment_id, speaker_role)
        task = room_tasks.get(key)
        if task and task.done():
            room_tasks.pop(key, None)
            if not room_tasks:
                self.ai_draft_tasks.pop(room_id, None)
            return None
        return task

    def _store_ai_draft_task(
        self,
        room_id: str,
        *,
        segment_id: str,
        speaker_role: str,
        task: asyncio.Task,
    ) -> asyncio.Task:
        room_tasks = self.ai_draft_tasks.setdefault(room_id, {})
        room_tasks[self._build_ai_draft_key(segment_id, speaker_role)] = task
        return task

    def _clear_ai_draft_task(
        self,
        room_id: str,
        *,
        segment_id: Optional[str] = None,
        speaker_role: Optional[str] = None,
    ) -> None:
        if segment_id is None or speaker_role is None:
            self.ai_draft_tasks.pop(room_id, None)
            return
        room_tasks = self.ai_draft_tasks.get(room_id)
        if not room_tasks:
            return
        room_tasks.pop(self._build_ai_draft_key(segment_id, speaker_role), None)
        if not room_tasks:
            self.ai_draft_tasks.pop(room_id, None)

    def _build_empty_ai_draft(
        self,
        *,
        room_id: str,
        segment_id: str,
        segment_title: Optional[str],
        speaker_role: str,
        speech_type: str,
        dependency_scope: str,
    ) -> Dict[str, Any]:
        return {
            "room_id": room_id,
            "segment_id": str(segment_id),
            "segment_title": segment_title,
            "speaker_role": str(speaker_role),
            "speech_type": str(speech_type),
            "dependency_scope": str(dependency_scope),
            "status": "idle",
            "dependency_signature": None,
            "source_speech_ids": [],
            "draft_text": "",
            "voice_id": None,
            "configured_audio_format": None,
            "ready_at": None,
            "release_not_before": None,
            "released_at": None,
            "speech_id": None,
            "error": None,
        }

    def _resolve_segment_speaker_role(
        self, segment: Dict[str, Any], room_state: Optional[Any] = None
    ) -> Optional[str]:
        speaker_roles = list(segment.get("speaker_roles") or [])
        if not speaker_roles:
            return None
        current_segment_id = str(getattr(room_state, "segment_id", "") or "")
        current_speaker = str(getattr(room_state, "current_speaker", "") or "")
        if (
            room_state
            and str(segment.get("id") or "") == current_segment_id
            and current_speaker in speaker_roles
        ):
            return current_speaker or None
        ai_role = next(
            (
                str(role or "").strip()
                for role in speaker_roles
                if str(role or "").strip().startswith("ai_")
            ),
            "",
        )
        if ai_role:
            return ai_role
        speaker_role = str(speaker_roles[0] or "").strip()
        return speaker_role or None

    def _normalize_prethinking_mode(
        self, value: Optional[str], *, default: str = "reactive"
    ) -> str:
        normalized = str(value or default).strip().lower()
        if normalized in {"reactive", "eager"}:
            return normalized
        return default

    def _coerce_nonnegative_float(self, value: Any, default: float) -> float:
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return float(default)

    def _mark_ai_draft_invalidated(
        self, room_id: str, draft: Dict[str, Any], *, reason: str
    ) -> Dict[str, Any]:
        invalidated = dict(draft)
        invalidated["status"] = "invalidated"
        invalidated["error"] = reason
        self._store_ai_draft(room_id, invalidated)
        return invalidated

    def _is_ai_draft_usable(
        self,
        draft: Optional[Dict[str, Any]],
        *,
        turn_plan: Dict[str, Any],
        dependency_signature: str,
    ) -> bool:
        if not draft or draft.get("status") != "ready":
            return False
        if draft.get("dependency_signature") != dependency_signature:
            return False
        if not str(draft.get("draft_text") or "").strip():
            return False
        ttl_sec = self._coerce_nonnegative_float(
            turn_plan.get("draft_ttl_sec"),
            120.0,
        )
        ready_at = draft.get("ready_at")
        if ttl_sec > 0 and isinstance(ready_at, datetime):
            expires_at = ready_at + timedelta(seconds=ttl_sec)
            if expires_at < self._now():
                return False
        return True

    def _build_segment_release_not_before(
        self, room_state: Any, turn_plan: Dict[str, Any]
    ) -> datetime:
        segment_start_time = getattr(room_state, "segment_start_time", None)
        base_time = (
            segment_start_time
            if isinstance(segment_start_time, datetime)
            else self._now()
        )
        return base_time + timedelta(
            seconds=self._coerce_nonnegative_float(
                turn_plan.get("response_delay_sec"),
                0.0,
            )
        )

    def _resolve_recent_speeches_limit(
        self, segment: Dict[str, Any], turn_plan: Dict[str, Any]
    ) -> int:
        segment_id = str(segment.get("id") or "")
        speech_type = str(turn_plan.get("speech_type") or "free_debate")
        if segment_id == "closing_negative_4":
            return 200
        if segment_id == "questioning_neg_summary":
            return 120
        if speech_type in {"question", "response", "rebuttal"}:
            return 60
        return 30

    def _hash_speech_content(self, speech: Speech) -> str:
        normalized = " ".join(
            str(getattr(speech, "content", "") or "").strip().split()
        )
        if not normalized:
            return "empty"
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]

    def _build_speech_signature_token(self, speech: Speech) -> str:
        return ":".join(
            [
                str(getattr(speech, "id", "") or ""),
                str(getattr(speech, "speaker_role", "") or ""),
                str(getattr(speech, "phase", "") or ""),
                self._hash_speech_content(speech),
            ]
        )

    def _find_latest_speech(
        self,
        recent_speeches: List[Speech],
        *,
        roles: Optional[List[str]] = None,
        speaker_side: Optional[str] = None,
        phase: Optional[str] = None,
    ) -> Optional[Speech]:
        normalized_roles = {str(role or "").strip() for role in (roles or []) if str(role or "").strip()}
        normalized_phase = str(phase or "").strip()
        for speech in reversed(recent_speeches):
            speech_role = str(getattr(speech, "speaker_role", "") or "").strip()
            if normalized_roles and speech_role not in normalized_roles:
                continue
            if speaker_side and self._speaker_side(speech_role) != speaker_side:
                continue
            if normalized_phase and str(getattr(speech, "phase", "") or "").strip() != normalized_phase:
                continue
            if not str(getattr(speech, "content", "") or "").strip():
                continue
            return speech
        return None

    def _summarize_speeches(
        self,
        speeches: List[Speech],
        *,
        max_items: int = 4,
        with_speaker: bool = True,
    ) -> str:
        lines: List[str] = []
        for speech in speeches[-max_items:]:
            content = str(getattr(speech, "content", "") or "").strip()
            if not content:
                continue
            prefix = ""
            if with_speaker:
                prefix = f"{str(getattr(speech, 'speaker_role', '') or 'unknown')}: "
            lines.append(f"{prefix}{content}")
        return "\n".join(lines)

    def _merge_dependency_speeches(
        self, *speech_groups: Optional[List[Optional[Speech]]]
    ) -> List[Speech]:
        merged: List[Speech] = []
        seen_keys = set()
        for speech_group in speech_groups:
            for speech in speech_group or []:
                if speech is None:
                    continue
                speech_id = str(getattr(speech, "id", "") or "").strip()
                if speech_id:
                    dedupe_key = speech_id
                else:
                    dedupe_key = "|".join(
                        [
                            str(getattr(speech, "speaker_role", "") or ""),
                            str(getattr(speech, "timestamp", "") or ""),
                            self._hash_speech_content(speech),
                        ]
                    )
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                merged.append(speech)
        return merged

    def _collect_dependency_speeches(
        self,
        segment_id: str,
        turn_plan: Dict[str, Any],
        recent_speeches: List[Speech],
        speaker_role: Optional[str],
    ) -> List[Speech]:
        speech_type = str(turn_plan.get("speech_type") or "free_debate")
        speaker_side = self._speaker_side(speaker_role)
        opponent_side = "negative" if speaker_side == "positive" else "positive"
        questioning_phase = str(DebatePhase.QUESTIONING.value)

        if segment_id == "questioning_2_neg_answer":
            latest_question = self._find_latest_speech(
                recent_speeches,
                roles=["debater_2"],
                phase=questioning_phase,
            )
            context = [
                speech
                for speech in recent_speeches
                if str(getattr(speech, "phase", "") or "") == questioning_phase
                and self._speaker_side(getattr(speech, "speaker_role", None))
                == opponent_side
            ][-3:]
            ordered = [speech for speech in context if speech is not None]
            if latest_question and latest_question not in ordered:
                ordered.append(latest_question)
            return ordered

        if segment_id == "questioning_3_ai3_ask":
            recent_positive = [
                speech
                for speech in recent_speeches
                if str(getattr(speech, "phase", "") or "") == questioning_phase
                and self._speaker_side(getattr(speech, "speaker_role", None))
                == opponent_side
            ][-2:]
            latest_negative_answer = self._find_latest_speech(
                recent_speeches,
                roles=["ai_2", "ai_3"],
                phase=questioning_phase,
            )
            ordered = [speech for speech in recent_positive if speech is not None]
            if latest_negative_answer and latest_negative_answer not in ordered:
                ordered.append(latest_negative_answer)
            return ordered

        if segment_id == "questioning_4_neg_answer":
            latest_question = self._find_latest_speech(
                recent_speeches,
                roles=["debater_3"],
                phase=questioning_phase,
            )
            context = [
                speech
                for speech in recent_speeches
                if str(getattr(speech, "phase", "") or "") == questioning_phase
                and self._speaker_side(getattr(speech, "speaker_role", None))
                == opponent_side
            ][-3:]
            ordered = [speech for speech in context if speech is not None]
            if latest_question and latest_question not in ordered:
                ordered.append(latest_question)
            return ordered

        if segment_id == "questioning_neg_summary":
            return [
                speech
                for speech in recent_speeches
                if str(getattr(speech, "phase", "") or "") == questioning_phase
            ]

        if segment_id == "closing_negative_4":
            return list(recent_speeches)

        if speech_type == "response":
            latest_question = self._find_latest_speech(
                recent_speeches,
                speaker_side=opponent_side,
            )
            return [latest_question] if latest_question else []

        if speech_type == "rebuttal":
            latest_argument = self._find_latest_speech(
                recent_speeches,
                speaker_side=opponent_side,
            )
            return [latest_argument] if latest_argument else []

        if speech_type == "question":
            return [
                speech
                for speech in recent_speeches
                if self._speaker_side(getattr(speech, "speaker_role", None))
                == opponent_side
            ][-3:]

        if speech_type == "closing":
            return recent_speeches[-12:]

        if speech_type == "free_debate":
            latest_human = self._find_latest_speech(
                recent_speeches,
                speaker_side=opponent_side,
            )
            latest_same_side_ai = self._find_latest_speech(
                recent_speeches,
                speaker_side=speaker_side,
            )
            recent_global = recent_speeches[-6:]
            return self._merge_dependency_speeches(
                [latest_same_side_ai] if latest_same_side_ai else [],
                [latest_human] if latest_human else [],
                recent_global,
            )

        return recent_speeches[-10:]

    def _is_room_segment_active(self, room_id: str, segment: Dict[str, Any]) -> bool:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return False
        return (
            room_state.current_phase == segment.get("phase")
            and str(room_state.segment_id or "") == str(segment.get("id") or "")
        )

    def _speaker_side(self, speaker_role: Optional[str]) -> Optional[str]:
        normalized = str(speaker_role or "").strip()
        if normalized.startswith("ai_"):
            return "negative"
        if normalized.startswith("debater_"):
            return "positive"
        return None

    def _should_skip_ai_turn_without_dependency(
        self,
        segment_id: str,
        turn_plan: Dict[str, Any],
        dependency_speeches: List[Speech],
    ) -> bool:
        if str(turn_plan.get("speech_type") or "") != "response":
            return False
        if str(turn_plan.get("dependency_scope") or "") != "last_opponent_question":
            return False
        if str(segment_id or "") not in {
            "questioning_2_neg_answer",
            "questioning_4_neg_answer",
        }:
            return False
        return not any(
            str(getattr(speech, "content", "") or "").strip()
            for speech in dependency_speeches
        )

    async def _skip_ai_turn_due_to_missing_dependency(
        self,
        room_id: str,
        *,
        segment: Dict[str, Any],
        speaker_role: str,
    ) -> None:
        await self._clear_ai_turn_state_if_matches(
            room_id,
            segment_id=str(segment.get("id") or ""),
            speaker_role=speaker_role,
        )
        await room_manager.update_room_state(
            room_id,
            turn_processing_status="idle",
            turn_processing_kind=None,
            turn_processing_error=None,
            turn_speech_committed=False,
            turn_speech_user_id=None,
            turn_speech_role=None,
            turn_speech_timestamp=None,
            pending_advance_reason=None,
        )
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "ai_turn_skipped",
                "data": {
                    "reason": "missing_opponent_question",
                    "segment_id": str(segment.get("id") or ""),
                    "segment_title": str(segment.get("title") or ""),
                    "speaker_role": speaker_role,
                    "timestamp": self._now().isoformat(),
                },
            },
        )
        await self.advance_segment(room_id)

    def _resolve_ai_stance(
        self, room_state: Any, speaker_role: Optional[str]
    ) -> str:
        if room_state and getattr(room_state, "ai_debaters", None):
            debater_info = next(
                (
                    item
                    for item in (room_state.ai_debaters or [])
                    if item.get("id") == str(speaker_role or "")
                ),
                None,
            )
            stance = str((debater_info or {}).get("stance") or "").strip()
            if stance in {"positive", "negative"}:
                return stance
        return "negative"

    def _resolve_ai_name(
        self, room_state: Any, speaker_role: Optional[str]
    ) -> Optional[str]:
        if room_state and getattr(room_state, "ai_debaters", None):
            debater_info = next(
                (
                    item
                    for item in (room_state.ai_debaters or [])
                    if item.get("id") == str(speaker_role or "")
                ),
                None,
            )
            if debater_info:
                return debater_info.get("name")
        return None

    async def _set_ai_turn_state(
        self,
        room_id: str,
        *,
        status: str,
        segment_id: Optional[str] = None,
        segment_title: Optional[str] = None,
        speaker_role: Optional[str] = None,
    ) -> None:
        await room_manager.update_room_state(
            room_id,
            ai_turn_status=str(status),
            ai_turn_segment_id=segment_id,
            ai_turn_segment_title=segment_title,
            ai_turn_speaker_role=speaker_role,
        )

    async def _clear_ai_turn_state(self, room_id: str) -> None:
        await self._set_ai_turn_state(
            room_id,
            status="idle",
            segment_id=None,
            segment_title=None,
            speaker_role=None,
        )

    async def _clear_ai_turn_state_if_matches(
        self,
        room_id: str,
        *,
        segment_id: Optional[str],
        speaker_role: Optional[str],
    ) -> None:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return
        if segment_id is not None and str(getattr(room_state, "ai_turn_segment_id", "") or "") != str(segment_id or ""):
            return
        if speaker_role is not None and str(getattr(room_state, "ai_turn_speaker_role", "") or "") != str(speaker_role or ""):
            return
        await self._clear_ai_turn_state(room_id)

    def _is_playback_gate_active(self, room_state: Optional[Any]) -> bool:
        if not room_state:
            return False
        return str(getattr(room_state, "playback_gate_status", "idle") or "idle") in {
            "waiting",
            "playing",
        }

    def _role_matches(self, expected: Optional[str], actual: Optional[str]) -> bool:
        normalized_expected = str(expected or "").strip()
        normalized_actual = str(actual or "").strip()
        if not normalized_expected or not normalized_actual:
            return False
        if normalized_expected == normalized_actual:
            return True
        if normalized_actual.endswith(f".{normalized_expected}"):
            return True
        return normalized_expected in normalized_actual

    def _resolve_playback_gate_deadline(self, duration_sec: int) -> datetime:
        normalized_duration = max(1, int(duration_sec or 1))
        buffer_sec = min(6.0, max(2.0, normalized_duration * 0.25))
        return self._now() + timedelta(seconds=normalized_duration + buffer_sec)

    def _resolve_playback_controller_user_id(
        self, room_state: Optional[Any]
    ) -> Optional[str]:
        participants = list(getattr(room_state, "participants", None) or [])
        preferred = next(
            (
                str(item.get("user_id") or "").strip()
                for item in participants
                if self._role_matches("debater_1", item.get("role"))
                and str(item.get("user_id") or "").strip()
            ),
            "",
        )
        if preferred:
            return preferred
        fallback = next(
            (
                str(item.get("user_id") or "").strip()
                for item in participants
                if str(item.get("user_id") or "").strip()
            ),
            "",
        )
        return fallback or None

    def _is_playback_controller_online(
        self, room_state: Optional[Any], user_id: Optional[str]
    ) -> bool:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id or not room_state:
            return False
        return any(
            str(item.get("user_id") or "").strip() == normalized_user_id
            for item in (getattr(room_state, "participants", None) or [])
        )

    async def _broadcast_playback_controller_appointed(
        self,
        room_id: str,
        *,
        speech_id: Optional[str],
        segment_id: Optional[str],
        speaker_role: Optional[str],
        controller_user_id: Optional[str],
    ) -> None:
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "playback_controller_appointed",
                "data": {
                    "speech_id": speech_id,
                    "segment_id": segment_id,
                    "speaker_role": speaker_role,
                    "controller_user_id": controller_user_id,
                    "timestamp": self._now().isoformat(),
                },
            },
        )

    async def _clear_playback_gate_state(self, room_id: str) -> None:
        await room_manager.update_room_state(
            room_id,
            playback_gate_status="idle",
            playback_gate_speech_id=None,
            playback_gate_segment_id=None,
            playback_gate_speaker_role=None,
            playback_gate_controller_user_id=None,
            playback_gate_started_at=None,
            playback_gate_deadline_at=None,
            pending_post_playback_action=None,
            flow_segments=self._serialize_segments(segments),
        )

    async def _start_playback_gate(
        self,
        room_id: str,
        *,
        speech_id: str,
        segment_id: str,
        speaker_role: str,
        duration_sec: int,
        post_action: str,
    ) -> bool:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return False

        if (
            self._is_playback_gate_active(room_state)
            and str(getattr(room_state, "playback_gate_speech_id", "") or "") == speech_id
        ):
            return True

        controller_user_id = self._resolve_playback_controller_user_id(room_state)
        started_at = self._now()
        deadline_at = self._resolve_playback_gate_deadline(duration_sec)
        await room_manager.update_room_state(
            room_id,
            playback_gate_status="waiting",
            playback_gate_speech_id=speech_id,
            playback_gate_segment_id=segment_id,
            playback_gate_speaker_role=speaker_role,
            playback_gate_controller_user_id=controller_user_id,
            playback_gate_started_at=started_at,
            playback_gate_deadline_at=deadline_at,
            pending_post_playback_action=post_action,
        )
        await self._broadcast_playback_controller_appointed(
            room_id,
            speech_id=speech_id,
            segment_id=segment_id,
            speaker_role=speaker_role,
            controller_user_id=controller_user_id,
        )
        return True

    async def _refresh_playback_controller_if_needed(self, room_id: str) -> bool:
        room_state = room_manager.get_room_state(room_id)
        if not self._is_playback_gate_active(room_state):
            return False

        current_controller_user_id = str(
            getattr(room_state, "playback_gate_controller_user_id", "") or ""
        ).strip()
        if self._is_playback_controller_online(room_state, current_controller_user_id):
            return False

        next_controller_user_id = self._resolve_playback_controller_user_id(room_state)
        if next_controller_user_id == current_controller_user_id:
            return False

        await room_manager.update_room_state(
            room_id,
            playback_gate_controller_user_id=next_controller_user_id,
        )
        await self._broadcast_playback_controller_appointed(
            room_id,
            speech_id=str(getattr(room_state, "playback_gate_speech_id", "") or ""),
            segment_id=str(getattr(room_state, "playback_gate_segment_id", "") or ""),
            speaker_role=str(getattr(room_state, "playback_gate_speaker_role", "") or ""),
            controller_user_id=next_controller_user_id,
        )
        return True

    def _matches_playback_gate(
        self,
        room_state: Optional[Any],
        *,
        speech_id: Optional[str] = None,
        segment_id: Optional[str] = None,
        speaker_role: Optional[str] = None,
    ) -> bool:
        if not self._is_playback_gate_active(room_state):
            return False
        if speech_id is not None and str(getattr(room_state, "playback_gate_speech_id", "") or "") != str(speech_id or ""):
            return False
        if segment_id is not None and str(segment_id or "") and str(getattr(room_state, "playback_gate_segment_id", "") or "") != str(segment_id or ""):
            return False
        if speaker_role is not None and str(speaker_role or "") and str(getattr(room_state, "playback_gate_speaker_role", "") or "") != str(speaker_role or ""):
            return False
        return True

    async def _finalize_playback_gate(
        self,
        room_id: str,
        *,
        status: str,
        speech_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        await self._refresh_playback_controller_if_needed(room_id)
        room_state = room_manager.get_room_state(room_id)
        if not self._matches_playback_gate(room_state, speech_id=speech_id):
            return False

        if user_id is not None:
            controller_user_id = str(
                getattr(room_state, "playback_gate_controller_user_id", "") or ""
            ).strip()
            if controller_user_id and controller_user_id != str(user_id or ""):
                return False

        pending_action = str(
            getattr(room_state, "pending_post_playback_action", "none") or "none"
        )
        gate_segment_id = str(getattr(room_state, "playback_gate_segment_id", "") or "")
        gate_speaker_role = str(
            getattr(room_state, "playback_gate_speaker_role", "") or ""
        )

        await room_manager.update_room_state(
            room_id,
            playback_gate_status=status,
            pending_advance_reason=None,
        )
        await self._clear_playback_gate_state(room_id)

        if pending_action == "advance_segment":
            await self.advance_segment(room_id)
            return True

        if pending_action == "release_mic":
            latest_state = room_manager.get_room_state(room_id)
            if not latest_state:
                return False
            await room_manager.update_room_state(
                room_id,
                mic_owner_user_id=None,
                mic_owner_role=None,
                mic_expires_at=None,
                current_speaker=None,
                free_debate_last_side="ai",
                free_debate_next_side="human",
            )
            await self._clear_ai_turn_state_if_matches(
                room_id,
                segment_id=gate_segment_id,
                speaker_role=gate_speaker_role,
            )
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "mic_released",
                    "data": {
                        "reason": "ai_done",
                        "timestamp": self._now().isoformat(),
                    },
                },
            )
            return True

        return True

    async def handle_speech_playback_started(
        self, room_id: str, user_id: str, data: Dict[str, Any]
    ) -> bool:
        await self._refresh_playback_controller_if_needed(room_id)
        room_state = room_manager.get_room_state(room_id)
        speech_id = str(data.get("speech_id") or "").strip()
        segment_id = str(data.get("segment_id") or "").strip()
        speaker_role = str(data.get("speaker_role") or "").strip()
        if not self._matches_playback_gate(
            room_state,
            speech_id=speech_id or None,
            segment_id=segment_id or None,
            speaker_role=speaker_role or None,
        ):
            return False

        controller_user_id = str(
            getattr(room_state, "playback_gate_controller_user_id", "") or ""
        ).strip()
        if controller_user_id and controller_user_id != str(user_id or ""):
            return False

        if str(getattr(room_state, "playback_gate_status", "") or "") == "playing":
            return True

        await room_manager.update_room_state(room_id, playback_gate_status="playing")
        return True

    async def handle_speech_playback_finished(
        self, room_id: str, user_id: str, data: Dict[str, Any]
    ) -> bool:
        speech_id = str(data.get("speech_id") or "").strip()
        return await self._finalize_playback_gate(
            room_id,
            status="completed",
            speech_id=speech_id or None,
            user_id=user_id,
        )

    async def handle_speech_playback_failed(
        self, room_id: str, user_id: str, data: Dict[str, Any]
    ) -> bool:
        speech_id = str(data.get("speech_id") or "").strip()
        return await self._finalize_playback_gate(
            room_id,
            status="skipped",
            speech_id=speech_id or None,
            user_id=user_id,
        )

    def _build_free_debate_segment(self) -> Dict[str, Any]:
        return {
            "id": "free_debate",
            "title": "自由辩论",
            "phase": DebatePhase.FREE_DEBATE,
            "mode": "free",
            "speaker_roles": ["ai_1", "ai_2", "ai_3", "ai_4"],
        }

    def _select_free_debate_ai_speaker(
        self,
        recent_speeches: List[Speech],
        room_state: Optional[Any] = None,
    ) -> str:
        candidate_roles = [
            str(item.get("id") or "").strip()
            for item in (getattr(room_state, "ai_debaters", None) or [])
            if str(item.get("id") or "").strip().startswith("ai_")
        ]
        if not candidate_roles:
            candidate_roles = ["ai_1", "ai_2", "ai_3", "ai_4"]

        latest_indexes: Dict[str, int] = {}
        for index, speech in enumerate(recent_speeches):
            speech_role = str(getattr(speech, "speaker_role", "") or "").strip()
            if speech_role in candidate_roles:
                latest_indexes[speech_role] = index

        ranked_roles = sorted(
            candidate_roles,
            key=lambda role: (latest_indexes.get(role, -1), candidate_roles.index(role)),
        )
        return ranked_roles[0] if ranked_roles else "ai_1"

    def _can_prepare_or_release_free_debate_ai(self, room_state: Optional[Any]) -> bool:
        if not room_state:
            return False
        if getattr(room_state, "current_phase", None) != DebatePhase.FREE_DEBATE:
            return False
        if str(getattr(room_state, "segment_id", "") or "") != "free_debate":
            return False
        if getattr(room_state, "free_debate_next_side", "human") != "ai":
            return False
        return True

    def resolve_ai_turn_plan(
        self,
        segment: Dict[str, Any],
        room_state: Any,
        *,
        coze_parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        phase = segment.get("phase") or getattr(room_state, "current_phase", None)
        segment_id = str(segment.get("id") or "")

        speech_type = "free_debate"
        dependency_scope = "recent_speeches"
        if phase == DebatePhase.OPENING:
            speech_type = "opening"
            dependency_scope = "topic_and_knowledge"
        elif phase == DebatePhase.CLOSING:
            speech_type = "closing"
            dependency_scope = "full_debate_summary"
        elif phase == DebatePhase.QUESTIONING:
            if "ask" in segment_id:
                speech_type = "question"
                dependency_scope = "recent_opponent_arguments"
            elif "answer" in segment_id:
                speech_type = "response"
                dependency_scope = "last_opponent_question"
            else:
                speech_type = "rebuttal"
                dependency_scope = "recent_questioning_exchange"

        default_turns = CozeConfig.get_default_ai_turns()
        default_strategy = (
            default_turns.get("default") if isinstance(default_turns, dict) else {}
        ) or {}
        built_in_segment_strategy = (
            default_turns.get(segment_id) if isinstance(default_turns, dict) else {}
        ) or {}
        configured_turns: Dict[str, Any] = {}
        if isinstance(coze_parameters, dict):
            raw_turns = coze_parameters.get("ai_turns")
            if isinstance(raw_turns, dict):
                configured_turns = raw_turns
        configured_default_strategy = (
            configured_turns.get("default")
            if isinstance(configured_turns, dict)
            else {}
        ) or {}
        configured_segment_strategy = (
            configured_turns.get(segment_id)
            if isinstance(configured_turns, dict)
            else {}
        ) or {}

        plan = {
            "segment_id": segment_id,
            "speech_type": speech_type,
            "prethinking_mode": self._normalize_prethinking_mode(
                default_strategy.get("prethinking_mode"),
                default="reactive",
            ),
            "dependency_scope": dependency_scope,
            "response_delay_sec": self._coerce_nonnegative_float(
                default_strategy.get("response_delay_sec"),
                2.0,
            ),
            "thinking_timeout_sec": self._coerce_nonnegative_float(
                default_strategy.get("thinking_timeout_sec"),
                20.0,
            ),
            "draft_ttl_sec": self._coerce_nonnegative_float(
                default_strategy.get("draft_ttl_sec"),
                120.0,
            ),
        }
        for strategy in (
            built_in_segment_strategy,
            configured_default_strategy,
            configured_segment_strategy,
        ):
            if not isinstance(strategy, dict):
                continue
            if "prethinking_mode" in strategy:
                plan["prethinking_mode"] = self._normalize_prethinking_mode(
                    strategy.get("prethinking_mode"),
                    default=plan["prethinking_mode"],
                )
            if "response_delay_sec" in strategy:
                plan["response_delay_sec"] = self._coerce_nonnegative_float(
                    strategy.get("response_delay_sec"),
                    plan["response_delay_sec"],
                )
            if "thinking_timeout_sec" in strategy:
                plan["thinking_timeout_sec"] = self._coerce_nonnegative_float(
                    strategy.get("thinking_timeout_sec"),
                    plan["thinking_timeout_sec"],
                )
            if "draft_ttl_sec" in strategy:
                plan["draft_ttl_sec"] = self._coerce_nonnegative_float(
                    strategy.get("draft_ttl_sec"),
                    plan["draft_ttl_sec"],
                )
        return plan

    def _load_recent_speeches(
        self, db: Any, debate_uuid: uuid.UUID, *, limit: int = 30
    ) -> List[Speech]:
        recent_desc = (
            db.execute(
                select(Speech)
                .where(Speech.debate_id == debate_uuid)
                .order_by(Speech.timestamp.desc(), Speech.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        speeches = list(reversed(recent_desc))
        return [
            speech
            for speech in speeches
            if str(getattr(speech, "content", "") or "").strip()
        ]

    def _build_llm_context(self, recent_speeches: List[Speech]) -> List[Dict[str, str]]:
        context: List[Dict[str, str]] = []
        for speech in recent_speeches[-20:]:
            content = str(getattr(speech, "content", "") or "").strip()
            if not content:
                continue
            context.append(
                {
                    "role": "assistant" if speech.speaker_type == "ai" else "user",
                    "content": content,
                }
            )
        return context

    def _build_turn_dependency_signature(
        self,
        turn_plan: Dict[str, Any],
        recent_speeches: List[Speech],
        speaker_role: Optional[str],
        *,
        segment_id: Optional[str] = None,
    ) -> str:
        normalized_segment_id = str(
            segment_id or turn_plan.get("segment_id") or ""
        ).strip()
        relevant = self._collect_dependency_speeches(
            normalized_segment_id,
            turn_plan,
            recent_speeches,
            speaker_role,
        )
        signature_parts = [
            self._build_speech_signature_token(speech)
            for speech in relevant
        ]
        return f"{normalized_segment_id}|{'|'.join(signature_parts)}"

    def _build_generation_kwargs(
        self,
        turn_plan: Dict[str, Any],
        recent_speeches: List[Speech],
        speaker_role: Optional[str],
        *,
        segment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        speech_type = str(turn_plan.get("speech_type") or "free_debate")
        normalized_segment_id = str(
            segment_id or turn_plan.get("segment_id") or ""
        ).strip()
        speaker_side = self._speaker_side(speaker_role)
        opponent_side = "negative" if speaker_side == "positive" else "positive"

        opponent_speeches = [
            speech
            for speech in recent_speeches
            if self._speaker_side(getattr(speech, "speaker_role", None)) == opponent_side
        ]
        same_side_speeches = [
            speech
            for speech in recent_speeches
            if self._speaker_side(getattr(speech, "speaker_role", None)) == speaker_side
        ]

        kwargs: Dict[str, Any] = {}
        if normalized_segment_id == "questioning_neg_summary":
            questioning_speeches = self._collect_dependency_speeches(
                normalized_segment_id,
                turn_plan,
                recent_speeches,
                speaker_role,
            )
            kwargs["opponent_argument"] = self._summarize_speeches(
                questioning_speeches,
                max_items=10,
                with_speaker=True,
            )
        elif speech_type == "question":
            dependency_speeches = self._collect_dependency_speeches(
                normalized_segment_id,
                turn_plan,
                recent_speeches,
                speaker_role,
            )
            question_inputs = [
                speech
                for speech in dependency_speeches
                if self._speaker_side(getattr(speech, "speaker_role", None))
                == opponent_side
            ] or opponent_speeches[-3:]
            kwargs["opponent_arguments"] = [
                str(getattr(speech, "content", "") or "").strip()
                for speech in question_inputs[-3:]
                if str(getattr(speech, "content", "") or "").strip()
            ]
        elif speech_type == "response":
            dependency_speeches = self._collect_dependency_speeches(
                normalized_segment_id,
                turn_plan,
                recent_speeches,
                speaker_role,
            )
            latest_question = (
                str(getattr(dependency_speeches[-1], "content", "") or "").strip()
                if dependency_speeches
                else ""
            )
            context_summary = self._summarize_speeches(
                dependency_speeches[:-1],
                max_items=2,
                with_speaker=True,
            )
            kwargs["question"] = (
                f"{latest_question}\n\n补充上下文：\n{context_summary}"
                if context_summary
                else latest_question
            )
        elif speech_type == "rebuttal":
            dependency_speeches = self._collect_dependency_speeches(
                normalized_segment_id,
                turn_plan,
                recent_speeches,
                speaker_role,
            )
            latest_argument = (
                str(getattr(dependency_speeches[-1], "content", "") or "").strip()
                if dependency_speeches
                else ""
            )
            kwargs["opponent_argument"] = latest_argument
        elif speech_type == "closing":
            if normalized_segment_id == "closing_negative_4":
                closing_speeches = self._collect_dependency_speeches(
                    normalized_segment_id,
                    turn_plan,
                    recent_speeches,
                    speaker_role,
                )
                recent_same_side = [
                    speech
                    for speech in closing_speeches
                    if self._speaker_side(getattr(speech, "speaker_role", None))
                    == speaker_side
                ][-6:]
                recent_opponent = [
                    speech
                    for speech in closing_speeches
                    if self._speaker_side(getattr(speech, "speaker_role", None))
                    == opponent_side
                ][-6:]
                kwargs["key_points"] = [
                    f"我方关键点：{str(getattr(speech, 'content', '') or '').strip()}"
                    for speech in recent_same_side
                    if str(getattr(speech, "content", "") or "").strip()
                ] + [
                    f"对方待回应点：{str(getattr(speech, 'content', '') or '').strip()}"
                    for speech in recent_opponent
                    if str(getattr(speech, "content", "") or "").strip()
                ]
            else:
                kwargs["key_points"] = [
                    str(getattr(speech, "content", "") or "").strip()
                    for speech in same_side_speeches[-4:]
                    if str(getattr(speech, "content", "") or "").strip()
                ]
        elif speech_type == "free_debate":
            dependency_speeches = self._collect_dependency_speeches(
                normalized_segment_id,
                turn_plan,
                recent_speeches,
                speaker_role,
            )
            kwargs["recent_speeches"] = [
                {
                    "speaker": str(
                        getattr(speech, "speaker_role", None)
                        or getattr(speech, "speaker_type", None)
                        or "未知"
                    ),
                    "content": str(getattr(speech, "content", "") or "").strip(),
                }
                for speech in dependency_speeches
                if str(getattr(speech, "content", "") or "").strip()
            ]

        return kwargs

    def _find_next_eager_ai_segment(
        self,
        room_id: str,
        room_state: Any,
        *,
        coze_parameters: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        segments = self.get_segments(room_id)
        current_index = int(getattr(room_state, "segment_index", 0) or 0)
        for index in range(current_index + 1, len(segments)):
            segment = segments[index]
            if str(segment.get("mode") or "") != "fixed":
                continue
            speaker_role = self._resolve_segment_speaker_role(segment, room_state)
            if not speaker_role or not speaker_role.startswith("ai_"):
                continue
            turn_plan = self.resolve_ai_turn_plan(
                segment,
                room_state,
                coze_parameters=coze_parameters,
            )
            if str(turn_plan.get("prethinking_mode") or "") != "eager":
                continue
            return {
                "index": index,
                "segment": segment,
                "speaker_role": speaker_role,
                "turn_plan": turn_plan,
            }
        return None

    def _is_context_reactive_segment(self, segment_id: Optional[str]) -> bool:
        return str(segment_id or "") in self.CONTEXT_REACTIVE_SEGMENT_IDS

    def _reactive_segment_can_prepare_now(
        self,
        target_segment_id: str,
        *,
        current_segment_id: Optional[str],
        committed_segment_id: Optional[str],
    ) -> bool:
        normalized_target = str(target_segment_id or "")
        normalized_current = str(current_segment_id or "")
        normalized_committed = str(committed_segment_id or "")
        if normalized_target and normalized_target == normalized_current:
            return True
        dependency_ready_sources = {
            "questioning_2_neg_answer": {"questioning_2_pos2_ask"},
            "questioning_3_ai3_ask": {"questioning_2_neg_answer"},
            "questioning_4_neg_answer": {"questioning_4_pos3_ask"},
            "questioning_neg_summary": {"questioning_4_neg_answer"},
            "closing_negative_4": {"free_debate"},
        }
        return normalized_committed in dependency_ready_sources.get(
            normalized_target,
            set(),
        )

    def _find_next_reactive_ai_segment(
        self,
        room_id: str,
        room_state: Any,
        *,
        coze_parameters: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        segments = self.get_segments(room_id)
        current_index = int(getattr(room_state, "segment_index", 0) or 0)
        current_segment_id = str(getattr(room_state, "segment_id", "") or "")
        current_turn_committed = bool(
            getattr(room_state, "turn_speech_committed", False)
        )
        for index in range(current_index, len(segments)):
            segment = segments[index]
            segment_id = str(segment.get("id") or "")
            if not self._is_context_reactive_segment(segment_id):
                continue
            if (
                index == current_index
                and segment_id == current_segment_id
                and current_turn_committed
            ):
                continue
            speaker_role = self._resolve_segment_speaker_role(segment, room_state)
            if not speaker_role or not speaker_role.startswith("ai_"):
                continue
            if index == current_index and segment_id != current_segment_id:
                continue
            turn_plan = self.resolve_ai_turn_plan(
                segment,
                room_state,
                coze_parameters=coze_parameters,
            )
            return {
                "index": index,
                "segment": segment,
                "speaker_role": speaker_role,
                "turn_plan": turn_plan,
            }
        return None

    async def _invalidate_context_reactive_drafts(
        self,
        room_id: str,
        room_state: Any,
        recent_speeches: List[Speech],
        *,
        coze_parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        room_drafts = dict(self.ai_drafts.get(room_id) or {})
        if not room_drafts:
            return
        segments_by_id = {
            str(segment.get("id") or ""): segment for segment in self.get_segments(room_id)
        }
        for draft in room_drafts.values():
            segment_id = str(draft.get("segment_id") or "")
            speaker_role = str(draft.get("speaker_role") or "")
            if not self._is_context_reactive_segment(segment_id):
                continue
            segment = segments_by_id.get(segment_id)
            if not segment or not speaker_role:
                continue
            turn_plan = self.resolve_ai_turn_plan(
                segment,
                room_state,
                coze_parameters=coze_parameters,
            )
            next_signature = self._build_turn_dependency_signature(
                turn_plan,
                recent_speeches,
                speaker_role,
                segment_id=segment_id,
            )
            current_signature = str(draft.get("dependency_signature") or "")
            if current_signature and current_signature == next_signature:
                continue
            if draft.get("status") == "ready":
                self._mark_ai_draft_invalidated(
                    room_id,
                    draft,
                    reason="dependency_changed",
                )
                if (
                    str(getattr(room_state, "ai_turn_segment_id", "") or "") == segment_id
                    and str(getattr(room_state, "ai_turn_speaker_role", "") or "")
                    == speaker_role
                ):
                    await self._set_ai_turn_state(
                        room_id,
                        status="recomputing",
                        segment_id=segment_id,
                        segment_title=str(segment.get("title") or ""),
                        speaker_role=speaker_role,
                    )
            task = self._get_ai_draft_task(
                room_id,
                segment_id=segment_id,
                speaker_role=speaker_role,
            )
            if task and not task.done():
                task.cancel()
                self._clear_ai_draft_task(
                    room_id,
                    segment_id=segment_id,
                    speaker_role=speaker_role,
                )
                if draft.get("status") != "released":
                    self._mark_ai_draft_invalidated(
                        room_id,
                    draft,
                    reason="dependency_changed",
                )
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except RuntimeError:
                    pass

    async def notify_speech_committed(
        self,
        room_id: str,
        *,
        speech_id: Optional[str] = None,
        speaker_role: Optional[str] = None,
        segment_id: Optional[str] = None,
    ) -> None:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return
        try:
            debate_uuid = uuid.UUID(str(room_state.debate_id))
        except ValueError:
            return

        db = None
        try:
            if db_module.SessionLocal is None:
                db_module.init_engine()
            db = db_module.SessionLocal()
            config_service = ConfigService(db)
            coze_config = await config_service.get_coze_config()
            coze_parameters = getattr(coze_config, "parameters", None) or {}
            recent_speeches = self._load_recent_speeches(db, debate_uuid, limit=200)
            await self._invalidate_context_reactive_drafts(
                room_id,
                room_state,
                recent_speeches,
                coze_parameters=coze_parameters,
            )

            target = self._find_next_reactive_ai_segment(
                room_id,
                room_state,
                coze_parameters=coze_parameters,
            )
            if not target:
                await self._sync_upcoming_ai_prethinking(room_id)
                return

            segment = target["segment"]
            target_speaker_role = str(target["speaker_role"] or "")
            turn_plan = target["turn_plan"]
            target_segment_id = str(segment.get("id") or "")
            if not self._reactive_segment_can_prepare_now(
                target_segment_id,
                current_segment_id=str(getattr(room_state, "segment_id", "") or ""),
                committed_segment_id=segment_id,
            ):
                await self._sync_upcoming_ai_prethinking(room_id)
                return
            cached = self._get_ai_draft(
                room_id,
                segment_id=target_segment_id,
                speaker_role=target_speaker_role,
            )
            next_signature = self._build_turn_dependency_signature(
                turn_plan,
                recent_speeches,
                target_speaker_role,
                segment_id=target_segment_id,
            )
            if self._is_ai_draft_usable(
                cached,
                turn_plan=turn_plan,
                dependency_signature=next_signature,
            ):
                await room_manager.update_room_state(
                    room_id,
                    ai_turn_status="ready",
                    ai_turn_segment_id=target_segment_id,
                    ai_turn_segment_title=str(segment.get("title") or ""),
                    ai_turn_speaker_role=target_speaker_role,
                )
                return

            existing_task = self._get_ai_draft_task(
                room_id,
                segment_id=target_segment_id,
                speaker_role=target_speaker_role,
            )
            if existing_task and not existing_task.done():
                await room_manager.update_room_state(
                    room_id,
                    ai_turn_status="thinking",
                    ai_turn_segment_id=target_segment_id,
                    ai_turn_segment_title=str(segment.get("title") or ""),
                    ai_turn_speaker_role=target_speaker_role,
                )
                return

            await room_manager.update_room_state(
                room_id,
                ai_turn_status="thinking",
                ai_turn_segment_id=target_segment_id,
                ai_turn_segment_title=str(segment.get("title") or ""),
                ai_turn_speaker_role=target_speaker_role,
            )
            task = asyncio.create_task(
                self._prepare_upcoming_ai_draft(
                    room_id,
                    segment,
                    target_speaker_role,
                )
            )
            self._store_ai_draft_task(
                room_id,
                segment_id=target_segment_id,
                speaker_role=target_speaker_role,
                task=task,
            )
            logger.info(
                "Scheduled reactive AI draft refresh: room=%s segment=%s speech=%s speaker=%s source_segment=%s",
                room_id,
                target_segment_id,
                speech_id,
                target_speaker_role,
                segment_id,
            )
        except Exception as exc:
            logger.warning(
                "notify_speech_committed failed for room %s: %s",
                room_id,
                exc,
                exc_info=True,
            )
        finally:
            if db is not None:
                db.close()

    async def _cancel_ai_draft_tasks(
        self, room_id: str, *, keep_keys: Optional[List[str]] = None
    ) -> None:
        room_tasks = self.ai_draft_tasks.get(room_id)
        if not room_tasks:
            return
        keep_key_set = set(keep_keys or [])
        current_task = asyncio.current_task()
        for key, task in list(room_tasks.items()):
            if task.done():
                room_tasks.pop(key, None)
                continue
            if key in keep_key_set:
                continue
            task.cancel()
            room_tasks.pop(key, None)
            if task is current_task:
                continue
            try:
                await task
            except asyncio.CancelledError:
                pass
            except RuntimeError:
                pass
        if not room_tasks:
            self.ai_draft_tasks.pop(room_id, None)

    async def _prepare_upcoming_ai_draft(
        self,
        room_id: str,
        segment: Dict[str, Any],
        speaker_role: str,
    ) -> None:
        segment_id = str(segment.get("id") or "")
        db = None
        try:
            room_state = room_manager.get_room_state(room_id)
            if not room_state:
                return
            try:
                debate_uuid = uuid.UUID(str(room_state.debate_id))
            except ValueError:
                return
            if db_module.SessionLocal is None:
                db_module.init_engine()
            db = db_module.SessionLocal()
            debate = db.execute(
                select(Debate).where(Debate.id == debate_uuid)
            ).scalar_one_or_none()
            if not debate:
                return
            config_service = ConfigService(db)
            coze_config = await config_service.get_coze_config()
            coze_parameters = getattr(coze_config, "parameters", None) or {}
            turn_plan = self.resolve_ai_turn_plan(
                segment,
                room_state,
                coze_parameters=coze_parameters,
            )
            recent_speeches = self._load_recent_speeches(
                db,
                debate_uuid,
                limit=self._resolve_recent_speeches_limit(segment, turn_plan),
            )
            await self.prepare_ai_draft(
                room_id=room_id,
                segment=segment,
                room_state=room_state,
                turn_plan=turn_plan,
                db=db,
                debate=debate,
                recent_speeches=recent_speeches,
                speaker_role=speaker_role,
            )
            latest_state = room_manager.get_room_state(room_id)
            if (
                latest_state
                and str(getattr(latest_state, "ai_turn_segment_id", "") or "")
                == segment_id
                and str(getattr(latest_state, "ai_turn_speaker_role", "") or "")
                == speaker_role
            ):
                await room_manager.update_room_state(
                    room_id,
                    ai_turn_status="ready",
                    ai_turn_segment_id=segment_id,
                    ai_turn_segment_title=str(segment.get("title") or ""),
                    ai_turn_speaker_role=speaker_role,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Upcoming AI draft preparation failed for room %s, segment %s: %s",
                room_id,
                segment_id,
                exc,
                exc_info=True,
            )
            latest_state = room_manager.get_room_state(room_id)
            if (
                latest_state
                and str(getattr(latest_state, "ai_turn_segment_id", "") or "")
                == segment_id
                and str(getattr(latest_state, "ai_turn_speaker_role", "") or "")
                == speaker_role
            ):
                await room_manager.update_room_state(
                    room_id,
                    ai_turn_status="idle",
                    ai_turn_segment_id=None,
                    ai_turn_segment_title=None,
                    ai_turn_speaker_role=None,
                )
        finally:
            self._clear_ai_draft_task(
                room_id,
                segment_id=segment_id,
                speaker_role=speaker_role,
            )
            if db is not None:
                db.close()

    async def _sync_upcoming_ai_prethinking(self, room_id: str) -> None:
        room_state = room_manager.get_room_state(room_id)
        keep_keys: List[str] = []
        current_segment_id = str(getattr(room_state, "segment_id", "") or "") if room_state else ""
        current_speaker = str(getattr(room_state, "current_speaker", "") or "") if room_state else ""
        if (
            room_state
            and str(getattr(room_state, "speaker_mode", "") or "") == "fixed"
            and current_segment_id
            and current_speaker.startswith("ai_")
        ):
            keep_keys.append(self._build_ai_draft_key(current_segment_id, current_speaker))
        if not room_state or getattr(room_state, "current_phase", None) in {
            DebatePhase.WAITING,
            DebatePhase.FINISHED,
        }:
            await self._cancel_ai_draft_tasks(room_id, keep_keys=keep_keys)
            if room_state:
                await room_manager.update_room_state(
                    room_id,
                    ai_turn_status="idle",
                    ai_turn_segment_id=None,
                    ai_turn_segment_title=None,
                    ai_turn_speaker_role=None,
                )
            return

        db = None
        target = None
        try:
            if db_module.SessionLocal is None:
                db_module.init_engine()
            db = db_module.SessionLocal()
            config_service = ConfigService(db)
            coze_config = await config_service.get_coze_config()
            coze_parameters = getattr(coze_config, "parameters", None) or {}
            target = self._find_next_eager_ai_segment(
                room_id,
                room_state,
                coze_parameters=coze_parameters,
            )
        except Exception as exc:
            logger.warning(
                "Failed to resolve eager AI prethinking target for room %s: %s",
                room_id,
                exc,
                exc_info=True,
            )
        finally:
            if db is not None:
                db.close()

        if not target:
            await self._cancel_ai_draft_tasks(room_id, keep_keys=keep_keys)
            await room_manager.update_room_state(
                room_id,
                ai_turn_status="idle",
                ai_turn_segment_id=None,
                ai_turn_segment_title=None,
                ai_turn_speaker_role=None,
            )
            return

        segment = target["segment"]
        speaker_role = str(target["speaker_role"] or "")
        turn_plan = target["turn_plan"]
        segment_id = str(segment.get("id") or "")
        draft_key = self._build_ai_draft_key(segment_id, speaker_role)
        await self._cancel_ai_draft_tasks(room_id, keep_keys=keep_keys + [draft_key])

        cached = self._get_ai_draft(
            room_id,
            segment_id=segment_id,
            speaker_role=speaker_role,
        )
        dependency_signature = str(cached.get("dependency_signature") or "") if cached else ""
        if self._is_ai_draft_usable(
            cached,
            turn_plan=turn_plan,
            dependency_signature=dependency_signature,
        ):
            await room_manager.update_room_state(
                room_id,
                ai_turn_status="ready",
                ai_turn_segment_id=segment_id,
                ai_turn_segment_title=str(segment.get("title") or ""),
                ai_turn_speaker_role=speaker_role,
            )
            return

        existing_task = self._get_ai_draft_task(
            room_id,
            segment_id=segment_id,
            speaker_role=speaker_role,
        )
        if existing_task and not existing_task.done():
            await room_manager.update_room_state(
                room_id,
                ai_turn_status="thinking",
                ai_turn_segment_id=segment_id,
                ai_turn_segment_title=str(segment.get("title") or ""),
                ai_turn_speaker_role=speaker_role,
            )
            return

        await room_manager.update_room_state(
            room_id,
            ai_turn_status="thinking",
            ai_turn_segment_id=segment_id,
            ai_turn_segment_title=str(segment.get("title") or ""),
            ai_turn_speaker_role=speaker_role,
        )
        task = asyncio.create_task(
            self._prepare_upcoming_ai_draft(room_id, segment, speaker_role)
        )
        self._store_ai_draft_task(
            room_id,
            segment_id=segment_id,
            speaker_role=speaker_role,
            task=task,
        )

    def is_last_segment(self, room_id: str) -> bool:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return False
        segments = self.get_segments(room_id)
        if not segments:
            return False
        current_index = int(getattr(room_state, "segment_index", 0) or 0)
        current_id = getattr(room_state, "segment_id", None)
        last = segments[-1]
        return current_index == (len(segments) - 1) and str(current_id) == str(
            last.get("id")
        )

    def check_speaking_permission(self, room_id: str, user_id: str, role: str) -> bool:
        """
        检查发言权限

        Args:
            room_id: 房间ID
            user_id: 用户ID
            role: 用户角色

        Returns:
            是否有发言权限
        """
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return False

        if room_state.current_phase == DebatePhase.FREE_DEBATE:
            return role in (room_state.speaker_options or [])

        if role in (room_state.speaker_options or []):
            return True

        return (
            room_state.current_speaker == role or room_state.current_speaker == user_id
        )

    async def set_current_speaker(self, room_id: str, speaker_role: str) -> bool:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return False

        if speaker_role not in (room_state.speaker_options or []):
            return False
        if getattr(room_state, "turn_speech_committed", False):
            return False

        await room_manager.update_room_state(room_id, current_speaker=speaker_role)
        segments = self.get_segments(room_id)
        current_index = int(getattr(room_state, "segment_index", 0) or 0)
        segment = segments[current_index] if current_index < len(segments) else None
        if (
            segment
            and str(speaker_role or "").startswith("ai_")
            and str(segment.get("mode") or "") in {"fixed", "choice"}
        ):
            if room_id in self.ai_tasks:
                task = self.ai_tasks.pop(room_id)
                task.cancel()
            self.ai_tasks[room_id] = asyncio.create_task(
                self._run_ai_turn(room_id, segment)
            )
        await self._sync_upcoming_ai_prethinking(room_id)
        return True

    async def advance_segment(self, room_id: str) -> bool:
        if room_id not in self.segment_index:
            return False

        self.segment_index[room_id] = self.segment_index.get(room_id, 0) + 1
        return await self._apply_current_segment(room_id)

    async def finish_debate_flow(
        self, room_id: str, reason: str = "flow_completed"
    ) -> bool:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return False

        if room_state.current_phase == DebatePhase.FINISHED:
            return True

        logger.info(
            "Finishing debate flow for room %s (reason=%s)",
            room_id,
            reason,
        )
        try:
            if db_module.SessionLocal is None:
                db_module.init_engine()
            if db_module.SessionLocal is None:
                raise RuntimeError("Database session factory is not available")
            db = db_module.SessionLocal()
        except Exception as e:
            logger.error(
                "Unable to finish debate flow for room %s: %s",
                room_id,
                e,
                exc_info=True,
            )
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "debate_end_failed",
                    "data": {
                        "reason": reason,
                        "message": "辩论结束失败，请稍后重试或手动结束",
                        "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                    },
                },
            )
            return False

        try:
            return await room_manager.end_debate(room_id, db)
        except Exception as e:
            logger.error(
                "Failed to finish debate flow for room %s: %s",
                room_id,
                e,
                exc_info=True,
            )
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "debate_end_failed",
                    "data": {
                        "reason": reason,
                        "message": "辩论结束失败，请稍后重试或手动结束",
                        "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                    },
                },
            )
            return False
        finally:
            db.close()

    async def force_advance_segment(self, room_id: str, reason: str = "forced") -> bool:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return False

        if reason != "host_advance":
            turn_processing_status = getattr(
                room_state, "turn_processing_status", "idle"
            )
            turn_processing_kind = getattr(room_state, "turn_processing_kind", None)
            pending_advance_reason = getattr(room_state, "pending_advance_reason", None)
            if turn_processing_status == "processing":
                if not pending_advance_reason:
                    await room_manager.update_room_state(
                        room_id, pending_advance_reason=reason
                    )
                    await websocket_manager.broadcast_to_room(
                        room_id,
                        {
                            "type": "advance_deferred",
                            "data": {
                                "reason": reason,
                                "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                            },
                        },
                    )
                return True
            if turn_processing_status == "failed" and turn_processing_kind:
                await websocket_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "advance_blocked",
                        "data": {
                            "reason": reason,
                            "processing_kind": turn_processing_kind,
                            "processing_error": getattr(
                                room_state, "turn_processing_error", None
                            ),
                            "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                        },
                    },
                )
                return False

        if room_id in self.ai_tasks:
            task = self.ai_tasks.pop(room_id)
            if task is not asyncio.current_task():
                task.cancel()

        if str(getattr(room_state, "playback_gate_status", "idle") or "idle") != "idle":
            await self._clear_playback_gate_state(room_id)

        segments = self.segments.get(room_id) or self._build_default_segments()
        current = (
            segments[room_state.segment_index]
            if room_state.segment_index < len(segments)
            else None
        )
        if not current:
            return await self.advance_segment(room_id)

        await room_manager.update_room_state(
            room_id,
            time_remaining=0,
            segment_time_remaining=0,
        )
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "timer_update",
                "data": {
                    "time_remaining": 0,
                    "phase": room_state.current_phase,
                    "segment_index": room_state.segment_index,
                    "segment_id": room_state.segment_id,
                    "segment_title": room_state.segment_title,
                    "reason": reason,
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )

        return await self.advance_segment(room_id)

    async def advance_to_next_phase(self, room_id: str, reason: str = "forced") -> bool:
        """
        强制跳转到下一个阶段
        
        Args:
            room_id: 房间ID
            reason: 跳转原因
            
        Returns:
            是否成功
        """
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return False
            
        current_phase = room_state.current_phase
        segments = self.segments.get(room_id) or self._build_default_segments()
        current_index = int(getattr(room_state, "segment_index", 0) or 0)
        self.segment_index[room_id] = current_index
        
        # 查找下一个不同阶段的segment
        next_phase_index = -1
        for i in range(current_index + 1, len(segments)):
            if segments[i]["phase"] != current_phase:
                next_phase_index = i
                break
        
        if next_phase_index == -1:
            # 没有找到下一个不同阶段，说明当前是最后一个阶段
            # 不应该直接结束，而是应该执行普通的advance_segment，让用户进入最后一个环节
            return await self.advance_segment(room_id)

        # 取消当前的AI任务和定时器
        if room_id in self.ai_tasks:
            task = self.ai_tasks.pop(room_id)
            if task is not asyncio.current_task():
                task.cancel()
            
        # 更新segment_index
        self.segment_index[room_id] = next_phase_index
        
        # 广播定时器更新（显示时间为0，表示当前段落结束）
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "timer_update",
                "data": {
                    "time_remaining": 0,
                    "phase": room_state.current_phase,
                    "segment_index": room_state.segment_index,
                    "segment_id": room_state.segment_id,
                    "segment_title": room_state.segment_title,
                    "reason": reason,
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )
        
        # 应用新的segment
        return await self._apply_current_segment(room_id)

    async def _apply_current_segment(self, room_id: str) -> bool:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return False

        segments = self.segments.get(room_id) or self._build_default_segments()
        index = self.segment_index.get(room_id, 0)

        if index >= len(segments):
            return await self.finish_debate_flow(room_id, reason="segments_completed")

        segment = segments[index]
        now = (datetime.utcnow() + timedelta(hours=8))
        phase_changed = room_state.current_phase != segment["phase"]

        current_speaker = None
        speaker_options = list(segment.get("speaker_roles") or [])
        if segment.get("mode") in ("fixed", "choice") and speaker_options:
            current_speaker = speaker_options[0]

        await room_manager.update_room_state(
            room_id,
            current_phase=segment["phase"],
            phase_start_time=now if phase_changed else room_state.phase_start_time,
            time_remaining=int(segment["duration"]),
            current_speaker=current_speaker,
            segment_index=index,
            segment_id=str(segment.get("id")),
            segment_title=str(segment.get("title")),
            segment_start_time=now,
            segment_time_remaining=int(segment["duration"]),
            speaker_mode=str(segment.get("mode")),
            speaker_options=speaker_options,
            mic_owner_user_id=None,
            mic_owner_role=None,
            mic_expires_at=None,
            free_debate_next_side=(
                "human"
                if segment.get("phase") == DebatePhase.FREE_DEBATE
                and str(segment.get("mode")) == "free"
                else room_state.free_debate_next_side
            ),
            free_debate_last_side=(
                None
                if segment.get("phase") == DebatePhase.FREE_DEBATE
                and str(segment.get("mode")) == "free"
                else room_state.free_debate_last_side
            ),
            turn_processing_status="idle",
            turn_processing_kind=None,
            turn_processing_error=None,
            turn_speech_committed=False,
            turn_speech_user_id=None,
            turn_speech_role=None,
            turn_speech_timestamp=None,
            pending_advance_reason=None,
            ai_turn_status="idle",
            ai_turn_segment_id=None,
            ai_turn_segment_title=None,
            ai_turn_speaker_role=None,
            playback_gate_status="idle",
            playback_gate_speech_id=None,
            playback_gate_segment_id=None,
            playback_gate_speaker_role=None,
            playback_gate_controller_user_id=None,
            playback_gate_started_at=None,
            playback_gate_deadline_at=None,
            pending_post_playback_action=None,
        )

        if phase_changed:
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "phase_change",
                    "data": {"phase": segment["phase"], "timestamp": now.isoformat()},
                },
            )

        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "segment_change",
                "data": {
                    "segment_index": index,
                    "segment_id": segment.get("id"),
                    "segment_title": segment.get("title"),
                    "phase": segment["phase"],
                    "speaker_mode": segment.get("mode"),
                    "speaker_options": speaker_options,
                    "timestamp": now.isoformat(),
                },
            },
        )
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "timer_update",
                "data": {
                    "time_remaining": int(segment["duration"]),
                    "phase": segment["phase"],
                    "segment_index": index,
                    "segment_id": segment.get("id"),
                    "segment_title": segment.get("title"),
                    "reason": "segment_start",
                    "timestamp": now.isoformat(),
                },
            },
        )
        if room_id in self.ai_tasks:
            task = self.ai_tasks.pop(room_id)
            if task is not asyncio.current_task():
                task.cancel()
        if (
            current_speaker
            and str(current_speaker).startswith("ai_")
            and segment.get("mode") in {"fixed", "choice"}
        ):
            self.ai_tasks[room_id] = asyncio.create_task(
                self._run_ai_turn(room_id, segment)
            )

        await self._sync_upcoming_ai_prethinking(room_id)

        return True

    async def trigger_free_debate_ai_turn(self, room_id: str) -> None:
        """
        触发自由辩论阶段的AI发言
        """
        current_task = asyncio.current_task()
        existing_task = self.ai_tasks.get(room_id)
        if (
            existing_task
            and existing_task is not current_task
            and not existing_task.done()
        ):
            existing_task.cancel()
            try:
                await existing_task
            except asyncio.CancelledError:
                pass
            except RuntimeError:
                pass
        if current_task is not None:
            self.ai_tasks[room_id] = current_task

        db = None
        speaker_role = ""
        segment = self._build_free_debate_segment()
        try:
            room_state = room_manager.get_room_state(room_id)
            if not self._can_prepare_or_release_free_debate_ai(room_state):
                return

            now = self._now()
            if (
                (room_state.mic_owner_user_id or room_state.mic_owner_role)
                and room_state.mic_expires_at
                and now < room_state.mic_expires_at
            ):
                return

            try:
                debate_uuid = uuid.UUID(str(room_state.debate_id))
            except ValueError:
                await self._clear_ai_turn_state(room_id)
                await room_manager.update_room_state(
                    room_id,
                    free_debate_next_side="human",
                )
                return

            if db_module.SessionLocal is None:
                db_module.init_engine()
            db = db_module.SessionLocal()
            debate = db.execute(
                select(Debate).where(Debate.id == debate_uuid)
            ).scalar_one_or_none()
            if not debate:
                await self._clear_ai_turn_state(room_id)
                await room_manager.update_room_state(
                    room_id,
                    free_debate_next_side="human",
                )
                return

            config_service = ConfigService(db)
            coze_config = await config_service.get_coze_config()
            coze_parameters = getattr(coze_config, "parameters", None) or {}
            turn_plan = self.resolve_ai_turn_plan(
                segment,
                room_state,
                coze_parameters=coze_parameters,
            )
            recent_speeches = self._load_recent_speeches(
                db,
                debate_uuid,
                limit=self._resolve_recent_speeches_limit(segment, turn_plan),
            )
            speaker_role = self._select_free_debate_ai_speaker(
                recent_speeches,
                room_state,
            )
            await self._set_ai_turn_state(
                room_id,
                status="thinking",
                segment_id=str(segment.get("id") or ""),
                segment_title=str(segment.get("title") or ""),
                speaker_role=speaker_role,
            )

            draft = await self.prepare_ai_draft(
                room_id=room_id,
                segment=segment,
                room_state=room_state,
                turn_plan=turn_plan,
                db=db,
                debate=debate,
                recent_speeches=recent_speeches,
                speaker_role=speaker_role,
            )
            await self._set_ai_turn_state(
                room_id,
                status="ready",
                segment_id=str(segment.get("id") or ""),
                segment_title=str(segment.get("title") or ""),
                speaker_role=speaker_role,
            )

            latest_state = room_manager.get_room_state(room_id)
            if not self._can_prepare_or_release_free_debate_ai(latest_state):
                await self._clear_ai_turn_state_if_matches(
                    room_id,
                    segment_id=str(segment.get("id") or ""),
                    speaker_role=speaker_role,
                )
                return
            if (
                (latest_state.mic_owner_user_id or latest_state.mic_owner_role)
                and latest_state.mic_expires_at
                and self._now() < latest_state.mic_expires_at
            ):
                await self._clear_ai_turn_state_if_matches(
                    room_id,
                    segment_id=str(segment.get("id") or ""),
                    speaker_role=speaker_role,
                )
                return

            mic_expires_at = self._now() + timedelta(seconds=30)
            await room_manager.update_room_state(
                room_id,
                mic_owner_user_id="__ai__",
                mic_owner_role=speaker_role,
                mic_expires_at=mic_expires_at,
                current_speaker=speaker_role,
            )
            await self._set_ai_turn_state(
                room_id,
                status="speaking",
                segment_id=str(segment.get("id") or ""),
                segment_title=str(segment.get("title") or ""),
                speaker_role=speaker_role,
            )
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "mic_grabbed",
                    "data": {
                        "user_id": "__ai__",
                        "role": speaker_role,
                        "expires_at": mic_expires_at.isoformat(),
                        "timestamp": self._now().isoformat(),
                    },
                },
            )

            latest_state = room_manager.get_room_state(room_id)
            if not latest_state or not self._can_prepare_or_release_free_debate_ai(
                latest_state
            ):
                await self._clear_ai_turn_state_if_matches(
                    room_id,
                    segment_id=str(segment.get("id") or ""),
                    speaker_role=speaker_role,
                )
                return

            await self.release_ai_speech(
                room_id=room_id,
                segment=segment,
                room_state=latest_state,
                draft=draft,
                db=db,
            )

            latest_state = room_manager.get_room_state(room_id)
            if self._is_playback_gate_active(latest_state):
                return
            if latest_state and latest_state.current_phase == DebatePhase.FREE_DEBATE:
                await room_manager.update_room_state(
                    room_id,
                    mic_owner_user_id=None,
                    mic_owner_role=None,
                    mic_expires_at=None,
                    current_speaker=None,
                    free_debate_last_side="ai",
                    free_debate_next_side="human",
                )
                await self._clear_ai_turn_state_if_matches(
                    room_id,
                    segment_id=str(segment.get("id") or ""),
                    speaker_role=speaker_role,
                )
                await websocket_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "mic_released",
                        "data": {
                            "reason": "ai_done",
                            "timestamp": self._now().isoformat(),
                        },
                    },
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "Free debate AI turn error in room %s: %s",
                room_id,
                exc,
                exc_info=True,
            )
            try:
                await room_manager.update_room_state(
                    room_id,
                    mic_owner_user_id=None,
                    mic_owner_role=None,
                    mic_expires_at=None,
                    current_speaker=None,
                    free_debate_next_side="human",
                )
                await self._clear_ai_turn_state_if_matches(
                    room_id,
                    segment_id=str(segment.get("id") or ""),
                    speaker_role=speaker_role or None,
                )
            except Exception:
                pass
        finally:
            if db is not None:
                db.close()
            active_task = self.ai_tasks.get(room_id)
            if active_task is current_task:
                self.ai_tasks.pop(room_id, None)

    async def _run_ai_turn_legacy(self, room_id: str, segment: Dict[str, Any]) -> None:
        conversion_ok = False
        try:
            await asyncio.sleep(0.3)
            room_state = room_manager.get_room_state(room_id)
            if not room_state:
                return
            if room_state.current_phase != segment.get(
                "phase"
            ) or room_state.segment_id != segment.get("id"):
                return
            phase_for_turn = room_state.current_phase
            if phase_for_turn in {
                DebatePhase.OPENING,
                DebatePhase.QUESTIONING,
                DebatePhase.FREE_DEBATE,
                DebatePhase.CLOSING,
            }:
                db_phase_value = str(phase_for_turn.value)
            else:
                db_phase_value = str(
                    (
                        DebatePhase.CLOSING
                        if phase_for_turn == DebatePhase.FINISHED
                        else DebatePhase.OPENING
                    ).value
                )
                logger.warning(
                    f"Coerced speech phase for DB insert: {phase_for_turn} -> {db_phase_value} (room_id={room_id})"
                )
            speaker_role = room_state.current_speaker
            if not speaker_role or not str(speaker_role).startswith("ai_"):
                return
            await room_manager.update_room_state(
                room_id,
                turn_processing_status="processing",
                turn_processing_kind="tts",
                turn_processing_error=None,
                turn_speech_committed=False,
                turn_speech_user_id=None,
                turn_speech_role=str(speaker_role),
                turn_speech_timestamp=None,
            )
            try:
                position = int(str(speaker_role).split("_")[1])
            except Exception:
                await room_manager.update_room_state(
                    room_id,
                    turn_processing_status="failed",
                    turn_processing_kind="tts",
                    turn_processing_error="AI角色解析失败",
                    turn_speech_committed=False,
                )
                return
            try:
                debate_uuid = uuid.UUID(str(room_state.debate_id))
            except ValueError:
                await room_manager.update_room_state(
                    room_id,
                    turn_processing_status="failed",
                    turn_processing_kind="tts",
                    turn_processing_error="辩论ID无效",
                    turn_speech_committed=False,
                )
                return

            if db_module.SessionLocal is None:
                db_module.init_engine()
            db = db_module.SessionLocal()
            try:
                debate = db.execute(
                    select(Debate).where(Debate.id == debate_uuid)
                ).scalar_one_or_none()
                if not debate:
                    return
                recent_speeches = (
                    db.execute(
                        select(Speech)
                        .where(Speech.debate_id == debate_uuid)
                        .order_by(Speech.timestamp.asc())
                        .limit(30)
                    )
                    .scalars()
                    .all()
                )
                context = []
                for s in recent_speeches[-20:]:
                    context.append(
                        {
                            "role": "assistant" if s.speaker_type == "ai" else "user",
                            "content": s.content,
                        }
                    )

                agent = AIDebaterAgent(position=position, db=db)

                speech_type = "free_debate"
                seg_id = str(segment.get("id") or "")
                if phase_for_turn == DebatePhase.OPENING:
                    speech_type = "opening"
                elif phase_for_turn == DebatePhase.CLOSING:
                    speech_type = "closing"
                elif phase_for_turn == DebatePhase.QUESTIONING:
                    if "ask" in seg_id:
                        speech_type = "question"
                    elif "answer" in seg_id:
                        speech_type = "response"
                    else:
                        speech_type = "rebuttal"

                last_human = next(
                    (s for s in reversed(recent_speeches) if s.speaker_type == "human"),
                    None,
                )
                question = last_human.content if last_human else ""

                kwargs = {}
                if speech_type == "response":
                    kwargs["question"] = question
                elif speech_type == "rebuttal":
                    kwargs["opponent_argument"] = question
                elif speech_type == "free_debate":
                    kwargs["recent_speeches"] = [
                        {
                            "speaker": (s.speaker_role or s.speaker_type or "未知"),
                            "content": (s.content or ""),
                        }
                        for s in recent_speeches[-10:]
                    ]

                # 先只生成文本，优先把AI回复同步到前端，音频再异步补齐。
                configured_audio_format = "mp3"
                try:
                    config_service = ConfigService(db)
                    tts_config = await config_service.get_tts_config()
                    configured_audio_format = (
                        tts_config.parameters.get("response_format")
                        if tts_config and tts_config.parameters
                        else None
                    ) or "mp3"
                except Exception:
                    configured_audio_format = "mp3"

                voice_id = agent.get_voice_id()
                current_text = ""
                current_duration = 0
                pending_text_buffer = ""
                stream_text_queue: Optional[asyncio.Queue[Optional[str]]] = None
                speech_timestamp = (datetime.utcnow() + timedelta(hours=8))
                speech = Speech(
                    id=uuid.uuid4(),
                    debate_id=debate_uuid,
                    speaker_id=None,
                    speaker_type="ai",
                    speaker_role=str(speaker_role),
                    phase=db_phase_value,
                    content="",
                    audio_url=None,
                    duration=0,
                    timestamp=speech_timestamp,
                )
                db.add(speech)
                db.commit()

                ai_name = None
                if room_state.ai_debaters:
                    debater_info = next(
                        (
                            item
                            for item in room_state.ai_debaters
                            if item.get("id") == str(speaker_role)
                        ),
                        None,
                    )
                    ai_name = debater_info.get("name") if debater_info else None

                def build_speech_event(
                    current_audio_url: Optional[str],
                    current_audio_status: str,
                    current_audio_format: Optional[str],
                ) -> Dict[str, Any]:
                    """?? speech ????????? speech_id ????????"""
                    return {
                        "speech_id": str(speech.id),
                        "message_id": str(speech.id),
                        "user_id": None,
                        "role": str(speaker_role),
                        "name": ai_name,
                        "stance": "negative",
                        "content": current_text,
                        "audio_url": current_audio_url,
                        "audio_format": current_audio_format,
                        "duration": current_duration,
                        "timestamp": speech_timestamp.isoformat(),
                        "speaker_type": "ai",
                        "audio_status": current_audio_status,
                        "phase": db_phase_value,
                        "segment_id": segment.get("id"),
                        "segment_title": segment.get("title"),
                    }

                async def flush_incremental_text(force: bool = False) -> None:
                    """
                    将 LLM 增量文本按“短句”粒度切片后推给 realtime TTS。
                    避免每个 token 都直接喂给 TTS，导致停顿和断句不自然。
                    """
                    nonlocal current_text
                    nonlocal current_duration
                    nonlocal pending_text_buffer

                    normalized_buffer = (pending_text_buffer or "").strip()
                    if not normalized_buffer:
                        pending_text_buffer = ""
                        return

                    should_flush = force or len(normalized_buffer) >= 24
                    if not should_flush:
                        should_flush = normalized_buffer[-1] in "，。！？；：,.!?;:\n"
                    if not should_flush:
                        return

                    current_text = AIDebaterAgent.limit_reply_text(
                        current_text + normalized_buffer,
                        AIDebaterAgent.MAX_REPLY_CHARS,
                    )
                    current_duration = max(1, int(len(current_text) / 2.5))
                    pending_text_buffer = ""
                    speech.content = current_text
                    speech.duration = current_duration
                    db.commit()
                    await websocket_manager.broadcast_to_room(
                        room_id,
                        {
                            "type": "speech",
                            "data": build_speech_event(
                                None,
                                "processing",
                                configured_audio_format,
                            ),
                        },
                    )
                    if stream_text_queue is not None:
                        await stream_text_queue.put(normalized_buffer)

                async def handle_text_delta(delta_text: str) -> None:
                    """接收 LLM 增量文本，并交给分块器判断是否需要立即刷新。"""
                    nonlocal pending_text_buffer
                    if not delta_text:
                        return
                    pending_text_buffer += delta_text
                    await flush_incremental_text(force=False)

                final_audio_format = configured_audio_format
                audio_data = None
                audio_url = None
                stream_started = False
                stream_chunk_index = 0
                stream_pcm_sample_rate = voice_processor.REALTIME_PCM_SAMPLE_RATE
                stream_pcm_channels = voice_processor.REALTIME_PCM_CHANNELS
                stream_pcm_sample_width = voice_processor.REALTIME_PCM_SAMPLE_WIDTH
                stream_result: Dict[str, Any] = {}

                async def broadcast_stream_chunk(audio_chunk: bytes) -> None:
                    """
                    realtime TTS每吐出一个PCM chunk，就立即转发给前端。
                    前端据此边收边播，避免整段TTS的额外等待。
                    """
                    nonlocal stream_started
                    nonlocal stream_chunk_index

                    if not stream_started:
                        stream_started = True
                        await websocket_manager.broadcast_to_room(
                            room_id,
                            {
                                "type": "tts_stream_start",
                                "data": {
                                    "speech_id": str(speech.id),
                                    "message_id": str(speech.id),
                                    "role": str(speaker_role),
                                    "name": ai_name,
                                    "timestamp": speech_timestamp.isoformat(),
                                    "audio_format": "pcm_s16le",
                                    "sample_rate": stream_pcm_sample_rate,
                                    "channels": stream_pcm_channels,
                                    "sample_width": stream_pcm_sample_width,
                                },
                            },
                        )

                    stream_chunk_index += 1
                    await websocket_manager.broadcast_to_room(
                        room_id,
                        {
                            "type": "tts_stream_chunk",
                            "data": {
                                "speech_id": str(speech.id),
                                "message_id": str(speech.id),
                                "chunk_index": stream_chunk_index,
                                "audio_base64": voice_processor.encode_audio_base64(
                                    audio_chunk
                                ),
                                "audio_format": "pcm_s16le",
                                "sample_rate": stream_pcm_sample_rate,
                                "channels": stream_pcm_channels,
                                "sample_width": stream_pcm_sample_width,
                                "timestamp": (
                                    datetime.utcnow() + timedelta(hours=8)
                                ).isoformat(),
                            },
                        },
                    )

                # 语速改为走后台配置，管理端更新后这里会自动生效。
                async def iter_live_tts_text() -> AsyncIterator[str]:
                    """把已切好的文本片段持续提供给 realtime TTS 会话。"""
                    assert stream_text_queue is not None
                    while True:
                        text_chunk = await stream_text_queue.get()
                        if text_chunk is None:
                            break
                        yield text_chunk

                stream_text_queue = asyncio.Queue()
                tts_task = asyncio.create_task(
                    voice_processor.synthesize_speech_stream_live(
                        text_source=iter_live_tts_text(),
                        voice_id=voice_id,
                        speed=None,
                        db=db,
                        on_chunk=broadcast_stream_chunk,
                    )
                )

                result: Dict[str, Any] = {}
                try:
                    result = await agent.generate_speech_with_audio(
                        speech_type=speech_type,
                        topic=debate.topic,
                        stance="negative",
                        context=context,
                        include_audio=False,
                        stream_callback=handle_text_delta,
                        **kwargs,
                    )
                finally:
                    await flush_incremental_text(force=True)
                    await stream_text_queue.put(None)

                text = (result.get("text") or current_text).strip()
                text = AIDebaterAgent.limit_reply_text(
                    text, AIDebaterAgent.MAX_REPLY_CHARS
                )
                if not text:
                    text = "[AI暂时无法回应]"

                # 如果流式阶段和最终文本存在差异，这里补齐剩余文本，保证入库与TTS一致。
                if text != current_text:
                    if text.startswith(current_text):
                        pending_text_buffer += text[len(current_text):]
                        await flush_incremental_text(force=True)
                    elif not current_text:
                        pending_text_buffer = text
                        await flush_incremental_text(force=True)
                    else:
                        current_text = text
                        current_duration = max(1, int(len(current_text) / 2.5))
                        speech.content = current_text
                        speech.duration = current_duration
                        db.commit()
                        await websocket_manager.broadcast_to_room(
                            room_id,
                            {
                                "type": "speech",
                                "data": build_speech_event(
                                    None,
                                    "processing",
                                    configured_audio_format,
                                ),
                            },
                        )

                text = current_text or text
                duration = max(1, int(len(text) / 2.5))
                speech.content = text
                speech.duration = duration
                db.commit()
                voice_id = result.get("voice_id") or voice_id

                try:
                    stream_result = await tts_task
                except Exception as exc:
                    logger.warning(f"AI live realtime TTS failed: {exc}", exc_info=True)
                    stream_result = {
                        "audio_data": None,
                        "audio_format": None,
                        "chunk_count": 0,
                        "used_streaming": False,
                        "error": str(exc),
                    }

                if stream_result.get("used_streaming"):
                    stream_pcm_sample_rate = int(
                        stream_result.get("sample_rate")
                        or voice_processor.REALTIME_PCM_SAMPLE_RATE
                    )
                    stream_pcm_channels = int(
                        stream_result.get("channels")
                        or voice_processor.REALTIME_PCM_CHANNELS
                    )
                    stream_pcm_sample_width = int(
                        stream_result.get("sample_width")
                        or voice_processor.REALTIME_PCM_SAMPLE_WIDTH
                    )
                    audio_data = stream_result.get("audio_data")
                    final_audio_format = (
                        stream_result.get("audio_format") or "wav"
                    )

                # realtime不可用时保留整段TTS兜底，避免其它配置直接失效。
                if not audio_data:
                    # realtime 不可用时，也沿用同一语速兜底，避免听感前后不一致。
                    try:
                        fallback_tts_started_at = time.perf_counter()
                        logger.info(
                            "TTS性能日志-整段兜底请求开始: %s",
                            json.dumps(
                                {
                                    "room_id": room_id,
                                    "speaker_role": str(speaker_role),
                                    "request_content": text,
                                },
                                ensure_ascii=False,
                            ),
                        )
                        audio_data = await voice_processor.synthesize_speech(
                            text=text,
                            voice_id=voice_id,
                            # realtime 不可用时仍沿用后台语速配置，保证兜底链路听感一致。
                            speed=None,
                            db=db,
                        )
                        logger.info(
                            "TTS性能日志-整段兜底请求完成: %s",
                            json.dumps(
                                {
                                    "room_id": room_id,
                                    "speaker_role": str(speaker_role),
                                    "request_content": text,
                                    "all_content_elapsed_seconds": f"{(time.perf_counter() - fallback_tts_started_at):.2f}",
                                },
                                ensure_ascii=False,
                            ),
                        )
                    except Exception as exc:
                        logger.warning(f"AI TTS fallback failed: {exc}", exc_info=True)
                        audio_data = None

                if audio_data:
                    for _ in range(2):
                        try:
                            audio_filename = (
                                f"{room_id}_{speaker_role}_"
                                f"{int((datetime.utcnow() + timedelta(hours=8)).timestamp() * 1000)}."
                                f"{final_audio_format}"
                            )
                            audio_path = await voice_processor.save_audio_file(
                                audio_data, audio_filename
                            )
                            audio_url = voice_processor.build_audio_url(audio_path)
                            if audio_url:
                                break
                        except Exception as exc:
                            logger.warning(
                                f"AI audio save failed: {exc}", exc_info=True
                            )

                conversion_ok = bool(audio_url)
                if conversion_ok:
                    speech.audio_url = audio_url
                    speech.duration = int(duration)
                    db.commit()
                    await room_manager.update_room_state(
                        room_id,
                        turn_processing_status="succeeded",
                        turn_processing_kind="tts",
                        turn_processing_error=None,
                        turn_speech_committed=True,
                        turn_speech_user_id=None,
                        turn_speech_role=str(speaker_role),
                        turn_speech_timestamp=(datetime.utcnow() + timedelta(hours=8)),
                    )
                    await websocket_manager.broadcast_to_room(
                        room_id,
                        {
                            "type": "speech",
                            "data": build_speech_event(
                                audio_url,
                                "completed",
                                final_audio_format,
                            ),
                        },
                    )
                else:
                    err = (
                        stream_result.get("error")
                        or result.get("error")
                        or "语音合成失败"
                    )
                    await room_manager.update_room_state(
                        room_id,
                        turn_processing_status="succeeded",
                        turn_processing_kind="tts",
                        turn_processing_error=str(err),
                        turn_speech_committed=True,
                        turn_speech_user_id=None,
                        turn_speech_role=str(speaker_role),
                        turn_speech_timestamp=(datetime.utcnow() + timedelta(hours=8)),
                    )

                if stream_started:
                    await websocket_manager.broadcast_to_room(
                        room_id,
                        {
                            "type": "tts_stream_end",
                            "data": {
                                "speech_id": str(speech.id),
                                "message_id": str(speech.id),
                                "audio_url": audio_url,
                                "audio_status": (
                                    "completed" if conversion_ok else "failed"
                                ),
                                "audio_format": final_audio_format,
                                "sample_rate": stream_pcm_sample_rate,
                                "channels": stream_pcm_channels,
                                "sample_width": stream_pcm_sample_width,
                                "timestamp": (
                                    datetime.utcnow() + timedelta(hours=8)
                                ).isoformat(),
                            },
                        },
                    )
            finally:
                db.close()

            if room_state.current_phase == DebatePhase.FREE_DEBATE:
                await room_manager.update_room_state(
                    room_id,
                    mic_owner_user_id=None,
                    mic_owner_role=None,
                    mic_expires_at=None,
                    current_speaker=None,
                    free_debate_last_side="ai",
                    free_debate_next_side="human",
                )
                await websocket_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "mic_released",
                        "data": {
                            "reason": "ai_done",
                            "timestamp": (
                                datetime.utcnow() + timedelta(hours=8)
                            ).isoformat(),
                        },
                    },
                )
                return

            if conversion_ok or room_state.current_phase != DebatePhase.FREE_DEBATE:
                await self.advance_segment(room_id)
        except asyncio.CancelledError:
            return
        except Exception as e:
            try:
                await room_manager.update_room_state(
                    room_id,
                    turn_processing_status="failed",
                    turn_processing_kind="tts",
                    turn_processing_error=str(e),
                    turn_speech_committed=False,
                )
            except Exception:
                pass
            logger.error(f"AI turn error in room {room_id}: {e}", exc_info=True)

    async def prepare_ai_draft(
        self,
        room_id: str,
        segment: Dict[str, Any],
        room_state: Any,
        turn_plan: Dict[str, Any],
        db: Any,
        debate: Debate,
        recent_speeches: List[Speech],
        speaker_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        speaker_role = str(speaker_role or room_state.current_speaker or "")
        segment_id = str(segment.get("id") or "")
        dependency_signature = self._build_turn_dependency_signature(
            turn_plan,
            recent_speeches,
            speaker_role,
            segment_id=segment_id,
        )
        dependency_speeches = self._collect_dependency_speeches(
            segment_id,
            turn_plan,
            recent_speeches,
            speaker_role,
        )
        cached = self._get_ai_draft(
            room_id,
            segment_id=segment_id,
            speaker_role=speaker_role,
        )
        if self._is_ai_draft_usable(
            cached,
            turn_plan=turn_plan,
            dependency_signature=dependency_signature,
        ):
            return dict(cached)
        if cached and cached.get("status") == "ready":
            self._mark_ai_draft_invalidated(
                room_id,
                cached,
                reason="dependency_changed_or_expired",
            )
        existing_task = self._get_ai_draft_task(
            room_id,
            segment_id=segment_id,
            speaker_role=speaker_role,
        )
        current_task = asyncio.current_task()
        if existing_task and existing_task is not current_task and not existing_task.done():
            try:
                await existing_task
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            cached = self._get_ai_draft(
                room_id,
                segment_id=segment_id,
                speaker_role=speaker_role,
            )
            if self._is_ai_draft_usable(
                cached,
                turn_plan=turn_plan,
                dependency_signature=dependency_signature,
            ):
                return dict(cached)

        draft = self._build_empty_ai_draft(
            room_id=room_id,
            segment_id=segment_id,
            segment_title=segment.get("title"),
            speaker_role=speaker_role,
            speech_type=str(turn_plan.get("speech_type") or "free_debate"),
            dependency_scope=str(turn_plan.get("dependency_scope") or "recent_speeches"),
        )
        draft["status"] = "preparing"
        draft["dependency_signature"] = dependency_signature
        draft["source_speech_ids"] = [
            str(getattr(speech, "id", ""))
            for speech in dependency_speeches
        ]
        draft["error"] = None
        self._store_ai_draft(room_id, draft)

        position = int(speaker_role.split("_")[1])
        agent = AIDebaterAgent(position=position, db=db)
        configured_audio_format = "mp3"
        try:
            config_service = ConfigService(db)
            tts_config = await config_service.get_tts_config()
            configured_audio_format = (
                tts_config.parameters.get("response_format")
                if tts_config and tts_config.parameters
                else None
            ) or "mp3"
        except Exception:
            configured_audio_format = "mp3"

        generation_kwargs = self._build_generation_kwargs(
            turn_plan,
            recent_speeches,
            speaker_role,
            segment_id=segment_id,
        )
        try:
            result = await asyncio.wait_for(
                agent.generate_speech_with_audio(
                    speech_type=str(turn_plan.get("speech_type") or "free_debate"),
                    topic=str(debate.topic or ""),
                    stance=self._resolve_ai_stance(room_state, speaker_role),
                    context=self._build_llm_context(recent_speeches),
                    include_audio=False,
                    **generation_kwargs,
                ),
                timeout=self._coerce_nonnegative_float(
                    turn_plan.get("thinking_timeout_sec"),
                    20.0,
                ),
            )
        except Exception as exc:
            draft["status"] = "failed"
            draft["error"] = str(exc)
            self._store_ai_draft(room_id, draft)
            raise

        text = AIDebaterAgent.limit_reply_text(
            str(result.get("text") or "").strip(),
            AIDebaterAgent.MAX_REPLY_CHARS,
        )
        if not text:
            text = "[AI暂时无法回应]"

        ready_at = self._now()
        release_not_before = (
            self._build_segment_release_not_before(room_state, turn_plan)
            if self._is_room_segment_active(room_id, segment)
            else None
        )
        draft.update(
            {
                "status": "ready",
                "draft_text": text,
                "voice_id": result.get("voice_id") or agent.get_voice_id(),
                "configured_audio_format": configured_audio_format,
                "ready_at": ready_at,
                "release_not_before": release_not_before,
                "error": result.get("error"),
            }
        )
        self._store_ai_draft(room_id, draft)
        return dict(draft)

    async def release_ai_speech(
        self,
        room_id: str,
        segment: Dict[str, Any],
        room_state: Any,
        draft: Dict[str, Any],
        db: Any,
    ) -> bool:
        if not self._is_room_segment_active(room_id, segment):
            return False

        phase_for_turn = room_state.current_phase
        if phase_for_turn in {
            DebatePhase.OPENING,
            DebatePhase.QUESTIONING,
            DebatePhase.FREE_DEBATE,
            DebatePhase.CLOSING,
        }:
            db_phase_value = str(phase_for_turn.value)
        else:
            db_phase_value = str(
                (
                    DebatePhase.CLOSING
                    if phase_for_turn == DebatePhase.FINISHED
                    else DebatePhase.OPENING
                ).value
            )
            logger.warning(
                "Coerced speech phase for DB insert: %s -> %s (room_id=%s)",
                phase_for_turn,
                db_phase_value,
                room_id,
            )

        speaker_role = str(draft.get("speaker_role") or room_state.current_speaker or "")
        text = str(draft.get("draft_text") or "").strip() or "[AI暂时无法回应]"
        duration = max(1, int(len(text) / 2.5))
        speech_timestamp = self._now()
        ai_name = self._resolve_ai_name(room_state, speaker_role)
        stance = self._resolve_ai_stance(room_state, speaker_role)
        configured_audio_format = str(draft.get("configured_audio_format") or "mp3")
        final_audio_format = configured_audio_format
        voice_id = str(draft.get("voice_id") or "")

        await room_manager.update_room_state(
            room_id,
            turn_processing_status="processing",
            turn_processing_kind="tts",
            turn_processing_error=None,
            turn_speech_committed=False,
            turn_speech_user_id=None,
            turn_speech_role=speaker_role,
            turn_speech_timestamp=None,
        )
        await self._set_ai_turn_state(
            room_id,
            status="speaking",
            segment_id=str(segment.get("id") or ""),
            segment_title=str(segment.get("title") or ""),
            speaker_role=speaker_role,
        )

        speech = Speech(
            id=uuid.uuid4(),
            debate_id=uuid.UUID(str(room_state.debate_id)),
            speaker_id=None,
            speaker_type="ai",
            speaker_role=speaker_role,
            phase=db_phase_value,
            content=text,
            audio_url=None,
            duration=duration,
            timestamp=speech_timestamp,
        )
        db.add(speech)
        db.commit()

        def build_speech_event(
            current_audio_url: Optional[str],
            current_audio_status: str,
            current_audio_format: Optional[str],
        ) -> Dict[str, Any]:
            return {
                "speech_id": str(speech.id),
                "message_id": str(speech.id),
                "user_id": None,
                "role": speaker_role,
                "name": ai_name,
                "stance": stance,
                "content": text,
                "audio_url": current_audio_url,
                "audio_format": current_audio_format,
                "duration": duration,
                "timestamp": speech_timestamp.isoformat(),
                "speaker_type": "ai",
                "audio_status": current_audio_status,
                "phase": db_phase_value,
                "segment_id": segment.get("id"),
                "segment_title": segment.get("title"),
            }

        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "speech",
                "data": build_speech_event(
                    None,
                    "processing",
                    configured_audio_format,
                ),
            },
        )

        stream_started = False
        stream_chunk_index = 0
        stream_pcm_sample_rate = voice_processor.REALTIME_PCM_SAMPLE_RATE
        stream_pcm_channels = voice_processor.REALTIME_PCM_CHANNELS
        stream_pcm_sample_width = voice_processor.REALTIME_PCM_SAMPLE_WIDTH
        audio_data = None
        audio_url = None
        playback_gate_started = False
        playback_post_action = (
            "release_mic"
            if room_state.current_phase == DebatePhase.FREE_DEBATE
            else "advance_segment"
        )

        async def ensure_playback_gate_started() -> None:
            nonlocal playback_gate_started
            if playback_gate_started:
                return
            playback_gate_started = await self._start_playback_gate(
                room_id,
                speech_id=str(speech.id),
                segment_id=str(segment.get("id") or ""),
                speaker_role=speaker_role,
                duration_sec=duration,
                post_action=playback_post_action,
            )

        async def broadcast_stream_chunk(audio_chunk: bytes) -> None:
            nonlocal stream_started
            nonlocal stream_chunk_index

            if not stream_started:
                stream_started = True
                await ensure_playback_gate_started()
                await websocket_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "tts_stream_start",
                        "data": {
                            "speech_id": str(speech.id),
                            "message_id": str(speech.id),
                            "role": speaker_role,
                            "name": ai_name,
                            "timestamp": speech_timestamp.isoformat(),
                            "audio_format": "pcm_s16le",
                            "sample_rate": stream_pcm_sample_rate,
                            "channels": stream_pcm_channels,
                            "sample_width": stream_pcm_sample_width,
                        },
                    },
                )

            stream_chunk_index += 1
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "tts_stream_chunk",
                    "data": {
                        "speech_id": str(speech.id),
                        "message_id": str(speech.id),
                        "chunk_index": stream_chunk_index,
                        "audio_base64": voice_processor.encode_audio_base64(audio_chunk),
                        "audio_format": "pcm_s16le",
                        "sample_rate": stream_pcm_sample_rate,
                        "channels": stream_pcm_channels,
                        "sample_width": stream_pcm_sample_width,
                        "timestamp": self._now().isoformat(),
                    },
                },
            )

        async def iter_live_tts_text() -> AsyncIterator[str]:
            yield text

        try:
            stream_result = await voice_processor.synthesize_speech_stream_live(
                text_source=iter_live_tts_text(),
                voice_id=voice_id,
                speed=None,
                db=db,
                on_chunk=broadcast_stream_chunk,
            )
        except Exception as exc:
            logger.warning(f"AI live realtime TTS failed: {exc}", exc_info=True)
            stream_result = {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": 0,
                "used_streaming": False,
                "error": str(exc),
            }

        if stream_result.get("used_streaming"):
            stream_pcm_sample_rate = int(
                stream_result.get("sample_rate")
                or voice_processor.REALTIME_PCM_SAMPLE_RATE
            )
            stream_pcm_channels = int(
                stream_result.get("channels")
                or voice_processor.REALTIME_PCM_CHANNELS
            )
            stream_pcm_sample_width = int(
                stream_result.get("sample_width")
                or voice_processor.REALTIME_PCM_SAMPLE_WIDTH
            )
            audio_data = stream_result.get("audio_data")
            final_audio_format = str(stream_result.get("audio_format") or "wav")

        if not audio_data:
            try:
                fallback_tts_started_at = time.perf_counter()
                logger.info(
                    "TTS性能日志-整段兜底请求开始: %s",
                    json.dumps(
                        {
                            "room_id": room_id,
                            "speaker_role": speaker_role,
                            "request_content": text,
                        },
                        ensure_ascii=False,
                    ),
                )
                audio_data = await voice_processor.synthesize_speech(
                    text=text,
                    voice_id=voice_id,
                    speed=None,
                    db=db,
                )
                logger.info(
                    "TTS性能日志-整段兜底请求完成: %s",
                    json.dumps(
                        {
                            "room_id": room_id,
                            "speaker_role": speaker_role,
                            "request_content": text,
                            "all_content_elapsed_seconds": f"{(time.perf_counter() - fallback_tts_started_at):.2f}",
                        },
                        ensure_ascii=False,
                    ),
                )
            except Exception as exc:
                logger.warning(f"AI TTS fallback failed: {exc}", exc_info=True)
                audio_data = None

        if audio_data:
            for _ in range(2):
                try:
                    audio_filename = (
                        f"{room_id}_{speaker_role}_"
                        f"{int(self._now().timestamp() * 1000)}."
                        f"{final_audio_format}"
                    )
                    audio_path = await voice_processor.save_audio_file(
                        audio_data,
                        audio_filename,
                    )
                    audio_url = voice_processor.build_audio_url(audio_path)
                    if audio_url:
                        break
                except Exception as exc:
                    logger.warning(f"AI audio save failed: {exc}", exc_info=True)

        conversion_ok = bool(audio_url)
        if conversion_ok:
            speech.audio_url = audio_url
            speech.duration = duration
            db.commit()
            if not stream_started:
                await ensure_playback_gate_started()
            await room_manager.update_room_state(
                room_id,
                turn_processing_status="succeeded",
                turn_processing_kind="tts",
                turn_processing_error=None,
                turn_speech_committed=True,
                turn_speech_user_id=None,
                turn_speech_role=speaker_role,
                turn_speech_timestamp=self._now(),
            )
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "speech",
                    "data": build_speech_event(
                        audio_url,
                        "completed",
                        final_audio_format,
                    ),
                },
            )
        else:
            err = (
                stream_result.get("error")
                or draft.get("error")
                or "语音合成失败"
            )
            await room_manager.update_room_state(
                room_id,
                turn_processing_status="succeeded",
                turn_processing_kind="tts",
                turn_processing_error=str(err),
                turn_speech_committed=True,
                turn_speech_user_id=None,
                turn_speech_role=speaker_role,
                turn_speech_timestamp=self._now(),
            )

        if stream_started:
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "tts_stream_end",
                    "data": {
                        "speech_id": str(speech.id),
                        "message_id": str(speech.id),
                        "audio_url": audio_url,
                        "audio_status": "completed" if conversion_ok else "failed",
                        "audio_format": final_audio_format,
                        "sample_rate": stream_pcm_sample_rate,
                        "channels": stream_pcm_channels,
                        "sample_width": stream_pcm_sample_width,
                        "timestamp": self._now().isoformat(),
                    },
                },
            )

        cached = self._get_ai_draft(
            room_id,
            segment_id=str(segment.get("id") or ""),
            speaker_role=speaker_role,
        )
        if cached:
            cached["status"] = "released"
            cached["released_at"] = self._now()
            cached["speech_id"] = str(speech.id)
            self._store_ai_draft(room_id, cached)

        await self.notify_speech_committed(
            room_id,
            speech_id=str(speech.id),
            speaker_role=speaker_role,
            segment_id=str(segment.get("id") or ""),
        )

        return conversion_ok

    async def run_ai_turn(self, room_id: str, segment: Dict[str, Any]) -> None:
        conversion_ok = False
        turn_processing_kind = "llm"
        try:
            await asyncio.sleep(0.3)
            room_state = room_manager.get_room_state(room_id)
            if not room_state or not self._is_room_segment_active(room_id, segment):
                return

            speaker_role = str(room_state.current_speaker or "")
            if not speaker_role.startswith("ai_"):
                return

            await self._set_ai_turn_state(
                room_id,
                status="thinking",
                segment_id=str(segment.get("id") or ""),
                segment_title=str(segment.get("title") or ""),
                speaker_role=speaker_role,
            )
            await room_manager.update_room_state(
                room_id,
                turn_processing_status="processing",
                turn_processing_kind=turn_processing_kind,
                turn_processing_error=None,
                turn_speech_committed=False,
                turn_speech_user_id=None,
                turn_speech_role=speaker_role,
                turn_speech_timestamp=None,
            )

            try:
                int(speaker_role.split("_")[1])
            except Exception:
                await self._clear_ai_turn_state(room_id)
                await room_manager.update_room_state(
                    room_id,
                    turn_processing_status="failed",
                    turn_processing_kind=turn_processing_kind,
                    turn_processing_error="AI角色解析失败",
                    turn_speech_committed=False,
                )
                return

            try:
                debate_uuid = uuid.UUID(str(room_state.debate_id))
            except ValueError:
                await self._clear_ai_turn_state(room_id)
                await room_manager.update_room_state(
                    room_id,
                    turn_processing_status="failed",
                    turn_processing_kind=turn_processing_kind,
                    turn_processing_error="辩论ID无效",
                    turn_speech_committed=False,
                )
                return

            if db_module.SessionLocal is None:
                db_module.init_engine()
            db = db_module.SessionLocal()
            try:
                debate = db.execute(
                    select(Debate).where(Debate.id == debate_uuid)
                ).scalar_one_or_none()
                if not debate:
                    await self._clear_ai_turn_state(room_id)
                    await room_manager.update_room_state(
                        room_id,
                        turn_processing_status="failed",
                        turn_processing_kind=turn_processing_kind,
                        turn_processing_error="辩论不存在",
                        turn_speech_committed=False,
                    )
                    return

                config_service = ConfigService(db)
                coze_config = await config_service.get_coze_config()
                coze_parameters = getattr(coze_config, "parameters", None) or {}
                turn_plan = self.resolve_ai_turn_plan(
                    segment,
                    room_state,
                    coze_parameters=coze_parameters,
                )
                recent_speeches = self._load_recent_speeches(
                    db,
                    debate_uuid,
                    limit=self._resolve_recent_speeches_limit(segment, turn_plan),
                )
                dependency_speeches = self._collect_dependency_speeches(
                    str(segment.get("id") or ""),
                    turn_plan,
                    recent_speeches,
                    speaker_role,
                )
                if self._should_skip_ai_turn_without_dependency(
                    str(segment.get("id") or ""),
                    turn_plan,
                    dependency_speeches,
                ):
                    await self._skip_ai_turn_due_to_missing_dependency(
                        room_id,
                        segment=segment,
                        speaker_role=speaker_role,
                    )
                    return
                draft = await self.prepare_ai_draft(
                    room_id=room_id,
                    segment=segment,
                    room_state=room_state,
                    turn_plan=turn_plan,
                    db=db,
                    debate=debate,
                    recent_speeches=recent_speeches,
                )
                await self._set_ai_turn_state(
                    room_id,
                    status="ready",
                    segment_id=str(segment.get("id") or ""),
                    segment_title=str(segment.get("title") or ""),
                    speaker_role=speaker_role,
                )

                latest_state = room_manager.get_room_state(room_id)
                if not latest_state or not self._is_room_segment_active(room_id, segment):
                    return
                release_not_before = self._build_segment_release_not_before(
                    latest_state,
                    turn_plan,
                )
                cached = self._get_ai_draft(
                    room_id,
                    segment_id=str(segment.get("id") or ""),
                    speaker_role=speaker_role,
                )
                if cached:
                    cached["release_not_before"] = release_not_before
                    self._store_ai_draft(room_id, cached)
                if isinstance(release_not_before, datetime):
                    remaining = (release_not_before - self._now()).total_seconds()
                    if remaining > 0:
                        await asyncio.sleep(remaining)

                latest_state = room_manager.get_room_state(room_id)
                if not latest_state or not self._is_room_segment_active(room_id, segment):
                    return

                turn_processing_kind = "tts"
                conversion_ok = await self.release_ai_speech(
                    room_id=room_id,
                    segment=segment,
                    room_state=latest_state,
                    draft=draft,
                    db=db,
                )
            finally:
                db.close()

            latest_state = room_manager.get_room_state(room_id)
            if not latest_state:
                return

            if latest_state.current_phase == DebatePhase.FREE_DEBATE:
                if self._is_playback_gate_active(latest_state):
                    return
                await room_manager.update_room_state(
                    room_id,
                    mic_owner_user_id=None,
                    mic_owner_role=None,
                    mic_expires_at=None,
                    current_speaker=None,
                    free_debate_last_side="ai",
                    free_debate_next_side="human",
                )
                await self._clear_ai_turn_state_if_matches(
                    room_id,
                    segment_id=str(segment.get("id") or ""),
                    speaker_role=speaker_role,
                )
                await websocket_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "mic_released",
                        "data": {
                            "reason": "ai_done",
                            "timestamp": self._now().isoformat(),
                        },
                    },
                )
                return

            if self._is_playback_gate_active(latest_state):
                return

            if conversion_ok or latest_state.current_phase != DebatePhase.FREE_DEBATE:
                await self.advance_segment(room_id)
        except asyncio.CancelledError:
            return
        except Exception as e:
            try:
                await self._clear_ai_turn_state(room_id)
                await room_manager.update_room_state(
                    room_id,
                    turn_processing_status="failed",
                    turn_processing_kind=turn_processing_kind,
                    turn_processing_error=str(e),
                    turn_speech_committed=False,
                )
            except Exception:
                pass
            logger.error(f"AI turn error in room {room_id}: {e}", exc_info=True)

    async def _run_ai_turn(self, room_id: str, segment: Dict[str, Any]) -> None:
        await self.run_ai_turn(room_id, segment)

    async def start_timer(self, room_id: str) -> None:
        """
        启动定时器

        Args:
            room_id: 房间ID
        """
        # 停止现有定时器
        await self.stop_timer(room_id)

        # 创建新的定时器任务
        task = asyncio.create_task(self._timer_loop(room_id))
        self.timer_tasks[room_id] = task

        logger.info(f"Started timer for room {room_id}")

    async def stop_timer(self, room_id: str) -> None:
        """
        停止定时器

        Args:
            room_id: 房间ID
        """
        if room_id in self.timer_tasks:
            task = self.timer_tasks[room_id]
            if task is asyncio.current_task():
                del self.timer_tasks[room_id]
                logger.info(f"Stopped timer for room {room_id} from current task")
                return
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except RuntimeError:
                pass
            del self.timer_tasks[room_id]

            logger.info(f"Stopped timer for room {room_id}")

    async def _timer_loop(self, room_id: str) -> None:
        """
        定时器循环

        Args:
            room_id: 房间ID
        """
        try:
            while True:
                room_state = room_manager.get_room_state(room_id)
                if not room_state:
                    break

                if await self._refresh_playback_controller_if_needed(room_id):
                    room_state = room_manager.get_room_state(room_id)
                    if not room_state:
                        break

                if self._is_playback_gate_active(room_state):
                    deadline_at = getattr(room_state, "playback_gate_deadline_at", None)
                    if isinstance(deadline_at, datetime) and self._now() >= deadline_at:
                        await self._finalize_playback_gate(room_id, status="timeout")
                        continue

                if room_state.segment_start_time:
                    if (
                        room_state.current_phase == DebatePhase.FREE_DEBATE
                        and room_state.mic_expires_at
                    ):
                        if (datetime.utcnow() + timedelta(hours=8)) >= room_state.mic_expires_at:
                            expired_owner_role = str(
                                getattr(room_state, "mic_owner_role", "") or ""
                            )
                            next_side = "human"
                            last_side = getattr(room_state, "free_debate_last_side", None)
                            should_trigger_ai = False
                            if expired_owner_role.startswith("debater_"):
                                next_side = "ai"
                                last_side = "human"
                                should_trigger_ai = True
                            elif expired_owner_role.startswith("ai_"):
                                next_side = "human"
                                last_side = "ai"
                            await room_manager.update_room_state(
                                room_id,
                                mic_owner_user_id=None,
                                mic_owner_role=None,
                                mic_expires_at=None,
                                current_speaker=None,
                                free_debate_last_side=last_side,
                                free_debate_next_side=next_side,
                            )
                            if expired_owner_role.startswith("ai_"):
                                await self._clear_ai_turn_state_if_matches(
                                    room_id,
                                    segment_id=str(getattr(room_state, "segment_id", "") or ""),
                                    speaker_role=expired_owner_role,
                                )
                            await websocket_manager.broadcast_to_room(
                                room_id,
                                {
                                    "type": "mic_released",
                                    "data": {
                                        "reason": "expired",
                                        "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                                    },
                                },
                            )
                            if should_trigger_ai:
                                asyncio.create_task(
                                    self.trigger_free_debate_ai_turn(room_id)
                                )
                    segments = (
                        self.segments.get(room_id) or self._build_default_segments()
                    )
                    segment = (
                        segments[room_state.segment_index]
                        if room_state.segment_index < len(segments)
                        else None
                    )
                    if segment:
                        elapsed = (
                            (datetime.utcnow() + timedelta(hours=8)) - room_state.segment_start_time
                        ).total_seconds()
                        time_remaining = max(0, int(segment["duration"]) - int(elapsed))
                        await room_manager.update_room_state(
                            room_id,
                            time_remaining=time_remaining,
                            segment_time_remaining=time_remaining,
                        )
                        await websocket_manager.broadcast_to_room(
                            room_id,
                            {
                                "type": "timer_update",
                                "data": {
                                    "time_remaining": time_remaining,
                                    "phase": room_state.current_phase,
                                    "segment_index": room_state.segment_index,
                                    "segment_id": room_state.segment_id,
                                    "segment_title": room_state.segment_title,
                                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                                },
                            },
                        )
                        if time_remaining <= 0:
                            await self.handle_segment_timeout(room_id)
                            continue

                # 每秒更新一次
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info(f"Timer cancelled for room {room_id}")
        except Exception as e:
            logger.error(f"Timer error for room {room_id}: {e}", exc_info=True)

    async def handle_segment_timeout(self, room_id: str) -> None:
        """
        处理段落超时

        Args:
            room_id: 房间ID
        """
        logger.info(f"Segment timeout in room {room_id}")

        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return

        turn_processing_status = getattr(
            room_state,
            "turn_processing_status",
            "idle",
        )
        turn_processing_kind = getattr(room_state, "turn_processing_kind", None)
        pending_advance_reason = getattr(room_state, "pending_advance_reason", None)

        if self._is_playback_gate_active(room_state):
            deadline_at = getattr(room_state, "playback_gate_deadline_at", None)
            if isinstance(deadline_at, datetime) and self._now() >= deadline_at:
                await self._finalize_playback_gate(room_id, status="timeout")
                return
            if not pending_advance_reason:
                await room_manager.update_room_state(
                    room_id, pending_advance_reason="timeout"
                )
                await websocket_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "advance_deferred",
                        "data": {
                            "reason": "playback_wait",
                            "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                        },
                    },
                )
            return

        if pending_advance_reason != "timeout":
            now = (datetime.utcnow() + timedelta(hours=8)).isoformat()
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "segment_timeout",
                    "data": {"timestamp": now},
                },
            )
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "phase_timeout",
                    "data": {"timestamp": now},
                },
            )

        if turn_processing_status == "processing":
            if (
                turn_processing_kind == "llm"
                and str(getattr(room_state, "current_speaker", "") or "").startswith("ai_")
            ):
                logger.warning(
                    "AI turn timed out while thinking; forcing segment advance "
                    "(room_id=%s, segment_id=%s)",
                    room_id,
                    getattr(room_state, "segment_id", None),
                )
                await room_manager.update_room_state(
                    room_id,
                    turn_processing_status="idle",
                    turn_processing_kind=None,
                    turn_processing_error=None,
                    pending_advance_reason=None,
                )
                return await self.force_advance_segment(
                    room_id,
                    reason="host_advance",
                )
            if not pending_advance_reason:
                await room_manager.update_room_state(
                    room_id, pending_advance_reason="timeout"
                )
                await websocket_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "advance_deferred",
                        "data": {
                            "reason": "timeout",
                            "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                        },
                    },
                )
            return

        if turn_processing_status == "failed" and turn_processing_kind:
            if not pending_advance_reason:
                await room_manager.update_room_state(
                    room_id, pending_advance_reason="timeout"
                )
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "advance_blocked",
                    "data": {
                        "reason": "timeout",
                        "processing_kind": turn_processing_kind,
                        "processing_error": getattr(
                            room_state,
                            "turn_processing_error",
                            None,
                        ),
                        "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                    },
                },
            )
            return

        await self.advance_segment(room_id)

    async def cleanup_room(self, room_id: str) -> None:
        """
        清理房间资源

        Args:
            room_id: 房间ID
        """
        await self.stop_timer(room_id)

        if room_id in self.ai_tasks:
            task = self.ai_tasks.pop(room_id)
            if task is not asyncio.current_task():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except RuntimeError:
                pass

        await self._cancel_ai_draft_tasks(room_id)
        self._clear_ai_draft(room_id)
        self._clear_ai_draft_task(room_id)

        if room_id in self.segments:
            del self.segments[room_id]
        if room_id in self.segment_index:
            del self.segment_index[room_id]

        logger.info(f"Cleaned up flow controller for room {room_id}")


# 创建全局流程控制器实例
flow_controller = DebateFlowController()
