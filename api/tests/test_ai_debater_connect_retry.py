import httpx
import pytest

from agents.debater_agent import AIDebaterAgent


@pytest.mark.asyncio
async def test_llm_connect_error_is_retried_then_returns_success(monkeypatch):
    agent = AIDebaterAgent(position=1, db=object())
    agent.LLM_CONNECT_RETRY_BACKOFF_SECONDS = 0
    calls = 0

    async def fake_call_once(*, endpoint, headers, payload):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("temporary TLS handshake failure")
        return "正常立论内容"

    monkeypatch.setattr(agent, "_call_llm_once", fake_call_once)

    result = await agent._call_llm_once_with_connect_retry(
        endpoint="https://example.test/chat/completions",
        headers={"Authorization": "Bearer test"},
        payload={"model": "test-model"},
    )

    assert result == "正常立论内容"
    assert calls == 2


@pytest.mark.asyncio
async def test_llm_connect_error_stops_after_bounded_attempts(monkeypatch):
    agent = AIDebaterAgent(position=1, db=object())
    agent.LLM_CONNECT_RETRY_BACKOFF_SECONDS = 0
    calls = 0

    async def always_fail(*, endpoint, headers, payload):
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("connect timeout")

    monkeypatch.setattr(agent, "_call_llm_once", always_fail)

    with pytest.raises(httpx.ConnectTimeout):
        await agent._call_llm_once_with_connect_retry(
            endpoint="https://example.test/chat/completions",
            headers={},
            payload={},
        )

    assert calls == agent.LLM_CONNECT_RETRY_COUNT + 1


@pytest.mark.asyncio
async def test_llm_business_failure_is_not_retried(monkeypatch):
    agent = AIDebaterAgent(position=1, db=object())
    calls = 0

    async def return_business_fallback(*, endpoint, headers, payload):
        nonlocal calls
        calls += 1
        return "[AI辩手1暂时无法回应]"

    monkeypatch.setattr(agent, "_call_llm_once", return_business_fallback)

    result = await agent._call_llm_once_with_connect_retry(
        endpoint="https://example.test/chat/completions",
        headers={},
        payload={},
    )

    assert result == "[AI辩手1暂时无法回应]"
    assert calls == 1
