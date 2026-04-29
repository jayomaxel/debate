"""
WebSocket路由
处理实时通信
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
import json
from datetime import datetime
import asyncio
import uuid
from pathlib import Path
from sqlalchemy import select
from datetime import timedelta

from database import get_db
from utils.websocket_manager import websocket_manager
from services.room_manager import room_manager
from services.flow_controller import flow_controller
from utils.security import get_user_from_token
from utils.voice_processor import voice_processor
from utils.audio_duration import (
    estimate_duration_from_text,
    get_audio_duration_seconds,
    resolve_local_upload_path_from_audio_url,
)
from models.user import User
from services.room_manager import DebatePhase
from models.speech import Speech
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


def _extract_transcription_text_and_duration(transcription_result) -> tuple[str, int]:
    """
    统一解析不同ASR返回格式，提取文本与时长。

    Args:
        transcription_result: ASR服务返回结果

    Returns:
        (文本内容, 时长秒数)
    """
    text = ""
    duration = 0

    if isinstance(transcription_result, dict):
        raw_text = transcription_result.get("text", "")
        if isinstance(raw_text, str):
            text = raw_text
        else:
            extracted = voice_processor._extract_text_from_transcription(raw_text)
            if isinstance(extracted, str):
                text = extracted
        duration = transcription_result.get("duration", 0) or 0
    elif isinstance(transcription_result, list):
        parts = []
        min_begin_ms = None
        max_end_ms = None
        for item in transcription_result:
            if not isinstance(item, dict):
                continue
            piece = item.get("text")
            if isinstance(piece, str) and piece.strip():
                parts.append(piece.strip())
            begin_ms = item.get("begin_time") or item.get("beginTime")
            end_ms = item.get("end_time") or item.get("endTime")
            if isinstance(begin_ms, (int, float)):
                min_begin_ms = begin_ms if min_begin_ms is None else min(min_begin_ms, begin_ms)
            if isinstance(end_ms, (int, float)):
                max_end_ms = end_ms if max_end_ms is None else max(max_end_ms, end_ms)
        text = "".join(parts).strip()
        if (
            min_begin_ms is not None
            and max_end_ms is not None
            and max_end_ms >= min_begin_ms
        ):
            duration = int(round((max_end_ms - min_begin_ms) / 1000.0))
    else:
        text = str(transcription_result or "").strip()

    return text, int(duration or 0)


async def _notify_committed_speech(
    room_id: str,
    *,
    speech: Speech | None,
    speaker_role: str | None,
    segment_id: str | None,
) -> None:
    if not speech or not getattr(speech, "id", None):
        return
    await flow_controller.notify_speech_committed(
        room_id,
        speech_id=str(speech.id),
        speaker_role=str(speaker_role or ""),
        segment_id=str(segment_id or ""),
    )


@router.websocket("/debate/{room_id}")
async def websocket_debate_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    辩论房间WebSocket端点

    Args:
        websocket: WebSocket连接
        room_id: 房间ID
        token: JWT令牌（通过查询参数传递）
        db: 数据库会话
    """
    user = None
    user_id = None

    try:
        token_payload = get_user_from_token(token)
        if not token_payload:
            await websocket.close(code=1008, reason="Invalid token")
            return

        user_id = str(token_payload.get("user_id"))
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token payload")
            return

        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            await websocket.close(code=1008, reason="Invalid user id")
            return

        user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return

        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            try:
                await room_manager.create_room(
                    room_id=room_id, debate_id=room_id, db=db
                )
            except Exception:
                await websocket.close(code=1008, reason="Room not found")
                return

        # 建立连接
        await websocket_manager.connect(websocket, user_id, room_id)

        # 加入房间
        success = await room_manager.join_room(room_id, user_id, db)
        if not success:
            await websocket.close(code=1008, reason="Failed to join room")
            return

        # 发送当前房间状态
        room_state = room_manager.get_room_state(room_id)
        if room_state:
            try:
                await websocket.send_json(
                    {"type": "state_update", "data": room_state.to_dict()}
                )
            except RuntimeError as e:
                logger.warning(f"Failed to send initial state to user {user_id}: {e}")
                # 连接已关闭，直接返回
                return

        # 消息循环
        while True:
            # 接收消息
            data = await websocket.receive_text()
            message = json.loads(data)

            message_type = message.get("type")
            message_data = message.get("data", {})

            logger.info(f"Received message from user {user_id}: {message_type}")

            # 处理不同类型的消息
            if message_type == "speech":
                # 发言消息
                await handle_speech_message(room_id, user_id, message_data, db)

            elif message_type == "audio":
                # 音频消息（语音发言）
                await handle_audio_message(room_id, user_id, message_data, db)

            elif message_type == "grab_mic":
                # 抢麦消息
                await handle_grab_mic_message(room_id, user_id, message_data, db)

            elif message_type == "request_recording":
                await handle_request_recording_message(room_id, user_id, message_data, db)

            elif message_type == "select_speaker":
                # 选择本段发言者（用于可选回答段）
                await handle_select_speaker_message(room_id, user_id, message_data, db)

            elif message_type == "start_debate":
                await handle_start_debate_message(room_id, user_id, message_data, db)

            elif message_type == "advance_segment":
                await handle_advance_segment_message(room_id, user_id, message_data, db)

            elif message_type == "end_turn":
                await handle_end_turn_message(room_id, user_id, message_data, db)

            elif message_type == "end_debate":
                await handle_end_debate_message(room_id, user_id, message_data, db)

            elif message_type == "speech_playback_started":
                await handle_speech_playback_started_message(
                    room_id, user_id, message_data, db
                )

            elif message_type == "speech_playback_finished":
                await handle_speech_playback_finished_message(
                    room_id, user_id, message_data, db
                )

            elif message_type == "speech_playback_failed":
                await handle_speech_playback_failed_message(
                    room_id, user_id, message_data, db
                )

            elif message_type == "ping":
                # 心跳消息
                try:
                    await websocket.send_json({"type": "pong"})
                except RuntimeError as e:
                    logger.debug(f"Failed to send pong to user {user_id}: {e}")
                    break  # 连接已关闭，退出消息循环

            else:
                logger.warning(f"Unknown message type: {message_type}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user {user_id}, room {room_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)

    finally:
        # 清理连接
        if user_id:
            await websocket_manager.disconnect(user_id, websocket)
            if not websocket_manager.is_user_connected(user_id):
                await room_manager.leave_room(room_id, user_id)

            # 如果房间为空，清理流程控制器
            room_state = room_manager.get_room_state(room_id)
            if not room_state:
                await flow_controller.cleanup_room(room_id)


async def handle_speech_message(
    room_id: str, user_id: str, data: dict, db: Session
) -> None:
    """
    处理发言消息

    Args:
        room_id: 房间ID
        user_id: 用户ID
        data: 消息数据
        db: 数据库会话
    """
    content = str(data.get("content", "") or "").strip()
    audio_url = data.get("audio_url")
    duration = data.get("duration", 0)
    duration_value = 0
    try:
        duration_value = int(duration or 0)
    except Exception:
        duration_value = 0
    if duration_value <= 0:
        local_path = resolve_local_upload_path_from_audio_url(audio_url) if audio_url else None
        actual = get_audio_duration_seconds(local_path) if local_path else None
        if actual is not None:
            duration_value = actual
        else:
            duration_value = estimate_duration_from_text(str(content or ""))
    duration = duration_value

    room_state = room_manager.get_room_state(room_id)
    if not room_state:
        return

    participant = next(
        (p for p in room_state.participants if p["user_id"] == user_id), None
    )
    if not participant:
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "permission_denied",
                "data": {
                    "message": "您不在该房间中",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )
        return

    user_role = participant.get("role")
    if not user_role:
        return

    if not content:
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "error",
                "data": {
                    "message": "发言内容不能为空",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )
        return

    now = (datetime.utcnow() + timedelta(hours=8))

    if room_state.current_phase == DebatePhase.FREE_DEBATE:
        if (
            room_state.mic_owner_user_id != user_id
            or not room_state.mic_expires_at
            or now >= room_state.mic_expires_at
        ):
            holder_label = None
            remaining = 0
            if room_state.mic_owner_user_id and room_state.mic_expires_at and now < room_state.mic_expires_at:
                remaining = max(0, int((room_state.mic_expires_at - now).total_seconds()))
                holder = next(
                    (p for p in room_state.participants if p.get("user_id") == room_state.mic_owner_user_id),
                    None,
                )
                holder_label = (holder.get("name") if holder else None) or str(room_state.mic_owner_role or room_state.mic_owner_user_id)
            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "permission_denied",
                    "data": {
                        "message": (
                            f"无法发言：自由辩论需先抢麦。当前持麦【{holder_label}】，剩余 {remaining} 秒"
                            if holder_label
                            else "无法发言：自由辩论需先抢麦，请点击“抢麦发言”"
                        ),
                        "timestamp": now.isoformat(),
                    },
                },
            )
            return
    else:
        if (
            room_state.speaker_mode == "choice"
            and not room_state.current_speaker
            and user_role in (room_state.speaker_options or [])
        ):
            selected = await flow_controller.set_current_speaker(room_id, user_role)
            if selected:
                room_state = room_manager.get_room_state(room_id) or room_state
                await websocket_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "speaker_selected",
                        "data": {
                            "role": user_role,
                            "timestamp": now.isoformat(),
                        },
                    },
                )
        if room_state.current_speaker != user_role:
            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "permission_denied",
                    "data": {
                        "message": f"无法发言：当前轮到【{room_state.current_speaker}】发言，您是【{user_role}】",
                        "timestamp": now.isoformat(),
                    },
                },
            )
            return

    speech = None
    try:
        debate_uuid = uuid.UUID(str(room_state.debate_id))
        speaker_uuid = uuid.UUID(str(user_id))
        phase_for_speech = room_state.current_phase
        if phase_for_speech in {
            DebatePhase.OPENING,
            DebatePhase.QUESTIONING,
            DebatePhase.FREE_DEBATE,
            DebatePhase.CLOSING,
        }:
            db_phase_value = str(phase_for_speech.value)
        else:
            db_phase_value = str(
                (
                    DebatePhase.CLOSING
                    if phase_for_speech == DebatePhase.FINISHED
                    else DebatePhase.OPENING
                ).value
            )
            logger.warning(
                f"Coerced speech phase for DB insert: {phase_for_speech} -> {db_phase_value} (room_id={room_id}, user_id={user_id})"
            )
        speech = Speech(
            debate_id=debate_uuid,
            speaker_id=speaker_uuid,
            speaker_type="human",
            speaker_role=str(user_role),
            phase=db_phase_value,
            content=str(content),
            audio_url=audio_url,
            duration=int(duration),
            timestamp=(datetime.utcnow() + timedelta(hours=8)),
        )
        db.add(speech)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to persist speech: {e}", exc_info=True)

    # 广播发言消息
    await websocket_manager.broadcast_to_room(
        room_id,
        {
            "type": "speech",
            "data": {
                "user_id": user_id,
                "role": user_role,
                "name": participant.get("name"),
                "stance": participant.get("stance"),
                "content": content,
                "audio_url": audio_url,
                "duration": duration,
                "timestamp": data.get("timestamp"),
            },
        },
    )

    segment_id = getattr(room_state, "segment_id", None)
    if (
        room_state.current_phase != DebatePhase.FREE_DEBATE
        and room_state.current_speaker == user_role
    ):
        await room_manager.update_room_state(
            room_id,
            turn_processing_status="idle",
            turn_processing_kind=None,
            turn_processing_error=None,
            turn_speech_committed=True,
            turn_speech_user_id=str(user_id),
            turn_speech_role=str(user_role),
            turn_speech_timestamp=(datetime.utcnow() + timedelta(hours=8)),
        )
        latest_state = room_manager.get_room_state(room_id)
        if (
            latest_state
            and latest_state.segment_id == segment_id
            and getattr(latest_state, "pending_advance_reason", None)
        ):
            pending = latest_state.pending_advance_reason
            await room_manager.update_room_state(room_id, pending_advance_reason=None)
            await flow_controller.force_advance_segment(room_id, reason=str(pending))

    await _notify_committed_speech(
        room_id,
        speech=speech,
        speaker_role=str(user_role),
        segment_id=str(segment_id or ""),
    )

    logger.info(f"Speech broadcast in room {room_id} from user {user_id}")


