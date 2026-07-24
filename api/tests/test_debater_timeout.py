import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from agents.debater_agent import AIDebaterAgent
from services.flow_controller import DebateFlowController


def test_stream_timeout_does_not_issue_a_second_provider_request(monkeypatch):
    agent = AIDebaterAgent(position=2, db=SimpleNamespace())

    async def timed_out_stream(*_args, **_kwargs):
        if False:
            yield ""
        raise httpx.ReadTimeout("provider timed out")

    ordinary_request = AsyncMock(return_value="unexpected retry")
    monkeypatch.setattr(agent, "_iter_llm_stream_lines", timed_out_stream)
    monkeypatch.setattr(agent, "_call_llm_once", ordinary_request)

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(
            agent._call_llm_stream(
                endpoint="https://example.invalid/chat/completions",
                headers={},
                payload={"model": "test", "messages": [{"content": "hello"}]},
                stream_callback=AsyncMock(),
            )
        )

    ordinary_request.assert_not_awaited()


def test_flow_timeout_is_longer_than_provider_timeout():
    controller = DebateFlowController.__new__(DebateFlowController)
    for turn_plan in (
        {"speech_type": "response", "thinking_timeout_sec": 15},
        {
            "speech_type": "opening",
            "prethinking_mode": "eager",
            "thinking_timeout_sec": 1.5,
        },
    ):
        timeout = controller._resolve_ai_generation_timeout(turn_plan)
        assert timeout >= AIDebaterAgent.LLM_HTTP_TIMEOUT_SECONDS + 5
