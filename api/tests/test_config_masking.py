import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from database import get_db
from routers import admin
from services.auth_service import AuthService
from services.config_service import ConfigService


@pytest.fixture
def admin_client(db_session):
    app = FastAPI()
    app.include_router(admin.router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _admin_headers(db_session):
    payload = AuthService.login(
        db=db_session,
        account="admin",
        password="Admin123!",
        user_type="administrator",
    )
    return {"Authorization": f"Bearer {payload['access_token']}"}


async def _seed_model_secret(service: ConfigService, secret: str):
    await service.update_model_config(
        model_name="gpt-4o-mini",
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key=secret,
        temperature=0.7,
        max_tokens=2048,
        parameters={},
    )


async def _seed_asr_secret(service: ConfigService, secret: str):
    await service.update_asr_config(
        model_name="qwen-audio-asr",
        api_endpoint="https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        api_key=secret,
        parameters={"provider": "dashscope"},
    )


async def _seed_tts_secret(service: ConfigService, secret: str):
    await service.update_tts_config(
        model_name="qwen-tts",
        api_endpoint="https://dashscope.aliyuncs.com/api/v1/services/aigc/text-to-speech/generation",
        api_key=secret,
        parameters={"voice": "Cherry"},
    )


async def _seed_vector_secret(service: ConfigService, secret: str):
    await service.update_vector_config(
        model_name="text-embedding-3-small",
        api_endpoint="https://api.openai.com/v1/embeddings",
        api_key=secret,
        embedding_dimension=1536,
        parameters={},
    )


async def _seed_coze_secret(service: ConfigService, secret: str):
    await service.update_coze_config(
        debater_1_bot_id="bot-1",
        debater_2_bot_id="bot-2",
        debater_3_bot_id="bot-3",
        debater_4_bot_id="bot-4",
        judge_bot_id="judge-bot",
        mentor_bot_id="mentor-bot",
        api_token=secret,
        parameters={"timeout": 30},
    )


async def _seed_email_secret(service: ConfigService, secret: str):
    await service.update_email_config(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="mailer@example.com",
        smtp_password=secret,
        from_email="mailer@example.com",
        auto_send_enabled=True,
    )


def test_masked_config_contract_examples_hide_raw_secret():
    examples = ConfigService.build_masked_config_contract_examples()

    assert set(examples.keys()) == {"model", "coze", "asr", "tts", "vector", "email"}
    assert examples["model"]["configured"] is True
    assert "****" in examples["model"]["masked"]
    assert "openai" not in examples["model"]["masked"]


def test_masked_config_contract_mock_endpoint_returns_all_examples():
    app = FastAPI()
    app.include_router(admin.router)
    client = TestClient(app)
    response = client.get("/api/admin/config/contracts/masked/mock")

    assert response.status_code == 200
    payload = response.json()
    assert "model" in payload
    assert payload["coze"]["configured"] is True
    assert "****" in payload["email"]["masked"]


@pytest.mark.parametrize(
    ("endpoint", "secret_field", "secret_value", "seed_fn"),
    [
        (
            "/api/admin/config/models",
            "api_key",
            "sk-live-model-secret-1234",
            _seed_model_secret,
        ),
        (
            "/api/admin/config/asr",
            "api_key",
            "asr-live-secret-1234",
            _seed_asr_secret,
        ),
        (
            "/api/admin/config/tts",
            "api_key",
            "tts-live-secret-1234",
            _seed_tts_secret,
        ),
        (
            "/api/admin/config/vector",
            "api_key",
            "vec-live-secret-1234",
            _seed_vector_secret,
        ),
        (
            "/api/admin/config/coze",
            "api_token",
            "pat-live-secret-1234",
            _seed_coze_secret,
        ),
        (
            "/api/admin/config/email",
            "smtp_password",
            "smtp-live-secret-1234",
            _seed_email_secret,
        ),
    ],
)
def test_real_config_endpoints_do_not_return_plain_secret(
    admin_client,
    db_session,
    endpoint,
    secret_field,
    secret_value,
    seed_fn,
):
    asyncio.run(seed_fn(ConfigService(db_session), secret_value))

    response = admin_client.get(endpoint, headers=_admin_headers(db_session))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert secret_value not in str(payload)
    assert payload["secret"]["configured"] is True
    assert payload["secret"]["masked"]
    if secret_field == "smtp_password":
        assert payload["smtp_password_masked"] == payload["secret"]["masked"]
        assert payload["smtp_password_configured"] is True
    else:
        assert payload[secret_field] == payload["secret"]["masked"]


def test_masked_model_api_key_roundtrip_keeps_existing_secret(admin_client, db_session):
    headers = _admin_headers(db_session)
    service = ConfigService(db_session)

    asyncio.run(
        service.update_model_config(
            model_name="gpt-4o-mini",
            api_endpoint="https://api.openai.com/v1/chat/completions",
            api_key="sk-roundtrip-secret-9999",
            temperature=0.6,
            max_tokens=1024,
            parameters={},
        )
    )
    get_response = admin_client.get("/api/admin/config/models", headers=headers)
    assert get_response.status_code == 200
    masked_api_key = get_response.json()["data"]["api_key"]
    assert masked_api_key != "sk-roundtrip-secret-9999"

    asyncio.run(
        service.update_model_config(
            temperature=0.9,
            api_key=masked_api_key,
        )
    )

    stored_config = asyncio.run(service.get_model_config())
    assert stored_config.api_key == "sk-roundtrip-secret-9999"
    assert stored_config.temperature == 0.9