async def handle_grab_mic_message(
    room_id: str, user_id: str, data: dict, db: Session
) -> None:
    """
    处理抢麦消息

    Args:
        room_id: 房间ID
        user_id: 用户ID
        data: 消息数据
        db: 数据库会话
    """
    # 获取用户角色
    room_state = room_manager.get_room_state(room_id)
    if not room_state:
        return

    user_role = None
    for participant in room_state.participants:
        if participant["user_id"] == user_id:
            user_role = participant["role"]
            break

    if not user_role:
        return

    if (
        room_state.current_phase != DebatePhase.FREE_DEBATE
        or room_state.speaker_mode != "free"
    ):
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "permission_denied",
                "data": {
                    "message": "当前阶段不可抢麦",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )
        return

    now = (datetime.utcnow() + timedelta(hours=8))
    if (
        room_state.mic_expires_at
        and now < room_state.mic_expires_at
        and (room_state.mic_owner_user_id or room_state.mic_owner_role)
    ):
        remaining = max(0, int((room_state.mic_expires_at - now).total_seconds()))
        holder = next(
            (p for p in room_state.participants if p.get("user_id") == room_state.mic_owner_user_id),
            None,
        )
        holder_label = (holder.get("name") if holder else None) or str(room_state.mic_owner_role or room_state.mic_owner_user_id)
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "permission_denied",
                "data": {
                    "message": f"抢麦失败：麦克风已被【{holder_label}】占用，剩余 {remaining} 秒",
                    "timestamp": now.isoformat(),
                },
            },
        )
        return

    mic_expires_at = now + timedelta(seconds=30)
    await room_manager.update_room_state(
        room_id,
        mic_owner_user_id=user_id,
        mic_owner_role=user_role,
        mic_expires_at=mic_expires_at,
        current_speaker=user_role,
        free_debate_last_side="human",
        free_debate_next_side="human",
    )

    # 广播抢麦成功
    await websocket_manager.broadcast_to_room(
        room_id,
        {
            "type": "mic_grabbed",
            "data": {
                "user_id": user_id,
                "role": user_role,
                "expires_at": mic_expires_at.isoformat(),
                "timestamp": now.isoformat(),
            },
        },
    )

    logger.info(f"Mic grabbed in room {room_id} by user {user_id}")


