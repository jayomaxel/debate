import asyncio


def test_e2e_probe_requires_transcript_and_non_fallback_ai(monkeypatch):
    from config import settings
    from services import e2e_health_probe_service as probe_module

    monkeypatch.setattr(settings, "E2E_HEALTH_PROBE_ENABLED", True)
    monkeypatch.setattr(settings, "E2E_HEALTH_PROBE_AUDIO_PATH", None)
    monkeypatch.setattr(settings, "E2E_HEALTH_PROBE_AUDIO_B64", None)
    monkeypatch.setattr(settings, "E2E_HEALTH_PROBE_EXPECTED_TEXT", "")
    monkeypatch.setattr(settings, "IS_PRODUCTION", False)

    class FakeVoiceProcessor:
        async def transcribe_audio(self, audio_data, **kwargs):
            assert audio_data
            assert kwargs["language"] == "zh"
            return {"text": "健康探针输入", "duration": 1}

    class FakeAgent:
        def __init__(self, position, db):
            assert position == 1
            assert db == "db"

        async def generate_free_debate_speech(self, **kwargs):
            assert kwargs["context"][0]["content"] == "健康探针输入"
            return "已收到健康探针输入。"

    monkeypatch.setattr(
        "utils.voice_processor.voice_processor", FakeVoiceProcessor()
    )
    monkeypatch.setattr("agents.debater_agent.AIDebaterAgent", FakeAgent)

    result = asyncio.run(probe_module.e2e_health_probe_service.run("db"))

    assert result["status"] == "passed"
    assert result["release_gate"]["eligible"] is True
    assert result["steps"]["asr"]["status"] == "passed"
    assert result["steps"]["ai"]["fallback"] is False
    assert "健康探针输入" not in result


def test_e2e_probe_blocks_fallback_ai(monkeypatch):
    from config import settings
    from services import e2e_health_probe_service as probe_module

    monkeypatch.setattr(settings, "E2E_HEALTH_PROBE_ENABLED", True)
    monkeypatch.setattr(settings, "E2E_HEALTH_PROBE_AUDIO_PATH", None)
    monkeypatch.setattr(settings, "E2E_HEALTH_PROBE_AUDIO_B64", None)
    monkeypatch.setattr(settings, "E2E_HEALTH_PROBE_EXPECTED_TEXT", None)
    monkeypatch.setattr(settings, "IS_PRODUCTION", False)

    class FakeVoiceProcessor:
        async def transcribe_audio(self, *_args, **_kwargs):
            return {"text": "健康探针输入"}

    class FakeAgent:
        def __init__(self, *_args, **_kwargs):
            pass

        async def generate_free_debate_speech(self, **_kwargs):
            return "[AI辩手1暂时无法回应]"

    monkeypatch.setattr(
        "utils.voice_processor.voice_processor", FakeVoiceProcessor()
    )
    monkeypatch.setattr("agents.debater_agent.AIDebaterAgent", FakeAgent)

    result = asyncio.run(probe_module.e2e_health_probe_service.run("db"))

    assert result["status"] == "failed"
    assert result["release_gate"]["eligible"] is False
    assert result["steps"]["ai"]["fallback"] is True


def test_e2e_probe_disabled_is_not_release_eligible(monkeypatch):
    from config import settings
    from services import e2e_health_probe_service as probe_module

    monkeypatch.setattr(settings, "E2E_HEALTH_PROBE_ENABLED", False)

    result = asyncio.run(probe_module.e2e_health_probe_service.run("db"))

    assert result["status"] == "disabled"
    assert result["release_gate"]["eligible"] is False

