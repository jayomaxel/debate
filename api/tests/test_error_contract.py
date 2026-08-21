import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from utils.error_contract import install_error_contract, public_exception_detail


class DemoPayload(BaseModel):
    count: int


def _build_client(*, raise_server_exceptions: bool = True) -> TestClient:
    app = FastAPI()
    install_error_contract(app)

    @app.get("/bad-request")
    async def bad_request():
        raise HTTPException(status_code=400, detail="输入参数无效")

    @app.post("/validate")
    async def validate_payload(payload: DemoPayload):
        return payload

    @app.get("/boom")
    async def boom():
        raise RuntimeError("raw database failure")

    @app.get("/safe-server-error")
    async def safe_server_error():
        raise HTTPException(status_code=500, detail="获取对话历史失败")

    @app.get("/raw-server-error")
    async def raw_server_error():
        raise HTTPException(status_code=500, detail="postgres://user:secret@db")

    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_http_exception_uses_unified_error_contract():
    client = _build_client()

    response = client.get("/bad-request", headers={"x-request-id": "req-contract-400"})

    assert response.status_code == 400
    assert response.headers["X-Request-Id"] == "req-contract-400"
    assert response.json() == {
        "code": 400,
        "message": "输入参数无效",
        "request_id": "req-contract-400",
        "detail": "输入参数无效",
    }


def test_validation_error_uses_unified_error_contract():
    client = _build_client()

    response = client.post(
        "/validate",
        headers={"x-request-id": "req-contract-422"},
        json={"count": "many"},
    )

    payload = response.json()
    assert response.status_code == 422
    assert response.headers["X-Request-Id"] == "req-contract-422"
    assert payload["code"] == 422
    assert payload["message"] == "请求参数校验失败"
    assert payload["request_id"] == "req-contract-422"
    assert payload["detail"] == payload["errors"]
    assert payload["errors"][0]["loc"] == ["body", "count"]


def test_unhandled_exception_hides_raw_detail_but_keeps_request_id():
    client = _build_client(raise_server_exceptions=False)

    response = client.get("/boom", headers={"x-request-id": "req-contract-500"})

    assert response.status_code == 500
    assert response.headers["X-Request-Id"] == "req-contract-500"
    assert response.json() == {
        "code": 500,
        "message": "服务器内部错误，请稍后重试",
        "request_id": "req-contract-500",
        "detail": "服务器内部错误，请稍后重试",
    }


def test_safe_http_500_message_stays_user_facing():
    client = _build_client()

    response = client.get(
        "/safe-server-error",
        headers={"x-request-id": "req-contract-safe-500"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "code": 500,
        "message": "获取对话历史失败",
        "request_id": "req-contract-safe-500",
        "detail": "获取对话历史失败",
    }


def test_raw_http_500_message_is_sanitized():
    client = _build_client()

    response = client.get(
        "/raw-server-error",
        headers={"x-request-id": "req-contract-raw-500"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "code": 500,
        "message": "服务器内部错误，请稍后重试",
        "request_id": "req-contract-raw-500",
        "detail": "服务器内部错误，请稍后重试",
    }


def test_router_exception_detail_never_exposes_sensitive_runtime_text():
    assert public_exception_detail(ValueError("邮箱已存在")) == "邮箱已存在"
    assert public_exception_detail(ValueError("assignment_run_id 不存在")) == "assignment_run_id 不存在"
    assert (
        public_exception_detail(ValueError("当前配置为 ai_auto_assign，不允许提交手动辩位结果"))
        == "当前配置为 ai_auto_assign，不允许提交手动辩位结果"
    )
    assert (
        public_exception_detail(RuntimeError("postgres://user:secret@db"))
        == "请求处理失败，请稍后重试"
    )