async def handle_request_recording_message(
    room_id: str, user_id: str, data: dict, db: Session
) -> None:
    room_state = room_manager.get_room_state(room_id)
    if not room_state:
        return

    request_id = data.get("request_id")
    now = (datetime.utcnow() + timedelta(hours=8))

    participant = next(
        (p for p in room_state.participants if p["user_id"] == user_id), None
    )
    if not participant or not participant.get("role"):
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "recording_permission",
                "data": {
                    "request_id": request_id,
                    "allowed": False,
                    "message": "无法开始录音：您不在该辩论房间中",
                    "timestamp": now.isoformat(),
                },
            },
        )
        return

    user_role = str(participant.get("role"))
    segment_title = getattr(room_state, "segment_title", None) or str(
        getattr(room_state, "segment_id", "") or ""
    )

    if room_state.current_phase in (DebatePhase.WAITING, DebatePhase.FINISHED):
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "recording_permission",
                "data": {
                    "request_id": request_id,
                    "allowed": False,
                    "message": "无法开始录音：辩论尚未开始或已结束",
                    "timestamp": now.isoformat(),
                },
            },
        )
        return

    if room_state.current_phase == DebatePhase.FREE_DEBATE and room_state.speaker_mode == "free":
        mic_owner_user_id = getattr(room_state, "mic_owner_user_id", None)
        mic_owner_role = getattr(room_state, "mic_owner_role", None)
        mic_expires_at = getattr(room_state, "mic_expires_at", None)
        mic_active = bool(mic_owner_user_id and mic_expires_at and now < mic_expires_at)

        if mic_active:
            if str(mic_owner_user_id) == str(user_id):
                await websocket_manager.send_to_user(
                    user_id,
                    {
                        "type": "recording_permission",
                        "data": {
                            "request_id": request_id,
                            "allowed": True,
                            "message": f"允许开始录音：您已持麦（{segment_title}）",
                            "timestamp": now.isoformat(),
                        },
                    },
                )
                return

            remaining = max(
                0, int((mic_expires_at - now).total_seconds())
            ) if mic_expires_at else 0
            holder_name = None
            if mic_owner_user_id:
                holder = next(
                    (p for p in room_state.participants if p.get("user_id") == mic_owner_user_id),
                    None,
                )
                holder_name = holder.get("name") if holder else None
            holder_label = holder_name or str(mic_owner_role or mic_owner_user_id or "未知")
            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "recording_permission",
                    "data": {
                        "request_id": request_id,
                        "allowed": False,
                        "message": f"无法开始录音：自由辩论已被【{holder_label}】持麦，剩余 {remaining} 秒",
                        "timestamp": now.isoformat(),
                    },
                },
            )
            return

        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "recording_permission",
                "data": {
                    "request_id": request_id,
                    "allowed": False,
                    "message": "无法开始录音：自由辩论需要先抢麦，请点击“抢麦发言”",
                    "timestamp": now.isoformat(),
                },
            },
        )
        return

    current_speaker = getattr(room_state, "current_speaker", None)
    if (
        room_state.speaker_mode == "choice"
        and not current_speaker
        and user_role in (room_state.speaker_options or [])
    ):
        selected = await flow_controller.set_current_speaker(room_id, user_role)
        if selected:
            room_state = room_manager.get_room_state(room_id) or room_state
            current_speaker = getattr(room_state, "current_speaker", None)
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "speaker_selected",
                    "data": {
                        "role": user_role,
                        "timestamp": now.isoformat(),
                    },
                },
            )

    if not current_speaker:
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "recording_permission",
                "data": {
                    "request_id": request_id,
                    "allowed": False,
                    "message": f"无法开始录音：当前未指定发言者（{segment_title}）",
                    "timestamp": now.isoformat(),
                },
            },
        )
        return

    if str(current_speaker) == user_role:
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "recording_permission",
                "data": {
                    "request_id": request_id,
                    "allowed": True,
                    "message": f"允许开始录音：当前轮到您发言（{segment_title}）",
                    "timestamp": now.isoformat(),
                },
            },
        )
        return

    await websocket_manager.send_to_user(
        user_id,
        {
            "type": "recording_permission",
            "data": {
                "request_id": request_id,
                "allowed": False,
                "message": f"无法开始录音：当前轮到【{current_speaker}】发言，您是【{user_role}】（{segment_title}）",
                "timestamp": now.isoformat(),
            },
        },
    )


