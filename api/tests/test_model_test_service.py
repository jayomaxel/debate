import asyncio
from types import SimpleNamespace

import httpx

from services.model_test_service import ModelTestService


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


class DummyClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.response


def test_model_test_service_success(monkeypatch):
    """测试模型测试服务能读取项目配置并完成一次成功调用。"""

    async def _fake_get_model_config(self):
        return SimpleNamespace(
            api_key="sk-test-key",
            api_endpoint="https://api.openai.com/v1",
            model_name="gpt-4o-mini",
            temperature=0.6,
            max_tokens=512,
            parameters={},
        )

    dummy_response = DummyResponse(
        status_code=200,
        json_data={
            "choices": [
                {"message": {"content": "模型连接测试成功"}}
            ]
        },
    )

    def _client_factory(*args, **kwargs):
        return DummyClient(dummy_response)

    monkeypatch.setattr(
        "services.config_service.ConfigService.get_model_config",
        _fake_get_model_config,
    )
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)

    service = ModelTestService(db=object())
    success, error_msg, result = asyncio.run(
        service.test_model_connection(prompt="请只回复：模型连接测试成功")
    )

    assert success is True
    assert error_msg is None
    assert result["model_name"] == "gpt-4o-mini"
    assert result["api_endpoint"].endswith("/chat/completions")
    assert result["reply"] == "模型连接测试成功"
    assert result["max_tokens"] == 128


def test_model_test_service_timeout(monkeypatch):
    """测试模型测试服务能明确返回读取超时错误。"""

    async def _fake_get_model_config(self):
        return SimpleNamespace(
            api_key="sk-test-key",
            api_endpoint="https://api.openai.com/v1/chat/completions",
            model_name="gpt-4o-mini",
            temperature=0.6,
            max_tokens=128,
            parameters={},
        )

    class TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            raise httpx.ReadTimeout("timed out")

    def _client_factory(*args, **kwargs):
        return TimeoutClient()

    monkeypatch.setattr(
        "services.config_service.ConfigService.get_model_config",
        _fake_get_model_config,
    )
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)

    service = ModelTestService(db=object())
    success, error_msg, result = asyncio.run(
        service.test_model_connection(timeout_seconds=12.0)
    )

    assert success is False
    assert result is None
    assert "12.0 秒" in error_msg
