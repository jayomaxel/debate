import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

from database import get_db
from models.config import CozeConfig, ModelConfig
from models.user import User
from routers import admin
from testing_db import create_test_engine, create_test_schema, drop_test_schema
from utils.security import create_token


BASE_URL = "http://test"
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin_secret_masking.db"
engine = create_test_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
app = FastAPI()
app.include_router(admin.router)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    create_test_schema(engine)
    yield
    drop_test_schema(engine)


def _seed_admin() -> dict:
    db = TestingSessionLocal()
    try:
        admin_user = User(
            id=uuid.uuid4(),
            account=f"admin_secret_{uuid.uuid4().hex[:8]}",
            password_hash="test-hash",
            user_type="administrator",
            name="Admin Secret",
            email=f"admin_secret_{uuid.uuid4().hex[:8]}@test.com",
        )
        db.add(admin_user)
        db.commit()
        token = create_token({"sub": str(admin_user.id), "user_type": "administrator"})
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


@pytest.mark.asyncio
async def test_model_config_response_masks_api_key_and_preserves_placeholder_update():
    headers = _seed_admin()
    db = TestingSessionLocal()
    try:
        config = ModelConfig(
            model_name="gpt-test",
            api_endpoint="https://example.test/v1/chat/completions",
            api_key="sk-real-secret-1234",
            temperature=0.7,
            max_tokens=2000,
            parameters={},
        )
        db.add(config)
        db.commit()
    finally:
        db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get("/api/admin/config/models", headers=headers)
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["api_key"] == "sk-r****1234"
        assert payload["api_key_masked"] == "sk-r****1234"
        assert payload["api_key_configured"] is True

        response = await client.post(
            "/api/admin/config/models",
            headers=headers,
            json={"model_name": "gpt-updated", "api_key": payload["api_key"]},
        )
        assert response.status_code == 200

    db = TestingSessionLocal()
    try:
        saved = db.query(ModelConfig).one()
        assert saved.model_name == "gpt-updated"
        assert saved.api_key == "sk-real-secret-1234"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_coze_config_response_masks_api_token_and_preserves_placeholder_update():
    headers = _seed_admin()
    db = TestingSessionLocal()
    try:
        config = CozeConfig(
            debater_1_bot_id="bot-1",
            debater_2_bot_id="bot-2",
            debater_3_bot_id="bot-3",
            debater_4_bot_id="bot-4",
            judge_bot_id="bot-judge",
            mentor_bot_id="bot-mentor",
            api_token="pat-real-secret-5678",
            parameters={},
        )
        db.add(config)
        db.commit()
    finally:
        db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.get("/api/admin/config/coze", headers=headers)
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["api_token"] == "pat-****5678"
        assert payload["api_token_masked"] == "pat-****5678"
        assert payload["api_token_configured"] is True

        response = await client.post(
            "/api/admin/config/coze",
            headers=headers,
            json={"mentor_bot_id": "bot-mentor-updated", "api_token": payload["api_token"]},
        )
        assert response.status_code == 200

    db = TestingSessionLocal()
    try:
        saved = db.query(CozeConfig).one()
        assert saved.mentor_bot_id == "bot-mentor-updated"
        assert saved.api_token == "pat-real-secret-5678"
    finally:
        db.close()
