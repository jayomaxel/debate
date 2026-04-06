"""
辩论流程控制器
负责控制辩论环节切换、发言权限管理、倒计时
"""

from typing import Optional, Dict, List, Any, AsyncIterator
from datetime import datetime, timedelta
import asyncio
import json
import time

from services.room_manager import room_manager, DebatePhase
from utils.websocket_manager import websocket_manager
import database as db_module
from sqlalchemy import select
import uuid
from models.debate import Debate
from models.speech import Speech
from agents.debater_agent import AIDebaterAgent
from services.config_service import ConfigService
from utils.voice_processor import voice_processor
from logging_config import get_logger

logger = get_logger(__name__)


class DebateFlowController:
    """辩论流程控制器"""

    def __init__(self):
        # 存储定时器任务: {room_id: asyncio.Task}
        self.timer_tasks: Dict[str, asyncio.Task] = {}
        self.segments: Dict[str, List[Dict[str, Any]]] = {}
        self.segment_index: Dict[str, int] = {}
        self.ai_tasks: Dict[str, asyncio.Task] = {}

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

        await room_manager.update_room_state(room_id, current_speaker=speaker_role)
        return True

    async def advance_segment(self, room_id: str) -> bool:
        if room_id not in self.segment_index:
            return False

        self.segment_index[room_id] = self.segment_index.get(room_id, 0) + 1
        return await self._apply_current_segment(room_id)

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
            task.cancel()

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
            await self.stop_timer(room_id)
            await room_manager.update_room_state(
                room_id,
                current_phase=DebatePhase.FINISHED,
                current_speaker=None,
                time_remaining=0,
                segment_time_remaining=0,
                speaker_mode=None,
                speaker_options=[],
                segment_id=None,
                segment_title=None,
                segment_start_time=None,
            )
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
            return False

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
            task.cancel()
        if (
            current_speaker
            and str(current_speaker).startswith("ai_")
            and segment.get("mode") == "fixed"
        ):
            self.ai_tasks[room_id] = asyncio.create_task(
                self._run_ai_turn(room_id, segment)
            )

        return True

    async def trigger_free_debate_ai_turn(self, room_id: str) -> None:
        """
        触发自由辩论阶段的AI发言
        """
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return

        if room_state.current_phase != DebatePhase.FREE_DEBATE:
            return
        if getattr(room_state, "free_debate_next_side", "human") != "ai":
            return

        now = (datetime.utcnow() + timedelta(hours=8))
        if (
            (room_state.mic_owner_user_id or room_state.mic_owner_role)
            and room_state.mic_expires_at
            and now < room_state.mic_expires_at
        ):
            return

        # 随机选择一个未发言或较少发言的AI（这里简单随机选择一个AI）
        import random
        ai_roles = ["ai_1", "ai_2", "ai_3", "ai_4"]
        speaker_role = random.choice(ai_roles)
        
        # 抢麦
        mic_expires_at = now + timedelta(seconds=30)
        
        await room_manager.update_room_state(
            room_id,
            mic_owner_user_id="__ai__",
            mic_owner_role=speaker_role,
            mic_expires_at=mic_expires_at,
            current_speaker=speaker_role,
        )

        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "mic_grabbed",
                "data": {
                    "user_id": "__ai__",
                    "role": speaker_role,
                    "expires_at": mic_expires_at.isoformat(),
                    "timestamp": now.isoformat(),
                },
            },
        )
        
        # 构造segment信息用于AI生成
        segment = {
            "id": "free_debate",
            "title": "自由辩论",
            "phase": DebatePhase.FREE_DEBATE,
            "mode": "free"
        }
        
        # 执行AI发言
        self.ai_tasks[room_id] = asyncio.create_task(
            self._run_ai_turn(room_id, segment)
        )

    async def _run_ai_turn(self, room_id: str, segment: Dict[str, Any]) -> None:
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

                if room_state.segment_start_time:
                    if (
                        room_state.current_phase == DebatePhase.FREE_DEBATE
                        and room_state.mic_expires_at
                    ):
                        if (datetime.utcnow() + timedelta(hours=8)) >= room_state.mic_expires_at:
                            await room_manager.update_room_state(
                                room_id,
                                mic_owner_user_id=None,
                                mic_owner_role=None,
                                mic_expires_at=None,
                                current_speaker=None,
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

        if room_id in self.segments:
            del self.segments[room_id]
        if room_id in self.segment_index:
            del self.segment_index[room_id]

        logger.info(f"Cleaned up flow controller for room {room_id}")


# 创建全局流程控制器实例
flow_controller = DebateFlowController()
