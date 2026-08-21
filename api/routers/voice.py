"""
语音相关API路由
提供ASR（语音识别）与TTS（语音合成）接口
"""
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import os

from config import settings
from logging_config import get_logger
from database import get_db
from middleware.auth_middleware import verify_token_middleware
from models.user import User
from utils.voice_processor import voice_processor
from services.config_service import ConfigService
from services.file_access_service import (
    FileAccessService,
    InvalidMediaTicket,
    PrivateFileNotFound,
)

logger = get_logger(__name__)

ALLOWED_AUDIO_FORMATS = {"webm", "wav", "mp3", "m4a", "ogg", "pcm"}


def _normalize_audio_format(audio_format: Optional[str]) -> str:
    normalized = (audio_format or "webm").strip().lower().lstrip(".")
    if normalized not in ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio format",
        )
    return normalized


def _validate_audio_size(audio_data: bytes) -> None:
    if len(audio_data or b"") > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio upload exceeds the configured size limit",
        )

router = APIRouter(prefix="/api/voice", tags=["语音"])


class AsrBase64Request(BaseModel):
    audio_base64: str
    audio_format: str = "webm"
    language: str = "zh"


class TtsSynthesizeRequest(BaseModel):
    text: str = Field(min_length=1)
    voice_id: Optional[str] = None
    speed: Optional[float] = Field(None, ge=0.5, le=4.0)


class MediaTicketRequest(BaseModel):
    audio_url: str = Field(min_length=1, max_length=1000)


@router.post("/media/ticket", summary="申请私有音频短时播放票据")
async def issue_media_ticket(
    request: MediaTicketRequest,
    current_user: User = Depends(verify_token_middleware),
    db: Session = Depends(get_db),
):
    try:
        object_key, speech = FileAccessService(db).authorize_media_reference(
            current_user,
            request.audio_url,
        )
    except PrivateFileNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    ticket = FileAccessService.issue_media_ticket(
        user_id=str(current_user.id),
        object_key=object_key,
        speech_id=str(speech.id),
    )
    return {
        "code": 200,
        "message": "播放票据已签发",
        "data": {
            "media_url": FileAccessService.ticketed_media_url(object_key, ticket),
            "expires_in": FileAccessService.MEDIA_TICKET_TTL_SECONDS,
        },
    }


@router.get("/media/{media_kind}/{object_name}", summary="使用短时票据读取私有音频")
async def download_private_media(
    media_kind: str,
    object_name: str,
    ticket: str = Query(..., min_length=20),
    db: Session = Depends(get_db),
):
    try:
        private_file = FileAccessService(db).resolve_ticketed_media(
            ticket,
            f"{media_kind}/{object_name}",
        )
    except (InvalidMediaTicket, PrivateFileNotFound):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid media ticket")
    return FileResponse(
        path=private_file.path,
        media_type=private_file.media_type,
        headers={
            **FileAccessService.private_headers(),
            "Content-Disposition": f'inline; filename="{private_file.filename}"',
        },
    )


@router.post("/asr/transcribe", summary="ASR语音识别（上传音频文件）")
async def transcribe_audio_file(
    file: UploadFile = File(...),
    language: str = Form("zh"),
    audio_format: Optional[str] = Form(None),
    current_user: User = Depends(verify_token_middleware),
    db: Session = Depends(get_db),
):
    try:
        audio_data = await file.read()
        _validate_audio_size(audio_data)
        if not audio_format:
            if file.filename and "." in file.filename:
                audio_format = file.filename.rsplit(".", 1)[-1].lower()
            else:
                audio_format = "webm"
        audio_format = _normalize_audio_format(audio_format)

        result = await voice_processor.transcribe_audio(
            audio_data=audio_data,
            audio_format=audio_format,
            language=language,
            db=db,
        )
        if "error" in result:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

        return {"code": 200, "message": "识别成功", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ASR transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="语音识别失败")


@router.post("/asr/transcribe/base64", summary="ASR语音识别（Base64音频）")
async def transcribe_audio_base64(
    request: AsrBase64Request,
    current_user: User = Depends(verify_token_middleware),
    db: Session = Depends(get_db),
):
    try:
        audio_data = voice_processor.decode_audio_base64(request.audio_base64)
        _validate_audio_size(audio_data)
        audio_format = _normalize_audio_format(request.audio_format)
        result = await voice_processor.transcribe_audio(
            audio_data=audio_data,
            audio_format=audio_format,
            language=request.language,
            db=db,
        )
        if "error" in result:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

        return {"code": 200, "message": "识别成功", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ASR transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="语音识别失败")


@router.post("/tts/synthesize", summary="TTS语音合成（返回Base64音频）")
async def synthesize_speech(
    request: TtsSynthesizeRequest,
    current_user: User = Depends(verify_token_middleware),
    db: Session = Depends(get_db),
):
    try:
        audio_data = await voice_processor.synthesize_speech(
            text=request.text,
            voice_id=request.voice_id or "Cherry",
            # 未显式传语速时，回退到后台 TTS 配置，保持和 AI 发言一致。
            speed=request.speed,
            db=db,
        )
        if not audio_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="语音合成失败")

        audio_base64 = voice_processor.encode_audio_base64(audio_data)
        data: Dict[str, Any] = {"audio_base64": audio_base64, "format": "wav"}
        return {"code": 200, "message": "合成成功", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="语音合成失败")


@router.post("/tts/synthesize/file", summary="TTS语音合成（返回音频文件URL）")
async def synthesize_speech_to_file(
    request: TtsSynthesizeRequest,
    current_user: User = Depends(verify_token_middleware),
    db: Session = Depends(get_db),
):
    try:
        audio_data = await voice_processor.synthesize_speech(
            text=request.text,
            voice_id=request.voice_id or "Cherry",
            # 未显式传语速时，回退到后台 TTS 配置，保持和 AI 发言一致。
            speed=request.speed,
            db=db,
        )
        if not audio_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="语音合成失败")

        # 获取格式配置
        config_service = ConfigService(db)
        tts_config = await config_service.get_tts_config()
        audio_format = (tts_config.parameters.get("response_format") if tts_config and tts_config.parameters else None) or "mp3"
        
        # 生成文件名
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        short_id = str(uuid.uuid4())[:8]
        filename = f"tts_{timestamp}_{short_id}.{audio_format}"
        
        # 保存文件
        audio_path = await voice_processor.save_audio_file(audio_data, filename)
        
        if not audio_path:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存音频文件失败")

        raw_audio_url = voice_processor.build_audio_url(audio_path)
        if not raw_audio_url:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存音频文件失败")
        object_key = FileAccessService.media_object_key(raw_audio_url)
        ticket = FileAccessService.issue_media_ticket(
            user_id=str(current_user.id),
            object_key=object_key,
            owner_only=True,
        )
        audio_url = FileAccessService.ticketed_media_url(object_key, ticket)

        data: Dict[str, Any] = {"audio_url": audio_url, "format": audio_format}
        return {"code": 200, "message": "合成成功", "data": data}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS synthesis to file failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="语音合成失败")