async def handle_audio_message(
    room_id: str, user_id: str, data: dict, db: Session
) -> None:
    """
    处理音频消息（语音发言）

    Args:
        room_id: 房间ID
        user_id: 用户ID
        data: 消息数据（包含audio_data, audio_format等）
        db: 数据库会话
    """
    asr_started_segment_id = None
    asr_started_phase = None
    asr_started_speaker = None
    asr_started_user_role = None

    def asr_turn_still_current() -> bool:
        latest = room_manager.get_room_state(room_id)
        if not latest:
            return False
        return (
            getattr(latest, "segment_id", None) == asr_started_segment_id
            and getattr(latest, "current_phase", None) == asr_started_phase
            and getattr(latest, "current_speaker", None) == asr_started_speaker
            and getattr(latest, "turn_processing_kind", None) == "asr"
            and getattr(latest, "turn_speech_user_id", None) == str(user_id)
            and getattr(latest, "turn_speech_role", None) == str(asr_started_user_role)
        )

    try:
        room_state = room_manager.get_room_state(room_id)
        if not room_state:
            return

        participant = next(
            (p for p in room_state.participants if p["user_id"] == user_id), None
        )
        if not participant:
            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "permission_denied",
                    "data": {
                        "message": "您不在该房间中",
                        "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                    },
                },
            )
            return

        user_role = participant.get("role")
        if not user_role:
            return

        now = (datetime.utcnow() + timedelta(hours=8))
        is_free_debate = room_state.current_phase == DebatePhase.FREE_DEBATE

        if is_free_debate:
            if (
                room_state.mic_owner_user_id != user_id
                or not room_state.mic_expires_at
                or now >= room_state.mic_expires_at
            ):
                holder_label = None
                remaining = 0
                if room_state.mic_owner_user_id and room_state.mic_expires_at and now < room_state.mic_expires_at:
                    remaining = max(0, int((room_state.mic_expires_at - now).total_seconds()))
                    holder = next(
                        (p for p in room_state.participants if p.get("user_id") == room_state.mic_owner_user_id),
                        None,
                    )
                    holder_label = (holder.get("name") if holder else None) or str(room_state.mic_owner_role or room_state.mic_owner_user_id)
                await websocket_manager.send_to_user(
                    user_id,
                    {
                        "type": "permission_denied",
                        "data": {
                            "message": (
                                f"无法开始录音：自由辩论已被【{holder_label}】持麦，剩余 {remaining} 秒"
                                if holder_label
                                else "无法开始录音：自由辩论需要先抢麦，请点击“抢麦发言”"
                            ),
                            "timestamp": now.isoformat(),
                        },
                    },
                )
                return
        else:
            if room_state.current_speaker != user_role:
                await websocket_manager.send_to_user(
                    user_id,
                    {
                        "type": "permission_denied",
                        "data": {
                            "message": f"无法开始录音：当前轮到【{room_state.current_speaker}】发言，您是【{user_role}】",
                            "timestamp": now.isoformat(),
                        },
                    },
                )
                return

        segment_id = getattr(room_state, "segment_id", None)
        asr_started_segment_id = segment_id
        asr_started_phase = getattr(room_state, "current_phase", None)
        asr_started_speaker = getattr(room_state, "current_speaker", None)
        asr_started_user_role = user_role
        await room_manager.update_room_state(
            room_id,
            turn_processing_status="processing",
            turn_processing_kind="asr",
            turn_processing_error=None,
            turn_speech_committed=False,
            turn_speech_user_id=str(user_id),
            turn_speech_role=str(user_role),
            turn_speech_timestamp=None,
        )

        audio_base64 = data.get("audio_data")
        audio_format = data.get("audio_format", "webm")
        client_transcript = str(data.get("client_transcript") or "").strip()
        if not audio_base64:
            logger.warning(f"No audio data in message from user {user_id}")
            if asr_turn_still_current():
                await room_manager.update_room_state(
                    room_id,
                    turn_processing_status="failed",
                    turn_processing_kind="asr",
                    turn_processing_error="音频数据为空",
                    turn_speech_committed=False,
                )
            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "error",
                    "data": {
                        "message": "音频数据为空",
                        "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                    },
                },
            )
            return

        # 先解码并保存音频，保证聊天室能尽快看到并播放这条语音。
        audio_data = voice_processor.decode_audio_base64(audio_base64)
        audio_path = None
        audio_url = None
        try:
            audio_filename = (
                f"{room_id}_{user_id}_"
                f"{int((datetime.utcnow() + timedelta(hours=8)).timestamp() * 1000)}."
                f"{audio_format}"
            )
            audio_path = await voice_processor.save_audio_file(audio_data, audio_filename)
            audio_url = voice_processor.build_audio_url(audio_path)
        except Exception as e:
            logger.warning(f"Failed to save audio file: {e}", exc_info=True)

        duration = 0
        if audio_path:
            actual = get_audio_duration_seconds(Path(audio_path))
            if actual is not None:
                duration = actual

        speech = None
        speech_timestamp = (datetime.utcnow() + timedelta(hours=8))
        try:
            debate_uuid = uuid.UUID(str(room_state.debate_id))
            speaker_uuid = uuid.UUID(str(user_id))
            speech = Speech(
                id=uuid.uuid4(),
                debate_id=debate_uuid,
                speaker_id=speaker_uuid,
                speaker_type="human",
                speaker_role=str(user_role),
                phase=str(room_state.current_phase.value),
                content="",
                audio_url=audio_url,
                duration=int(duration or 0),
                timestamp=speech_timestamp,
            )
            db.add(speech)
            db.commit()
        except Exception as e:
            db.rollback()
            speech = None
            logger.error(f"Failed to persist initial audio speech: {e}", exc_info=True)

        # 先广播语音占位消息，后续ASR完成后再用同一speech_id回填文本。
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "speech",
                "data": {
                    "speech_id": str(speech.id) if speech and speech.id else None,
                    "message_id": str(speech.id) if speech and speech.id else None,
                    "user_id": user_id,
                    "role": user_role,
                    "name": participant.get("name"),
                    "stance": participant.get("stance"),
                    "content": "",
                    "audio_url": audio_url,
                    "audio_format": audio_format,
                    "duration": int(duration or 0),
                    "timestamp": speech_timestamp.isoformat(),
                    "is_audio": True,
                    "transcription_status": "processing",
                    "phase": str(room_state.current_phase.value),
                    "segment_id": segment_id,
                    "segment_title": getattr(room_state, "segment_title", None),
                },
            },
        )

        logger.info(f"Transcribing audio from user {user_id} in room {room_id}")
        transcription_result = await voice_processor.transcribe_audio(
            audio_data, audio_format=audio_format, language="zh", db=db
        )
        if (
            isinstance(transcription_result, dict)
            and "error" in transcription_result
            and client_transcript
        ):
            logger.warning("ASR failed, using browser speech recognition fallback text.")
            transcription_result = {
                "text": client_transcript,
                "duration": int(duration or 0),
                "fallback_source": "browser_speech_recognition",
            }
        if isinstance(transcription_result, dict) and "error" in transcription_result:
            logger.error(f"ASR failed: {transcription_result['error']}")
            if asr_turn_still_current():
                await room_manager.update_room_state(
                    room_id,
                    turn_processing_status="failed",
                    turn_processing_kind="asr",
                    turn_processing_error=str(transcription_result.get("error")),
                    turn_speech_committed=False,
                )
            if speech is not None:
                await websocket_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "speech",
                        "data": {
                            "speech_id": str(speech.id),
                            "message_id": str(speech.id),
                            "user_id": user_id,
                            "role": user_role,
                            "name": participant.get("name"),
                            "stance": participant.get("stance"),
                            "content": "",
                            "audio_url": audio_url,
                            "audio_format": audio_format,
                            "duration": int(duration or 0),
                            "timestamp": speech_timestamp.isoformat(),
                            "is_audio": True,
                            "transcription_status": "failed",
                            "transcription_error": str(transcription_result.get("error")),
                            "phase": str(room_state.current_phase.value),
                            "segment_id": segment_id,
                            "segment_title": getattr(room_state, "segment_title", None),
                        },
                    },
                )
            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "error",
                    "data": {
                        "message": f"语音识别失败: {transcription_result['error']}",
                        "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                    },
                },
            )
            return

        text, asr_duration = _extract_transcription_text_and_duration(transcription_result)
        if not text and client_transcript:
            text = client_transcript
        if not text:
            logger.warning(f"Empty transcription result for user {user_id}")
            if asr_turn_still_current():
                await room_manager.update_room_state(
                    room_id,
                    turn_processing_status="failed",
                    turn_processing_kind="asr",
                    turn_processing_error="未识别到语音内容",
                    turn_speech_committed=False,
                )
            if speech is not None:
                await websocket_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "speech",
                        "data": {
                            "speech_id": str(speech.id),
                            "message_id": str(speech.id),
                            "user_id": user_id,
                            "role": user_role,
                            "name": participant.get("name"),
                            "stance": participant.get("stance"),
                            "content": "",
                            "audio_url": audio_url,
                            "audio_format": audio_format,
                            "duration": int(duration or 0),
                            "timestamp": speech_timestamp.isoformat(),
                            "is_audio": True,
                            "transcription_status": "failed",
                            "transcription_error": "未识别到语音内容",
                            "phase": str(room_state.current_phase.value),
                            "segment_id": segment_id,
                            "segment_title": getattr(room_state, "segment_title", None),
                        },
                    },
                )
            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "error",
                    "data": {
                        "message": "未识别到语音内容",
                        "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                    },
                },
            )
            return

        logger.info(f"Transcription successful: {text[:50]}...")
        if int(duration or 0) <= 0:
            duration = int(asr_duration or 0)
        if int(duration or 0) <= 0:
            duration = estimate_duration_from_text(str(text or ""))

        if speech is not None:
            try:
                # 使用同一条Speech记录回填识别文本，前端可按speech_id合并更新。
                speech.content = str(text)
                speech.duration = int(duration)
                if audio_url and not speech.audio_url:
                    speech.audio_url = audio_url
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to update speech after ASR: {e}", exc_info=True)

        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "speech",
                "data": {
                    "speech_id": str(speech.id) if speech and speech.id else None,
                    "message_id": str(speech.id) if speech and speech.id else None,
                    "user_id": user_id,
                    "role": user_role,
                    "name": participant.get("name"),
                    "stance": participant.get("stance"),
                    "content": text,
                    "audio_url": audio_url,
                    "audio_format": audio_format,
                    "duration": int(duration),
                    "timestamp": speech_timestamp.isoformat(),
                    "is_audio": True,
                    "transcription_status": "completed",
                    "phase": str(room_state.current_phase.value),
                    "segment_id": segment_id,
                    "segment_title": getattr(room_state, "segment_title", None),
                },
            },
        )

        asr_current = asr_turn_still_current()
        if asr_current:
            await room_manager.update_room_state(
                room_id,
                turn_processing_status="succeeded",
                turn_processing_kind="asr",
                turn_processing_error=None,
                turn_speech_committed=True,
                turn_speech_user_id=str(user_id),
                turn_speech_role=str(user_role),
                turn_speech_timestamp=(datetime.utcnow() + timedelta(hours=8)),
            )
            await _notify_committed_speech(
                room_id,
                speech=speech,
                speaker_role=str(user_role),
                segment_id=str(segment_id or ""),
            )
        latest_state = room_manager.get_room_state(room_id)
        if (
            not is_free_debate
            and latest_state
            and latest_state.segment_id == segment_id
            and asr_current
            and getattr(latest_state, "pending_advance_reason", None)
        ):
            pending = latest_state.pending_advance_reason
            await room_manager.update_room_state(room_id, pending_advance_reason=None)
            await flow_controller.force_advance_segment(room_id, reason=str(pending))

        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "audio_processed",
                "data": {
                    "speech_id": str(speech.id) if speech and speech.id else None,
                    "text": text,
                    "audio_url": audio_url,
                    "audio_format": audio_format,
                    "duration": int(duration),
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )

        logger.info(
            f"Audio message processed and updated in room {room_id} from user {user_id}"
        )

    except Exception as e:
        logger.error(f"Failed to process audio message: {e}", exc_info=True)
        if asr_turn_still_current():
            await room_manager.update_room_state(
                room_id,
                turn_processing_status="failed",
                turn_processing_kind="asr",
                turn_processing_error=str(e),
                turn_speech_committed=False,
            )
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "error",
                "data": {
                    "message": f"音频处理失败: {str(e)}",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )


