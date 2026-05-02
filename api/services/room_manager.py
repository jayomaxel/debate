"""
辩论房间管理器
负责管理辩论房间的创建、状态同步、成员管理
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select

from models.debate import Debate, DebateParticipation
from models.user import User
from utils.websocket_manager import websocket_manager
from logging_config import get_logger

logger = get_logger(__name__)

TEACHER_MODERATOR_ROLE = "teacher_moderator"


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
        user: User, participation: DebateParticipation
    ) -> dict:
        return {
            "user_id": str(user.id),
            "name": user.name,
            "role": str(participation.role),
            "stance": str(participation.stance),
            "user_type": "student",
            "can_moderate": False,
            "can_speak": True,
        }

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
        room_state = RoomState(
            room_id=room_id,
            debate_id=str(debate_uuid),
            current_phase=DebatePhase.WAITING,
        )

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
            )
        ).scalar_one_or_none()

        is_teacher_moderator = str(getattr(debate, "teacher_id", "")) == str(user_uuid)

        if not participation and not is_teacher_moderator:
            logger.error(
                f"User {user_id} is not a participant of debate {room_state.debate_id}"
            )
            return False

        # 检查用户是否已在房间
        if any(p["user_id"] == user_id for p in room_state.participants):
            logger.info(f"User {user_id} already in room {room_id}")
            # 即使已在房间，也发送当前状态
            await websocket_manager.send_to_user(
                user_id, {"type": "state_update", "data": room_state.to_dict()}
            )
            return True

        # 添加参与者
        participant_info = (
            self.build_teacher_moderator_participant(user)
            if is_teacher_moderator
            else self.build_student_participant(user, participation)
        )
        room_state.participants.append(participant_info)

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

        return True

    async def leave_room(self, room_id: str, user_id: str) -> bool:
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

        # 移除参与者
        room_state.participants = [
            p for p in room_state.participants if p["user_id"] != user_id
        ]

        logger.info(f"User {user_id} left room {room_id}")

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

        # 更新辩论状态
        debate = db.execute(
            select(Debate).where(Debate.id == debate_uuid)
        ).scalar_one_or_none()

        if debate:
            debate.status = "in_progress"
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
            debate.end_time = (datetime.utcnow() + timedelta(hours=8))
            db.commit()

        # 更新房间状态
        room_state.current_phase = DebatePhase.FINISHED
        room_state.current_speaker = None
        room_state.time_remaining = 0
        room_state.segment_time_remaining = 0
        room_state.speaker_mode = None
        room_state.speaker_options = []
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
            
            # 保存报告到数据库
            debate = db.execute(select(Debate).where(Debate.id == debate_id)).scalar_one()
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

        await websocket_manager.broadcast_to_room(
            room_id, {"type": "state_update", "data": room_state.to_dict()}
        )


# 创建全局房间管理器实例
room_manager = DebateRoomManager()
