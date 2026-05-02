"""
语音处理服务
处理语音录制、ASR（语音识别）、TTS（语音合成）
"""

import os
import io
import time
import wave
import json
import base64
import queue
import httpx
import asyncio
import threading
import shutil
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Awaitable, List, AsyncIterator
from http import HTTPStatus
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from config import settings
import uuid
from pathlib import Path
from logging_config import get_logger
from utils.http_client_pool import async_http_client_pool

logger = get_logger(__name__)


class VoiceProcessor:
    """语音处理器类"""
    REALTIME_PCM_SAMPLE_RATE = 24000
    REALTIME_PCM_CHANNELS = 1
    REALTIME_PCM_SAMPLE_WIDTH = 2
    HTTP_TIMEOUT_SECONDS = 30.0

    def __init__(self):
        """初始化语音处理器"""
        self.asr_service_url = os.getenv(
            "ASR_SERVICE_URL", "https://api.openai.com/v1/audio/transcriptions"
        )
        self.tts_service_url = os.getenv(
            "TTS_SERVICE_URL", "https://api.openai.com/v1/audio/speech"
        )

    @staticmethod
    def _format_elapsed_seconds(elapsed_seconds: float) -> str:
        """
        统一格式化耗时日志，按秒输出并保留两位小数。
        """
        return f"{max(0.0, float(elapsed_seconds)):.2f}"

    def _log_tts_performance(self, stage: str, details: Dict[str, Any]) -> None:
        """
        统一输出 TTS 性能日志，便于按阶段检索排查。
        """
        logger.info(
            "TTS性能日志-%s: %s",
            stage,
            json.dumps(details, ensure_ascii=False),
        )

    def _get_asr_http_client(self) -> httpx.AsyncClient:
        """
        获取可复用的 ASR HTTP 客户端。
        """
        return async_http_client_pool.get_client(
            purpose="voice_asr",
            timeout=self.HTTP_TIMEOUT_SECONDS,
        )

    def _get_tts_http_client(self) -> httpx.AsyncClient:
        """
        获取可复用的 TTS HTTP 客户端。
        """
        return async_http_client_pool.get_client(
            purpose="voice_tts",
            timeout=self.HTTP_TIMEOUT_SECONDS,
        )

    @staticmethod
    def _is_valid_public_file_url_prefix(file_url_prefix: str) -> bool:
        normalized_prefix = (file_url_prefix or "").strip()
        if not normalized_prefix:
            return False

        parsed_prefix = urlparse(normalized_prefix)
        if parsed_prefix.scheme not in {"http", "https"}:
            return False
        if not parsed_prefix.netloc:
            return False

        hostname = (parsed_prefix.hostname or "").lower()
        return hostname not in {"localhost", "127.0.0.1"}

    def get_default_ai_tts_speed(self) -> float:
        """返回统一定义在 config.py 中的 TTS 默认语速。"""
        return settings.TTS_DEFAULT_SPEED

    def resolve_tts_speed(self, speed: Optional[float], config_speed: Any = None) -> float:
        """
        统一解析 TTS 语速。

        优先使用调用方显式传入的 speed；未传时再回退到后台配置；
        两者都不可用时，才使用系统默认值，避免不同链路出现不一致。
        """
        candidate_speed = speed if speed is not None else config_speed
        try:
            resolved_speed = float(candidate_speed)
        except (TypeError, ValueError):
            resolved_speed = settings.TTS_DEFAULT_SPEED

        if resolved_speed < 0.25 or resolved_speed > 4.0:
            return settings.TTS_DEFAULT_SPEED
        return resolved_speed

    async def _get_asr_config(self, db: Session):
        from services.config_service import ConfigService

        config_service = ConfigService(db)
        return await config_service.get_asr_config()

    async def _get_tts_config(self, db: Session):
        from services.config_service import ConfigService

        config_service = ConfigService(db)
        return await config_service.get_tts_config()

    async def transcribe_audio(
        self,
        audio_data: bytes,
        audio_format: str = "webm",
        language: str = "zh",
        db: Session = None,
    ) -> Dict[str, Any]:
        """
        将音频转换为文字（ASR）

        Args:
            audio_data: 音频数据（字节流）
            audio_format: 音频格式（webm, mp3, wav等）
            language: 语言代码（zh, en等）
            db: 数据库会话（用于获取配置）

        Returns:
            Dict包含：
            - text: 识别的文字
            - duration: 音频时长（秒）
            - confidence: 置信度（0-1）
        """
        try:
            # 验证音频质量
            is_valid, message = await self.validate_audio_quality(audio_data)
            if not is_valid:
                logger.warning(f"Audio quality validation failed: {message}")
                return {"text": "", "duration": 0, "confidence": 0.0, "error": message}

            # 获取API密钥
            if not db:
                logger.error("Database session required for configuration")
                return {
                    "text": "",
                    "duration": 0,
                    "confidence": 0.0,
                    "error": "数据库会话未提供",
                }

            asr_config = await self._get_asr_config(db)
            api_key = asr_config.api_key if asr_config else ""
            if not api_key:
                logger.error("OpenAI API key not configured")
                return {
                    "text": "",
                    "duration": 0,
                    "confidence": 0.0,
                    "error": "ASR服务未配置",
                }

            provider = (
                (asr_config.parameters or {}).get("provider") if asr_config else None
            )
            model_name = (asr_config.model_name if asr_config else "") or ""
            api_endpoint = (asr_config.api_endpoint if asr_config else "") or ""
            parameters = (asr_config.parameters or {}) if asr_config else {}

            if provider in (
                "dashscope_realtime",
                "dashscope_sdk",
            ) or model_name.startswith("fun-asr-realtime"):
                return await self._dashscope_sdk_transcribe_local(
                    audio_data=audio_data,
                    audio_format=audio_format,
                    language=language,
                    api_key=api_key,
                    model_name=model_name,
                    parameters=parameters,
                )

            if (
                provider == "dashscope"
                or model_name.startswith("qwen")
                or ("dashscope" in api_endpoint)
            ):
                return await self._dashscope_transcribe_filetrans(
                    audio_data=audio_data,
                    audio_format=audio_format,
                    language=language,
                    api_key=api_key,
                    api_endpoint=api_endpoint or settings.ASR_API_ENDPOINT,
                    model_name=model_name or settings.ASR_MODEL_NAME,
                    parameters=parameters,
                )

            # 调用OpenAI Whisper API
            # 复用 ASR 连接池，减少连续识别时重复建连和 TLS 握手。
            async with async_http_client_pool.use_client(
                purpose="voice_asr",
                timeout=self.HTTP_TIMEOUT_SECONDS,
            ) as client:
                files = {
                    "file": (
                        f"audio.{audio_format}",
                        audio_data,
                        f"audio/{audio_format}",
                    )
                }
                default_language = (
                    (asr_config.parameters or {}).get("language")
                    if asr_config
                    else None
                )
                response_format = (
                    (asr_config.parameters or {}).get("response_format")
                    if asr_config
                    else None
                )
                data = {
                    "model": (asr_config.model_name if asr_config else "whisper-1"),
                    "language": language or default_language or "zh",
                    "response_format": response_format or "verbose_json",
                }
                headers = {"Authorization": f"Bearer {api_key}"}

                response = await client.post(
                    (asr_config.api_endpoint if asr_config else self.asr_service_url),
                    files=files,
                    data=data,
                    headers=headers,
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "text": result.get("text", ""),
                        "duration": result.get("duration", 0),
                        "confidence": 1.0,  # Whisper不返回置信度，默认为1.0
                        "language": result.get("language", language),
                    }
                else:
                    error_msg = (
                        f"ASR service error: {response.status_code} - {response.text}"
                    )
                    logger.error(error_msg)
                    return {
                        "text": "",
                        "duration": 0,
                        "confidence": 0.0,
                        "error": error_msg,
                    }

        except httpx.TimeoutException:
            logger.error("ASR service timeout")
            return {
                "text": "",
                "duration": 0,
                "confidence": 0.0,
                "error": "ASR服务超时",
            }
        except Exception as e:
            logger.error(f"ASR transcription failed: {e}", exc_info=True)
            return {"text": "", "duration": 0, "confidence": 0.0, "error": str(e)}

    async def synthesize_speech(
        self,
        text: str,
        voice_id: str = "Cherry",
        speed: Optional[float] = None,
        db: Session = None,
    ) -> Optional[bytes]:
        """
        将文字转换为语音（TTS）

        Args:
            text: 要转换的文字
            voice_id: 语音ID（Cherry, Serena, Ethan, Moon）
            speed: 语速（0.25-4.0）
            db: 数据库会话（用于获取配置）

        Returns:
            音频数据（字节流），失败返回None
        """
        try:
            if not text or not text.strip():
                logger.warning("Empty text for TTS")
                return None

            # 获取API密钥
            if not db:
                logger.error("Database session required for configuration")
                return None

            tts_config = await self._get_tts_config(db)
            api_key = tts_config.api_key if tts_config else ""
            if not api_key:
                logger.error("OpenAI API key not configured")
                return None

            config_speed = (
                (tts_config.parameters or {}).get("speed") if tts_config else None
            )
            # 显式传参优先；未传时回退到后台配置；再不行才使用系统默认值。
            resolved_speed = self.resolve_tts_speed(speed, config_speed)

            provider = (
                (tts_config.parameters or {}).get("provider") if tts_config else None
            )
            if (
                provider == "dashscope"
                or (tts_config.model_name if tts_config else "").startswith("qwen")
                or ("dashscope" in (tts_config.api_endpoint if tts_config else ""))
            ):
                audio_bytes = await self._dashscope_tts(
                    text=text,
                    voice=voice_id,
                    api_key=api_key,
                    api_endpoint=(
                        tts_config.api_endpoint
                        if tts_config
                        else settings.TTS_API_ENDPOINT
                    ),
                    model_name=(
                        tts_config.model_name if tts_config else settings.TTS_MODEL_NAME
                    ),
                    speed=resolved_speed,
                    parameters=(tts_config.parameters or {}) if tts_config else {},
                )
                return audio_bytes

            # 调用OpenAI TTS API
            # 复用 TTS 连接池，减少高频合成时重复建连和握手成本。
            async with async_http_client_pool.use_client(
                purpose="voice_tts",
                timeout=self.HTTP_TIMEOUT_SECONDS,
            ) as client:
                default_voice = ((tts_config.parameters or {}).get("voice") if tts_config else None)
                response_format = (
                    (tts_config.parameters or {}).get("response_format")
                    if tts_config
                    else None
                )
                payload = {
                    "model": (tts_config.model_name if tts_config else "tts-1"),
                    "input": text,
                    "voice": voice_id or default_voice or "alloy",
                    "speed": resolved_speed,
                    "response_format": response_format or "mp3",
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

                response = await client.post(
                    (tts_config.api_endpoint if tts_config else self.tts_service_url),
                    json=payload,
                    headers=headers,
                )

                if response.status_code == 200:
                    return response.content
                else:
                    error_msg = (
                        f"TTS service error: {response.status_code} - {response.text}"
                    )
                    logger.error(error_msg)
                    return None

        except httpx.TimeoutException:
            logger.error("TTS service timeout")
            return None
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}", exc_info=True)
            return None

    async def synthesize_speech_stream(
        self,
        text: str,
        voice_id: str = "Cherry",
        speed: Optional[float] = None,
        db: Session = None,
        on_chunk: Optional[Callable[[bytes], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        使用真正流式TTS返回音频分块，并在结束后返回完整音频。
        目前优先接入DashScope realtime TTS，其它提供商继续走原有整段TTS链路。
        """
        if not text or not text.strip():
            logger.warning("Empty text for streaming TTS")
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": 0,
                "used_streaming": False,
                "error": "TTS文本为空",
            }

        if not db:
            logger.error("Database session required for streaming TTS configuration")
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": 0,
                "used_streaming": False,
                "error": "数据库会话未提供",
            }

        tts_config = await self._get_tts_config(db)
        api_key = tts_config.api_key if tts_config else ""
        if not api_key:
            logger.error("Streaming TTS API key not configured")
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": 0,
                "used_streaming": False,
                "error": "TTS服务未配置",
            }

        provider = (
            (tts_config.parameters or {}).get("provider") if tts_config else None
        )
        model_name = (tts_config.model_name if tts_config else "") or ""
        api_endpoint = (tts_config.api_endpoint if tts_config else "") or ""
        parameters = (tts_config.parameters or {}) if tts_config else {}
        resolved_speed = self.resolve_tts_speed(speed, parameters.get("speed"))
        is_dashscope_tts = (
            provider == "dashscope"
            or model_name.startswith("qwen")
            or ("dashscope" in api_endpoint)
        )

        if not is_dashscope_tts:
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": 0,
                "used_streaming": False,
                "error": "当前TTS配置不支持实时流式输出",
            }

        return await self._dashscope_tts_realtime(
            text=text,
            voice=voice_id,
            speed=resolved_speed,
            api_key=api_key,
            model_name=model_name or "qwen3-tts-instruct-flash-realtime",
            parameters=parameters,
            on_chunk=on_chunk,
        )

    async def synthesize_speech_stream_live(
        self,
        text_source: AsyncIterator[str],
        voice_id: str = "Cherry",
        speed: Optional[float] = None,
        db: Session = None,
        on_chunk: Optional[Callable[[bytes], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        持续消费文本流并复用同一个 realtime TTS 会话。
        这样可以把 AI 的增量文本边生成边送入 TTS。
        """
        if not db:
            logger.error("Database session required for live streaming TTS configuration")
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": 0,
                "used_streaming": False,
                "error": "缺少数据库会话",
            }

        tts_config = await self._get_tts_config(db)
        api_key = tts_config.api_key if tts_config else ""
        if not api_key:
            logger.error("Live streaming TTS API key not configured")
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": 0,
                "used_streaming": False,
                "error": "TTS API Key 未配置",
            }

        provider = (
            (tts_config.parameters or {}).get("provider") if tts_config else None
        )
        model_name = (tts_config.model_name if tts_config else "") or ""
        api_endpoint = (tts_config.api_endpoint if tts_config else "") or ""
        parameters = (tts_config.parameters or {}) if tts_config else {}
        resolved_speed = self.resolve_tts_speed(speed, parameters.get("speed"))
        is_dashscope_tts = (
            provider == "dashscope"
            or model_name.startswith("qwen")
            or ("dashscope" in api_endpoint)
        )

        if not is_dashscope_tts:
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": 0,
                "used_streaming": False,
                "error": "当前TTS配置不支持实时流式合成",
            }

        return await self._dashscope_tts_realtime_live(
            text_source=text_source,
            voice=voice_id,
            speed=resolved_speed,
            api_key=api_key,
            model_name=model_name or "qwen3-tts-instruct-flash-realtime",
            parameters=parameters,
            on_chunk=on_chunk,
        )

    async def _dashscope_tts(
        self,
        text: str,
        voice: Optional[str],
        api_key: str,
        api_endpoint: str,
        model_name: str,
        speed: Optional[float],
        parameters: Dict[str, Any],
    ) -> Optional[bytes]:
        voice_name = voice or parameters.get("voice") or "Cherry"
        language_type = parameters.get("language_type") or "Chinese"
        resolved_speed = self.resolve_tts_speed(speed, parameters.get("speed"))
        payload = {
            "model": model_name or "qwen3-tts-flash",
            "input": {
                "text": text,
                "voice": voice_name,
                "language_type": language_type,
            },
            # 非流式链路也带上语速参数，保证后台配置在兜底场景里同样生效。
            "parameters": {
                "speech_rate": resolved_speed,
            },
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # DashScope TTS 同样走复用池，避免合成和音频下载阶段重复建连。
        async with async_http_client_pool.use_client(
            purpose="voice_tts",
            timeout=self.HTTP_TIMEOUT_SECONDS,
        ) as client:
            response = await client.post(api_endpoint, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(
                    f"TTS service error: {response.status_code} - {response.text}"
                )
                return None

            data = response.json()
            output = data.get("output") or {}
            audio = output.get("audio") or {}

            if isinstance(audio, dict) and audio.get("data"):
                try:
                    return base64.b64decode(audio["data"])
                except Exception:
                    return None

            audio_url = audio.get("url")
            if not audio_url:
                return None

            audio_resp = await client.get(audio_url)
            if audio_resp.status_code != 200:
                logger.error(
                    f"TTS audio download error: {audio_resp.status_code} - {audio_resp.text}"
                )
                return None
            return audio_resp.content

    async def _dashscope_tts_realtime(
        self,
        text: str,
        voice: Optional[str],
        speed: Optional[float],
        api_key: str,
        model_name: str,
        parameters: Dict[str, Any],
        on_chunk: Optional[Callable[[bytes], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        使用DashScope realtime websocket做真正流式TTS。
        SDK回调在其它线程里触发，这里通过asyncio队列桥接回当前事件循环。
        """
        loop = asyncio.get_running_loop()
        event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        sample_rate = int(
            parameters.get("sample_rate") or self.REALTIME_PCM_SAMPLE_RATE
        )
        channels = int(parameters.get("channels") or self.REALTIME_PCM_CHANNELS)
        sample_width = int(
            parameters.get("sample_width") or self.REALTIME_PCM_SAMPLE_WIDTH
        )
        stream_chunks: List[bytes] = []

        def _push_event(event: Dict[str, Any]) -> None:
            try:
                asyncio.run_coroutine_threadsafe(event_queue.put(event), loop)
            except Exception as exc:
                logger.warning(f"Failed to forward realtime TTS event: {exc}")

        class _RealtimeCallback:
            """本地回调适配器，只负责把SDK事件转到当前协程。"""

            def __init__(self):
                self.complete_event = threading.Event()

            def on_open(self) -> None:
                _push_event({"type": "open"})

            def on_close(self, close_status_code, close_msg) -> None:
                _push_event(
                    {
                        "type": "close",
                        "close_status_code": close_status_code,
                        "close_msg": close_msg,
                    }
                )
                self.complete_event.set()

            def on_event(self, response: Dict[str, Any]) -> None:
                try:
                    event_type = (response or {}).get("type")
                    if event_type == "response.audio.delta":
                        chunk = base64.b64decode(response.get("delta") or b"")
                        if chunk:
                            _push_event({"type": "audio", "audio": chunk})
                        return
                    if event_type == "response.done":
                        _push_event({"type": "response_done"})
                        return
                    if event_type == "session.finished":
                        _push_event({"type": "session_finished"})
                        self.complete_event.set()
                except Exception as exc:
                    _push_event({"type": "error", "error": str(exc)})
                    self.complete_event.set()

            def wait_for_finished(self) -> None:
                self.complete_event.wait()

        def _run_realtime_session() -> None:
            try:
                import dashscope
                from dashscope.audio.qwen_tts_realtime import (
                    AudioFormat,
                    QwenTtsRealtime,
                    QwenTtsRealtimeCallback,
                )
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "未安装DashScope realtime TTS依赖，请先确认 dashscope 包可用"
                ) from exc

            callback_impl = _RealtimeCallback()

            class _SdkCallback(QwenTtsRealtimeCallback):
                """转发SDK事件，避免把业务逻辑散在SDK子类中。"""

                def on_open(self) -> None:
                    callback_impl.on_open()

                def on_close(self, close_status_code, close_msg) -> None:
                    callback_impl.on_close(close_status_code, close_msg)

                def on_event(self, response: Dict[str, Any]) -> None:
                    callback_impl.on_event(response)

            dashscope.api_key = api_key
            client = QwenTtsRealtime(model=model_name, callback=_SdkCallback())
            client.connect()
            resolved_speed = self.resolve_tts_speed(speed, parameters.get("speed"))
            client.update_session(
                voice=voice or parameters.get("voice") or "Cherry",
                response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
                mode=parameters.get("mode") or "server_commit",
                speech_rate=resolved_speed,
                language_type=parameters.get("language_type") or "Chinese",
            )

            # 先按短句切块，再逐段提交给realtime会话，保证首包尽快返回。
            append_interval = float(parameters.get("append_interval_seconds") or 0.05)
            for text_chunk in self.split_text_for_streaming_tts(text):
                if not text_chunk:
                    continue
                client.append_text(text_chunk)
                if append_interval > 0:
                    time.sleep(append_interval)

            client.finish()
            callback_impl.wait_for_finished()

        worker_task = asyncio.create_task(asyncio.to_thread(_run_realtime_session))
        saw_session_finish = False

        try:
            while True:
                if (
                    worker_task.done()
                    and saw_session_finish
                    and event_queue.empty()
                ):
                    break

                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    if worker_task.done() and event_queue.empty():
                        break
                    continue

                event_type = event.get("type")
                if event_type == "audio":
                    audio_chunk = event.get("audio") or b""
                    if audio_chunk:
                        stream_chunks.append(audio_chunk)
                        if on_chunk:
                            await on_chunk(audio_chunk)
                elif event_type == "session_finished":
                    saw_session_finish = True
                elif event_type == "error":
                    raise RuntimeError(event.get("error") or "realtime TTS回调失败")

            await worker_task
        except Exception as exc:
            if not worker_task.done():
                worker_task.cancel()
            logger.error(f"DashScope realtime TTS failed: {exc}", exc_info=True)
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": len(stream_chunks),
                "used_streaming": True,
                "sample_rate": sample_rate,
                "channels": channels,
                "sample_width": sample_width,
                "error": str(exc),
            }

        if not stream_chunks:
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": 0,
                "used_streaming": True,
                "sample_rate": sample_rate,
                "channels": channels,
                "sample_width": sample_width,
                "error": "realtime TTS未返回音频分块",
            }

        pcm_audio = b"".join(stream_chunks)
        wav_audio = self.wrap_pcm_to_wav(
            pcm_audio=pcm_audio,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
        )
        return {
            "audio_data": wav_audio,
            "audio_format": "wav",
            "chunk_count": len(stream_chunks),
            "used_streaming": True,
            "sample_rate": sample_rate,
            "channels": channels,
            "sample_width": sample_width,
            "error": None,
        }

    async def _dashscope_tts_realtime_live(
        self,
        text_source: AsyncIterator[str],
        voice: Optional[str],
        speed: Optional[float],
        api_key: str,
        model_name: str,
        parameters: Dict[str, Any],
        on_chunk: Optional[Callable[[bytes], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        使用 DashScope realtime TTS 持续接收文本片段并返回流式音频。
        """
        loop = asyncio.get_running_loop()
        event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        text_queue: queue.Queue[Any] = queue.Queue()
        stream_chunks: List[bytes] = []
        sample_rate = int(parameters.get("sample_rate") or self.REALTIME_PCM_SAMPLE_RATE)
        channels = int(parameters.get("channels") or self.REALTIME_PCM_CHANNELS)
        sample_width = int(parameters.get("sample_width") or self.REALTIME_PCM_SAMPLE_WIDTH)
        sentinel = object()
        request_started_at = time.perf_counter()
        text_chunk_count = 0
        total_text_request_elapsed_seconds = 0.0
        first_request_content = ""

        def _push_event(event: Dict[str, Any]) -> None:
            try:
                asyncio.run_coroutine_threadsafe(event_queue.put(event), loop)
            except Exception as exc:
                logger.warning(f"Failed to forward live realtime TTS event: {exc}")

        async def _pump_text_chunks() -> None:
            try:
                async for raw_chunk in text_source:
                    text_chunk = (raw_chunk or "").strip()
                    if text_chunk:
                        text_queue.put(text_chunk)
            except Exception as exc:
                _push_event({"type": "error", "error": f"实时TTS文本流读取失败: {exc}"})
            finally:
                text_queue.put(sentinel)

        class _RealtimeCallback:
            """把 SDK 回调转换为 asyncio 事件，便于主协程统一处理。"""

            def __init__(self):
                self.complete_event = threading.Event()

            def on_open(self) -> None:
                _push_event({"type": "open"})

            def on_close(self, close_status_code, close_msg) -> None:
                _push_event(
                    {
                        "type": "close",
                        "close_status_code": close_status_code,
                        "close_msg": close_msg,
                    }
                )
                self.complete_event.set()

            def on_event(self, response: Dict[str, Any]) -> None:
                try:
                    event_type = (response or {}).get("type")
                    if event_type == "response.audio.delta":
                        chunk = base64.b64decode(response.get("delta") or b"")
                        if chunk:
                            _push_event({"type": "audio", "audio": chunk})
                        return
                    if event_type == "response.done":
                        _push_event({"type": "response_done"})
                        return
                    if event_type == "session.finished":
                        _push_event({"type": "session_finished"})
                        self.complete_event.set()
                except Exception as exc:
                    _push_event({"type": "error", "error": str(exc)})
                    self.complete_event.set()

            def wait_for_finished(self) -> None:
                self.complete_event.wait()

        def _run_realtime_session() -> None:
            nonlocal text_chunk_count
            nonlocal total_text_request_elapsed_seconds
            nonlocal first_request_content
            try:
                import dashscope
                from dashscope.audio.qwen_tts_realtime import (
                    AudioFormat,
                    QwenTtsRealtime,
                    QwenTtsRealtimeCallback,
                )
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "未安装 DashScope realtime TTS 依赖，请先安装 dashscope"
                ) from exc

            callback_impl = _RealtimeCallback()

            class _SdkCallback(QwenTtsRealtimeCallback):
                def on_open(self) -> None:
                    callback_impl.on_open()

                def on_close(self, close_status_code, close_msg) -> None:
                    callback_impl.on_close(close_status_code, close_msg)

                def on_event(self, response: Dict[str, Any]) -> None:
                    callback_impl.on_event(response)

            dashscope.api_key = api_key
            client = QwenTtsRealtime(model=model_name, callback=_SdkCallback())
            client.connect()
            resolved_speed = self.resolve_tts_speed(speed, parameters.get("speed"))
            client.update_session(
                voice=voice or parameters.get("voice") or "Cherry",
                response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
                mode=parameters.get("mode") or "server_commit",
                speech_rate=resolved_speed,
                language_type=parameters.get("language_type") or "Chinese",
            )

            append_interval = float(parameters.get("append_interval_seconds") or 0.05)
            while True:
                item = text_queue.get()
                if item is sentinel:
                    break
                append_started_at = time.perf_counter()
                if text_chunk_count == 0:
                    first_request_content = str(item)
                    # 记录 realtime TTS 首次收到文本时的输入内容，便于核对与 LLM 分块是否一致。
                    self._log_tts_performance(
                        "流式请求开始",
                        {
                            "model": model_name,
                            "voice": voice or parameters.get("voice") or "Cherry",
                            "start_request_content": first_request_content,
                        },
                    )
                client.append_text(item)
                append_finished_at = time.perf_counter()
                text_chunk_count += 1
                total_text_request_elapsed_seconds += (
                    append_finished_at - append_started_at
                )
                # 逐块记录发送给 TTS 的文本和该次发送耗时，便于分析哪一块阻塞明显。
                self._log_tts_performance(
                    "文本块发送",
                    {
                        "model": model_name,
                        "voice": voice or parameters.get("voice") or "Cherry",
                        "chunk_index": text_chunk_count,
                        "chunk_content": str(item),
                        "chunk_request_elapsed_seconds": self._format_elapsed_seconds(
                            append_finished_at - append_started_at
                        ),
                        "all_chunk_request_elapsed_seconds": self._format_elapsed_seconds(
                            total_text_request_elapsed_seconds
                        ),
                        "all_content_elapsed_seconds": self._format_elapsed_seconds(
                            append_finished_at - request_started_at
                        ),
                    },
                )
                if append_interval > 0:
                    time.sleep(append_interval)

            client.finish()
            callback_impl.wait_for_finished()

        producer_task = asyncio.create_task(_pump_text_chunks())
        worker_task = asyncio.create_task(asyncio.to_thread(_run_realtime_session))
        saw_session_finish = False

        try:
            while True:
                if worker_task.done() and saw_session_finish and event_queue.empty():
                    break

                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    if worker_task.done() and event_queue.empty():
                        break
                    continue

                event_type = event.get("type")
                if event_type == "audio":
                    audio_chunk = event.get("audio") or b""
                    if audio_chunk:
                        stream_chunks.append(audio_chunk)
                        if on_chunk:
                            await on_chunk(audio_chunk)
                elif event_type == "session_finished":
                    saw_session_finish = True
                elif event_type == "error":
                    raise RuntimeError(event.get("error") or "live realtime TTS 执行失败")

            await producer_task
            await worker_task
        except Exception as exc:
            if not producer_task.done():
                producer_task.cancel()
            if not worker_task.done():
                worker_task.cancel()
            logger.error(f"DashScope live realtime TTS failed: {exc}", exc_info=True)
            self._log_tts_performance(
                "流式请求失败",
                {
                    "model": model_name,
                    "voice": voice or parameters.get("voice") or "Cherry",
                    "start_request_content": first_request_content,
                    "text_chunk_count": text_chunk_count,
                    "audio_chunk_count": len(stream_chunks),
                    "all_chunk_request_elapsed_seconds": self._format_elapsed_seconds(
                        total_text_request_elapsed_seconds
                    ),
                    "all_content_elapsed_seconds": self._format_elapsed_seconds(
                        time.perf_counter() - request_started_at
                    ),
                    "error": str(exc),
                },
            )
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": len(stream_chunks),
                "used_streaming": True,
                "sample_rate": sample_rate,
                "channels": channels,
                "sample_width": sample_width,
                "error": str(exc),
            }

        if not stream_chunks:
            self._log_tts_performance(
                "流式请求完成",
                {
                    "model": model_name,
                    "voice": voice or parameters.get("voice") or "Cherry",
                    "start_request_content": first_request_content,
                    "text_chunk_count": text_chunk_count,
                    "audio_chunk_count": 0,
                    "all_chunk_request_elapsed_seconds": self._format_elapsed_seconds(
                        total_text_request_elapsed_seconds
                    ),
                    "all_content_elapsed_seconds": self._format_elapsed_seconds(
                        time.perf_counter() - request_started_at
                    ),
                    "error": "live realtime TTS 未返回任何音频数据",
                },
            )
            return {
                "audio_data": None,
                "audio_format": None,
                "chunk_count": 0,
                "used_streaming": True,
                "sample_rate": sample_rate,
                "channels": channels,
                "sample_width": sample_width,
                "error": "live realtime TTS 未返回任何音频数据",
            }

        pcm_audio = b"".join(stream_chunks)
        wav_audio = self.wrap_pcm_to_wav(
            pcm_audio=pcm_audio,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
        )
        self._log_tts_performance(
            "流式请求完成",
            {
                "model": model_name,
                "voice": voice or parameters.get("voice") or "Cherry",
                "start_request_content": first_request_content,
                "text_chunk_count": text_chunk_count,
                "audio_chunk_count": len(stream_chunks),
                "all_chunk_request_elapsed_seconds": self._format_elapsed_seconds(
                    total_text_request_elapsed_seconds
                ),
                "all_content_elapsed_seconds": self._format_elapsed_seconds(
                    time.perf_counter() - request_started_at
                ),
            },
        )
        return {
            "audio_data": wav_audio,
            "audio_format": "wav",
            "chunk_count": len(stream_chunks),
            "used_streaming": True,
            "sample_rate": sample_rate,
            "channels": channels,
            "sample_width": sample_width,
            "error": None,
        }

    async def _dashscope_transcribe_filetrans(
        self,
        audio_data: bytes,
        audio_format: str,
        language: str,
        api_key: str,
        api_endpoint: str,
        model_name: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        file_url = await self._persist_audio_for_dashscope(
            audio_data, audio_format, parameters
        )
        if not file_url:
            return {
                "text": "",
                "duration": 0,
                "confidence": 0.0,
                "error": "ASR音频文件URL前缀未配置（管理员端ASR配置->音频文件URL前缀，或设置PUBLIC_BASE_URL）",
            }

        payload = {
            "model": model_name or "qwen3-asr-flash-filetrans",
            "input": {"file_url": file_url},
            "parameters": {
                "channel_id": parameters.get("channel_id") or [0],
                "enable_itn": bool(parameters.get("enable_itn", False)),
                "enable_words": bool(parameters.get("enable_words", True)),
            },
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

        task_base_url = parameters.get("task_base_url")
        if not task_base_url:
            if "/api/v1/" in api_endpoint:
                task_base_url = api_endpoint.split("/api/v1/")[0] + "/api/v1"
            else:
                task_base_url = "https://dashscope.aliyuncs.com/api/v1"

        poll_interval = float(parameters.get("poll_interval_seconds", 0.5))
        poll_timeout = float(parameters.get("poll_timeout_seconds", 20))

        # 文件转写会经历提交任务和轮询结果两个阶段，复用同一个客户端可降低固定耗时。
        async with async_http_client_pool.use_client(
            purpose="voice_asr",
            timeout=self.HTTP_TIMEOUT_SECONDS,
        ) as client:
            resp = await client.post(api_endpoint, json=payload, headers=headers)
            if resp.status_code != 200:
                return {
                    "text": "",
                    "duration": 0,
                    "confidence": 0.0,
                    "error": f"ASR service error: {resp.status_code} - {resp.text}",
                }
            data = resp.json()
            output = data.get("output") or {}
            task_id = (
                output.get("task_id") or output.get("taskId") or data.get("task_id")
            )
            if not task_id:
                return {
                    "text": "",
                    "duration": 0,
                    "confidence": 0.0,
                    "error": "ASR未返回task_id",
                }

            start = datetime.utcnow()
            status_url = f"{task_base_url}/tasks/{task_id}"
            while (datetime.utcnow() - start).total_seconds() <= poll_timeout:
                status_resp = await client.get(
                    status_url, headers={"Authorization": f"Bearer {api_key}"}
                )
                if status_resp.status_code != 200:
                    await asyncio.sleep(poll_interval)
                    continue

                status_data = status_resp.json()
                status_output = status_data.get("output") or {}
                task_status = (
                    status_output.get("task_status")
                    or status_output.get("taskStatus")
                    or status_data.get("task_status")
                )
                if task_status in ("PENDING", "RUNNING"):
                    await asyncio.sleep(poll_interval)
                    continue

                if task_status != "SUCCEEDED":
                    msg = (
                        status_data.get("message")
                        or status_output.get("message")
                        or "ASR任务失败"
                    )
                    return {
                        "text": "",
                        "duration": 0,
                        "confidence": 0.0,
                        "error": msg,
                    }

                results = status_output.get("results") or []
                transcription_url = None
                if isinstance(results, list) and results:
                    transcription_url = results[0].get("transcription_url") or results[
                        0
                    ].get("transcriptionUrl")

                if transcription_url:
                    tr_resp = await client.get(transcription_url)
                    if tr_resp.status_code == 200:
                        try:
                            tr_json = tr_resp.json()
                        except Exception:
                            tr_json = None
                        text = (
                            self._extract_text_from_transcription(tr_json)
                            if tr_json
                            else ""
                        )
                        return {
                            "text": text,
                            "duration": 0,
                            "confidence": 1.0 if text else 0.0,
                            "language": language,
                        }

                text = self._extract_text_from_transcription(status_output)
                return {
                    "text": text,
                    "duration": 0,
                    "confidence": 1.0 if text else 0.0,
                    "language": language,
                }

            return {
                "text": "",
                "duration": 0,
                "confidence": 0.0,
                "error": "ASR任务超时",
            }

    async def _dashscope_sdk_transcribe_local(
        self,
        audio_data: bytes,
        audio_format: str,
        language: str,
        api_key: str,
        model_name: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        tmp_dir = Path(settings.UPLOAD_DIR) / "asr_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        src_format = (audio_format or "wav").lower().strip()
        src_path = tmp_dir / f"{uuid.uuid4().hex}.{src_format}"
        src_path.write_bytes(audio_data)

        wav_path: Optional[Path] = None
        try:
            if src_format in ("wav", "pcm"):
                wav_path = src_path
            else:
                ffmpeg_path = shutil.which("ffmpeg")
                if not ffmpeg_path:
                    fallback_model_name = str(
                        parameters.get("fallback_model_name") or ""
                    ).strip()
                    if not fallback_model_name:
                        configured_model_name = str(
                            settings.ASR_MODEL_NAME or ""
                        ).strip()
                        fallback_model_name = (
                            configured_model_name
                            if configured_model_name
                            and not configured_model_name.startswith(
                                "fun-asr-realtime"
                            )
                            else "qwen3-asr-flash-filetrans"
                        )

                    fallback_api_endpoint = str(
                        parameters.get("fallback_api_endpoint") or ""
                    ).strip()
                    if not fallback_api_endpoint:
                        configured_api_endpoint = str(
                            settings.ASR_API_ENDPOINT or ""
                        ).strip()
                        if configured_api_endpoint.lower().startswith(
                            ("http://", "https://")
                        ):
                            fallback_api_endpoint = configured_api_endpoint
                        else:
                            fallback_api_endpoint = (
                                "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
                            )

                    fallback_parameters = dict(parameters or {})
                    fallback_parameters["provider"] = "dashscope"
                    fallback_result = await self._dashscope_transcribe_filetrans(
                        audio_data=audio_data,
                        audio_format=src_format,
                        language=language,
                        api_key=api_key,
                        api_endpoint=fallback_api_endpoint,
                        model_name=fallback_model_name,
                        parameters=fallback_parameters,
                    )
                    if fallback_result.get("error"):
                        fallback_result["error"] = (
                            "DashScope fun-asr-realtime needs WAV/PCM (16k mono). "
                            f"Current audio format={src_format}, ffmpeg not found; "
                            "auto-fallback to file transcription also failed: "
                            f"{fallback_result['error']}"
                        )
                    else:
                        fallback_result["warning"] = (
                            "ffmpeg not found; auto-fallback to DashScope file transcription"
                        )
                    return fallback_result
                    return {
                        "text": "",
                        "duration": 0,
                        "confidence": 0.0,
                        "error": f"DashScope fun-asr-realtime 需要WAV/PCM(16k单声道)。当前音频格式={src_format}，且未找到ffmpeg用于转码",
                    }

                wav_path = tmp_dir / f"{uuid.uuid4().hex}.wav"
                cmd = [
                    ffmpeg_path,
                    "-y",
                    "-i",
                    str(src_path),
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    str(wav_path),
                ]
                proc = await asyncio.to_thread(
                    lambda: subprocess.run(cmd, capture_output=True, text=True)
                )
                if proc.returncode != 0 or not wav_path.exists():
                    detail = (proc.stderr or proc.stdout or "").strip()
                    return {
                        "text": "",
                        "duration": 0,
                        "confidence": 0.0,
                        "error": f"音频转码失败（{src_format} -> wav 16k mono）：{detail or 'unknown error'}",
                    }

            sample_rate = int(parameters.get("sample_rate") or 16000)
            fmt = parameters.get("format") or "wav"
            language_hints = parameters.get("language_hints")
            if not isinstance(language_hints, list) or not language_hints:
                language_hints = [language] if language else ["zh", "en"]

            def call_recognition():
                import dashscope
                from dashscope.audio.asr import Recognition

                dashscope.api_key = api_key
                recognition = Recognition(
                    model=model_name or "fun-asr-realtime-2025-11-07",
                    format=fmt,
                    sample_rate=sample_rate,
                    language_hints=language_hints,
                    callback=None,
                )
                return recognition.call(str(wav_path))

            try:
                result = await asyncio.to_thread(call_recognition)
            except ModuleNotFoundError:
                return {
                    "text": "",
                    "duration": 0,
                    "confidence": 0.0,
                    "error": "未安装dashscope SDK，请先安装依赖：pip install dashscope>=1.25.16",
                }

            status_code = getattr(result, "status_code", None)
            if status_code == HTTPStatus.OK:
                text = ""
                try:
                    text = result.get_sentence() or ""
                except Exception:
                    text = ""
                return {
                    "text": text,
                    "duration": 0,
                    "confidence": 1.0 if text else 0.0,
                    "language": language,
                }

            message = getattr(result, "message", "") or ""
            return {
                "text": "",
                "duration": 0,
                "confidence": 0.0,
                "error": message or f"DashScope ASR失败: status_code={status_code}",
            }
        finally:
            try:
                if src_path.exists() and src_path != wav_path:
                    src_path.unlink(missing_ok=True)
            except Exception:
                pass
            try:
                if wav_path and wav_path.exists() and wav_path != src_path:
                    wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    async def _persist_audio_for_dashscope(
        self,
        audio_data: bytes,
        audio_format: str,
        parameters: Dict[str, Any],
    ) -> Optional[str]:
        file_url_prefix = (
            parameters.get("file_url_prefix")
            or parameters.get("fileUrlPrefix")
            or parameters.get("file_urlPrefix")
        )
        if isinstance(file_url_prefix, str):
            file_url_prefix = file_url_prefix.strip()
        else:
            file_url_prefix = ""

        if not self._is_valid_public_file_url_prefix(file_url_prefix):
            public_base_url = settings.PUBLIC_BASE_URL or os.getenv(
                "PUBLIC_BASE_URL", ""
            ).rstrip("/")
            if public_base_url:
                file_url_prefix = f"{public_base_url}/uploads/asr"
            else:
                return None

        upload_dir = Path(settings.UPLOAD_DIR) / "asr"
        upload_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.{audio_format}"
        path = upload_dir / filename
        path.write_bytes(audio_data)
        return f"{file_url_prefix.rstrip('/')}/{filename}"

    def _extract_text_from_transcription(self, payload: Any) -> str:
        if not payload:
            return ""
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            if isinstance(payload.get("text"), str):
                return payload["text"]
            if isinstance(payload.get("transcript"), str):
                return payload["transcript"]
            if isinstance(payload.get("transcripts"), list):
                parts = []
                for item in payload["transcripts"]:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                if parts:
                    return " ".join(parts).strip()
            if isinstance(payload.get("sentences"), list):
                parts = []
                for item in payload["sentences"]:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                if parts:
                    return "".join(parts).strip()
            output = payload.get("output")
            if output:
                return self._extract_text_from_transcription(output)
        if isinstance(payload, list):
            parts = [self._extract_text_from_transcription(x) for x in payload]
            return " ".join([p for p in parts if p]).strip()
        return ""

    def split_text_for_streaming_tts(
        self,
        text: str,
        max_chunk_chars: int = 60,
    ) -> List[str]:
        """
        将整段文本切成适合realtime TTS逐段提交的小块。
        优先按中文标点截断，避免一次性提交整段文本导致首包变慢。
        """
        normalized_text = (text or "").strip()
        if not normalized_text:
            return []

        chunks: List[str] = []
        current = ""
        split_points = "，。！？；：,.!?;:\n"

        for char in normalized_text:
            current += char
            if len(current) >= max_chunk_chars or char in split_points:
                chunk = current.strip()
                if chunk:
                    chunks.append(chunk)
                current = ""

        if current.strip():
            chunks.append(current.strip())

        return chunks

    def wrap_pcm_to_wav(
        self,
        pcm_audio: bytes,
        sample_rate: int,
        channels: int,
        sample_width: int,
    ) -> bytes:
        """
        把实时TTS返回的PCM字节流封装成WAV，便于落盘和后续回放。
        """
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_audio)
        return buffer.getvalue()

    async def validate_audio_quality(
        self,
        audio_data: bytes,
        min_size: int = 1024,  # 最小1KB
        max_size: int = 10 * 1024 * 1024,  # 最大10MB
    ) -> tuple[bool, str]:
        """
        验证音频质量

        Args:
            audio_data: 音频数据
            min_size: 最小文件大小（字节）
            max_size: 最大文件大小（字节）

        Returns:
            (是否有效, 错误消息)
        """
        try:
            # 检查音频数据是否为空
            if not audio_data:
                return False, "音频数据为空"

            # 检查文件大小
            audio_size = len(audio_data)
            if audio_size < min_size:
                return False, f"音频文件太小（{audio_size} bytes），可能录制失败"

            if audio_size > max_size:
                return (
                    False,
                    f"音频文件太大（{audio_size} bytes），超过{max_size}字节限制",
                )

            # 基本的音频格式检查（检查文件头）
            # WebM: 1A 45 DF A3
            # MP3: FF FB 或 FF F3 或 FF F2 或 ID3
            # WAV: 52 49 46 46 (RIFF)
            # OGG: 4F 67 67 53 (OggS)

            if len(audio_data) < 4:
                return False, "音频数据不完整"

            header = audio_data[:4]

            # 检查常见音频格式
            valid_formats = [
                b"\x1a\x45\xdf\xa3",  # WebM
                b"RIFF",  # WAV
                b"OggS",  # OGG
                b"ID3",  # MP3 with ID3
            ]

            # MP3可能以FF开头
            if header[0:1] == b"\xff" and header[1:2] in [b"\xfb", b"\xf3", b"\xf2"]:
                return True, ""

            # 检查其他格式
            for valid_header in valid_formats:
                if header.startswith(valid_header):
                    return True, ""

            # 如果格式不匹配，仍然允许（可能是其他有效格式）
            logger.warning(f"Unknown audio format, header: {header.hex()}")
            return True, ""

        except Exception as e:
            logger.error(f"Audio validation failed: {e}", exc_info=True)
            return False, f"音频验证失败: {str(e)}"

    async def save_audio_file(
        self, audio_data: bytes, filename: str, upload_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        保存音频文件到本地

        Args:
            audio_data: 音频数据
            filename: 文件名
            upload_dir: 上传目录

        Returns:
            文件路径，失败返回None
        """
        try:
            resolved_upload_dir = upload_dir or str(Path(settings.UPLOAD_DIR) / "audio")
            # 创建上传目录
            os.makedirs(resolved_upload_dir, exist_ok=True)

            # 生成完整路径
            file_path = os.path.join(resolved_upload_dir, filename)

            # 保存文件
            with open(file_path, "wb") as f:
                f.write(audio_data)

            logger.info(f"Audio file saved: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save audio file: {e}", exc_info=True)
            return None

    def build_audio_url(self, file_path: Optional[str]) -> Optional[str]:
        """
        将本地保存后的音频路径转换为前端可访问的URL。

        Args:
            file_path: 本地文件路径

        Returns:
            前端可访问的音频URL，转换失败返回None
        """
        if not file_path:
            return None

        normalized = str(file_path).replace("\\", "/")
        if normalized.startswith("uploads/"):
            return f"/uploads/{normalized[len('uploads/'):]}".replace("//", "/")
        if "uploads/" in normalized:
            return ("/" + normalized[normalized.find("uploads/") :]).replace("//", "/")
        return None

    def encode_audio_base64(self, audio_data: bytes) -> str:
        """
        将音频数据编码为Base64字符串

        Args:
            audio_data: 音频数据

        Returns:
            Base64编码的字符串
        """
        return base64.b64encode(audio_data).decode("utf-8")

    def decode_audio_base64(self, audio_base64: str) -> bytes:
        """
        将Base64字符串解码为音频数据

        Args:
            audio_base64: Base64编码的字符串

        Returns:
            音频数据（字节流）
        """
        return base64.b64decode(audio_base64)


# 全局实例
voice_processor = VoiceProcessor()
