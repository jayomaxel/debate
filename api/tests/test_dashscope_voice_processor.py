import asyncio
import pytest

from utils.voice_processor import voice_processor
from config import settings


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, content=b"", text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.content = content
        self.text = text or ""

    def json(self):
        return self._json_data


class DummyClient:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, headers=None, files=None, data=None):
        self.calls.append(("POST", url, json, headers))
        return self._responses.pop(0)

    async def get(self, url, headers=None):
        self.calls.append(("GET", url, None, headers))
        return self._responses.pop(0)


def test_dashscope_tts_returns_wav_bytes(monkeypatch):
    dummy_audio = b"RIFF....WAVE"
    responses = [
        DummyResponse(
            200,
            json_data={"output": {"audio": {"url": "https://example.com/audio.wav"}}},
        ),
        DummyResponse(200, content=dummy_audio),
    ]

    def client_factory(*args, **kwargs):
        return DummyClient(responses)

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    audio = asyncio.run(
        voice_processor._dashscope_tts(
            text="你好",
            voice="Cherry",
            api_key="test-key",
            api_endpoint="https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
            model_name="qwen3-tts-flash",
            speed=None,
            parameters={"language_type": "Chinese"},
        )
    )
    assert audio == dummy_audio


def test_openai_tts_uses_backend_configured_speed(monkeypatch):
    responses = [DummyResponse(200, content=b"fake-mp3")]
    captured_payloads = []

    class DummyTtsConfig:
        api_key = "test-key"
        model_name = "tts-1"
        api_endpoint = "https://api.openai.com/v1/audio/speech"
        parameters = {
            "provider": "openai",
            "voice": "alloy",
            "speed": 1.35,
            "response_format": "mp3",
        }

    async def _fake_get_tts_config(_db):
        return DummyTtsConfig()

    def client_factory(*args, **kwargs):
        return DummyClient(responses)

    original_post = DummyClient.post

    async def _capturing_post(self, url, json=None, headers=None, files=None, data=None):
        captured_payloads.append(json)
        return await original_post(self, url, json=json, headers=headers, files=files, data=data)

    import httpx

    monkeypatch.setattr(voice_processor, "_get_tts_config", _fake_get_tts_config)
    monkeypatch.setattr(DummyClient, "post", _capturing_post)
    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    audio = asyncio.run(
        voice_processor.synthesize_speech(
            text="测试后台配置语速",
            voice_id="alloy",
            speed=None,
            db=object(),
        )
    )

    assert audio == b"fake-mp3"
    assert captured_payloads[0]["speed"] == 1.35


def test_dashscope_asr_polls_and_extracts_text(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    responses = [
        DummyResponse(200, json_data={"output": {"task_id": "t1"}}),
        DummyResponse(
            200,
            json_data={
                "output": {
                    "task_status": "SUCCEEDED",
                    "results": [{"transcription_url": "https://example.com/t.json"}],
                }
            },
        ),
        DummyResponse(200, json_data={"transcripts": [{"text": "hello world"}]}),
    ]

    def client_factory(*args, **kwargs):
        return DummyClient(responses)

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    result = asyncio.run(
        voice_processor._dashscope_transcribe_filetrans(
            audio_data=b"fake-audio",
            audio_format="mp3",
            language="zh",
            api_key="test-key",
            api_endpoint="https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription",
            model_name="qwen3-asr-flash-filetrans",
            parameters={"file_url_prefix": "http://example.com/uploads/asr", "task_base_url": "https://dashscope.aliyuncs.com/api/v1"},
        )
    )
    assert result["text"] == "hello world"
