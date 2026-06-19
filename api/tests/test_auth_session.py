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
from routers import auth
from services.auth_service import AuthService


@pytest.fixture
def auth_client(db_session):
    app = FastAPI()
    app.include_router(auth.router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_auth_session_contract_preview_has_frozen_shape():
    payload = AuthService.build_auth_session_contract_preview("administrator")

    assert set(payload.keys()) == {
        "access_token",
        "access_token_expires_in",
        "session_id",
        "user",
        "refresh_strategy",
        "requires_reauth",
    }
    assert payload["user"]["role"] == "admin"
    assert payload["refresh_strategy"] == "server_session"
    assert payload["requires_reauth"] is False


def test_auth_session_contract_mock_endpoint_returns_admin_role(auth_client):
    response = auth_client.get(
        "/api/auth/contracts/session/mock",
        params={"user_type": "administrator"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["role"] == "admin"
    assert payload["refresh_strategy"] == "server_session"


def test_login_openapi_schema_exposes_frozen_and_compat_fields(auth_client):
    response = auth_client.get("/openapi.json")

    assert response.status_code == 200
    openapi = response.json()
    login_response = openapi["paths"]["/api/auth/login"]["post"]["responses"]["200"]
    schema_ref = login_response["content"]["application/json"]["schema"]["$ref"]
    schema_name = schema_ref.split("/")[-1]
    login_schema = openapi["components"]["schemas"][schema_name]
    data_ref = login_schema["properties"]["data"]["$ref"]
    data_schema_name = data_ref.split("/")[-1]
    data_schema = openapi["components"]["schemas"][data_schema_name]

    assert "session_id" in data_schema["properties"]
    assert "access_token_expires_in" in data_schema["properties"]
    assert "refresh_strategy" in data_schema["properties"]
    assert "refresh_token" in data_schema["properties"]
    assert "expires_in" in data_schema["properties"]


@pytest.mark.parametrize(
    ("account", "password", "user_type", "bootstrap"),
    [
        (
            "teacher_contract",
            "Teacher123!",
            "teacher",
            lambda db: AuthService.register_teacher(
                db=db,
                account="teacher_contract",
                email="teacher_contract@test.com",
                phone="13800138011",
                password="Teacher123!",
                name="Teacher Contract",
            ),
        ),
        (
            "student_contract",
            "Student123!",
            "student",
            lambda db: AuthService.register_student(
                db=db,
                account="student_contract",
                password="Student123!",
                name="Student Contract",
                email="student_contract@test.com",
            ),
        ),
        (
            "admin",
            "Admin123!",
            "administrator",
            lambda db: AuthService.login(
                db=db,
                account="admin",
                password="Admin123!",
                user_type="administrator",
            ),
        ),
    ],
)
def test_real_login_returns_session_contract_fields(
    auth_client, db_session, account, password, user_type, bootstrap
):
    bootstrap(db_session)

    response = auth_client.post(
        "/api/auth/login",
        json={
            "account": account,
            "password": password,
            "user_type": user_type,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == payload["access_token_expires_in"]
    assert payload["session_id"]
    assert payload["refresh_strategy"] == "server_session"
    assert payload["requires_reauth"] is False
    assert payload["user"]["id"]
    assert payload["user"]["username"] == account
    assert payload["user"]["role"] in {"teacher", "student", "admin"}
    assert payload["user"]["account"] == account
    assert payload["user"]["user_type"] == user_type


def test_real_refresh_keeps_session_contract_fields(auth_client, db_session):
    AuthService.register_teacher(
        db=db_session,
        account="teacher_refresh_contract",
        email="teacher_refresh_contract@test.com",
        phone="13800138012",
        password="Teacher123!",
        name="Refresh Contract Teacher",
    )

    login_response = auth_client.post(
        "/api/auth/login",
        json={
            "account": "teacher_refresh_contract",
            "password": "Teacher123!",
            "user_type": "teacher",
        },
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()["data"]

    refresh_response = auth_client.post(
        "/api/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()["data"]
    assert refresh_payload["access_token"] != login_payload["access_token"]
    assert refresh_payload["session_id"] == login_payload["session_id"]
    assert (
        refresh_payload["access_token_expires_in"]
        == login_payload["access_token_expires_in"]
    )
    assert refresh_payload["refresh_strategy"] == "server_session"
    assert refresh_payload["user"]["username"] == "teacher_refresh_contract"
    assert refresh_payload["user"]["role"] == "teacher"