async def handle_select_speaker_message(
    room_id: str,
    user_id: str,
    data: dict,
    db: Session,
) -> None:
    room_state = room_manager.get_room_state(room_id)
    if not room_state:
        return

    if room_state.speaker_mode != "choice":
        return

    participant = next(
        (p for p in room_state.participants if p["user_id"] == user_id), None
    )
    if not participant:
        return

    desired_role = data.get("role")
    if not desired_role:
        return

    if participant.get("role") != desired_role:
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "permission_denied",
                "data": {
                    "message": "只能选择自己作为回答者",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )
        return

    ok = await flow_controller.set_current_speaker(room_id, desired_role)
    if ok:
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "speaker_selected",
                "data": {
                    "role": desired_role,
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )


async def handle_start_debate_message(
    room_id: str,
    user_id: str,
    data: dict,
    db: Session,
) -> None:
    room_state = room_manager.get_room_state(room_id)
    if not room_state:
        return
    participant = next(
        (p for p in room_state.participants if p["user_id"] == user_id), None
    )
    if not participant:
        return
    if participant.get("role") != "debater_1":
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "permission_denied",
                "data": {
                    "message": "只有正方一辩可以开始辩论",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )
        return
    ok = await room_manager.start_debate(room_id, db)
    if not ok:
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "error",
                "data": {
                    "message": "辩论开始失败",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )


