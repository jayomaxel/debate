"""
Helpers for building WebSocket speech payloads.
"""

from datetime import datetime, timedelta
from typing import Any, Optional


def _iso_timestamp(value: Any = None) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and value:
        return value
    return (datetime.utcnow() + timedelta(hours=8)).isoformat()


def build_speech_payload(
    *,
    speech_id: Optional[str],
    user_id: Optional[str],
    role: Optional[str],
    name: Optional[str],
    stance: Optional[str],
    content: str,
    speaker_type: str,
    match_state: Optional[str] = None,
    timestamp: Any = None,
    audio_url: Optional[str] = None,
    audio_format: Optional[str] = None,
    duration: int = 0,
    is_audio: bool = False,
    side: Optional[str] = None,
    speaker_position: Optional[int] = None,
    started_at: Any = None,
    ended_at: Any = None,
    official_duration_sec: Optional[int] = None,
    actual_duration_sec: Optional[int] = None,
    transcription_status: Optional[str] = None,
    transcription_error: Optional[str] = None,
    audio_status: Optional[str] = None,
    phase: Optional[str] = None,
    segment_id: Optional[str] = None,
    segment_title: Optional[str] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "speech_id": speech_id,
        "message_id": speech_id,
        "user_id": user_id,
        "role": role,
        "name": name,
        "stance": stance,
        "speaker_type": speaker_type,
        "content": content,
        "audio_url": audio_url,
        "audio_format": audio_format,
        "duration": int(duration or 0),
        "timestamp": _iso_timestamp(timestamp),
        "is_audio": bool(is_audio),
        "match_state": match_state,
        "side": side,
        "speaker_position": speaker_position,
        "started_at": _iso_timestamp(started_at) if started_at is not None else None,
        "ended_at": _iso_timestamp(ended_at) if ended_at is not None else None,
        "official_duration_sec": official_duration_sec,
        "actual_duration_sec": actual_duration_sec,
        "transcription_status": transcription_status,
        "phase": phase,
        "segment_id": segment_id,
        "segment_title": segment_title,
    }
    if transcription_error is not None:
        payload["transcription_error"] = transcription_error
    if audio_status is not None:
        payload["audio_status"] = audio_status
    return payload