async def handle_advance_segment_message(
    room_id: str,
    user_id: str,
    data: dict,
    db: Session,
) -> None:
    room_state = room_manager.get_room_state(room_id)
    if not room_state:
        return
    participant = next(
        (p for p in room_state.participants if p["user_id"] == user_id), None
    )
    if not participant:
        return
    if participant.get("role") != "debater_1":
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "permission_denied",
                "data": {
                    "message": "只有正方一辩可以推进环节",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )
        return
    ok = await flow_controller.force_advance_segment(room_id, reason="host_advance")
    if not ok:
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "error",
                "data": {
                    "message": "推进环节失败（可能尚未开始）",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )


async def handle_end_debate_message(
    room_id: str,
    user_id: str,
    data: dict,
    db: Session,
) -> None:
    room_state = room_manager.get_room_state(room_id)
    if not room_state:
        return
    participant = next(
        (p for p in room_state.participants if p["user_id"] == user_id), None
    )
    if not participant:
        return
    if participant.get("role") != "debater_1":
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "permission_denied",
                "data": {
                    "message": "只有正方一辩可以结束辩论",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )
        return
    if room_state.current_phase in (DebatePhase.WAITING, DebatePhase.FINISHED):
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "permission_denied",
                "data": {
                    "message": "当前阶段无法结束辩论",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )
        return
    allow_early_close = (
        room_state.current_phase == DebatePhase.CLOSING
        and str(getattr(room_state, "segment_id", "") or "") == "closing_negative_4"
        and not any(p.get("role") == "debater_4" for p in room_state.participants)
    )
    if not (flow_controller.is_last_segment(room_id) or allow_early_close):
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "permission_denied",
                "data": {
                    "message": "仅最后一轮可结束辩论（正方四辩缺席时可在反方四辩后结束）",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )
        return
    ok = await room_manager.end_debate(room_id, db)
    if not ok:
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "error",
                "data": {
                    "message": "结束辩论失败",
                    "timestamp": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
            },
        )


async def handle_speech_playback_started_message(
    room_id: str,
    user_id: str,
    data: dict,
    db: Session,
) -> None:
    await flow_controller.handle_speech_playback_started(room_id, user_id, data or {})


async def handle_speech_playback_finished_message(
    room_id: str,
    user_id: str,
    data: dict,
    db: Session,
) -> None:
    await flow_controller.handle_speech_playback_finished(room_id, user_id, data or {})


async def handle_speech_playback_failed_message(
    room_id: str,
    user_id: str,
    data: dict,
    db: Session,
) -> None:
    await flow_controller.handle_speech_playback_failed(room_id, user_id, data or {})


async def handle_end_turn_message(
    room_id: str,
    user_id: str,
    data: dict,
    db: Session,
) -> None:
    room_state = room_manager.get_room_state(room_id)
    if not room_state:
        return
    participant = next(
        (p for p in room_state.participants if p["user_id"] == user_id), None
    )
    if not participant:
        return
    user_role = participant.get("role")
    if not user_role:
        return
    now = (datetime.utcnow() + timedelta(hours=8))
    if (
        room_state.current_phase == DebatePhase.FREE_DEBATE
        and room_state.speaker_mode == "free"
    ):
        if (
            getattr(room_state, "turn_processing_status", "idle") == "processing"
            and getattr(room_state, "turn_speech_user_id", None) == user_id
        ):
            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "error",
                    "data": {
                        "message": "语音处理中，处理成功后请点击“结束发言”以交给反方AI发言",
                        "timestamp": now.isoformat(),
                    },
                },
            )
            return
        if (
            room_state.mic_owner_user_id != user_id
            or not room_state.mic_expires_at
            or now >= room_state.mic_expires_at
        ):
            holder_label = None
            remaining = 0
            if room_state.mic_owner_user_id and room_state.mic_expires_at and now < room_state.mic_expires_at:
                remaining = max(0, int((room_state.mic_expires_at - now).total_seconds()))
                holder = next(
                    (p for p in room_state.participants if p.get("user_id") == room_state.mic_owner_user_id),
                    None,
                )
                holder_label = (holder.get("name") if holder else None) or str(room_state.mic_owner_role or room_state.mic_owner_user_id)
            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "permission_denied",
                    "data": {
                        "message": (
                            f"无法结束发言：当前持麦【{holder_label}】，剩余 {remaining} 秒"
                            if holder_label
                            else "无法结束发言：自由辩论需要先抢麦"
                        ),
                        "timestamp": now.isoformat(),
                    },
                },
            )
            return
        await room_manager.update_room_state(
            room_id,
            mic_owner_user_id=None,
            mic_owner_role=None,
            mic_expires_at=None,
            current_speaker=None,
            free_debate_last_side="human",
            free_debate_next_side="human",
        )
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "mic_released",
                "data": {"reason": "end_turn", "timestamp": now.isoformat()},
            },
        )
        await flow_controller.schedule_free_debate_ai_turn(room_id)
        return
    if room_state.current_speaker != user_role:
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "permission_denied",
                "data": {
                    "message": f"无法结束发言：当前轮到【{room_state.current_speaker}】发言，您是【{user_role}】",
                    "timestamp": now.isoformat(),
                },
            },
        )
        return
    ok = await flow_controller.force_advance_segment(room_id, reason="end_turn")
    if not ok:
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "error",
                "data": {
                    "message": "无法结束回合：语音处理未成功",
                    "timestamp": now.isoformat(),
                },
            },
        )
