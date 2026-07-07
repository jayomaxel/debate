import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from database import get_db
from routers import admin, auth
from services.audit_service import AuditService
from services.auth_service import AuthService
from testing_db import create_test_engine, create_test_schema, drop_test_schema


@pytest.fixture
def audit_env(tmp_path):
    AuditService.clear_events()
    database_url = f"sqlite:///{tmp_path / 'audit_service.db'}"
    engine = create_test_engine(database_url)
    create_test_schema(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(admin.router)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield {"client": client, "session_factory": session_factory}

    app.dependency_overrides.clear()
    drop_test_schema(engine)
    AuditService.clear_events()


def _admin_headers(session_factory):
    db = session_factory()
    try:
        payload = AuthService.login(
            db=db,
            account="admin",
            password="Admin123!",
            user_type="administrator",
        )
    finally:
        db.close()
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_login_records_success_audit_event(audit_env):
    client = audit_env["client"]
    session_factory = audit_env["session_factory"]

    db = session_factory()
    try:
        AuthService.register_teacher(
            db=db,
            account="teacher_audit_login",
            email="teacher_audit_login@test.com",
            phone="13800138101",
            password="Teacher123!",
            name="Audit Teacher",
        )
    finally:
        db.close()

    response = client.post(
        "/api/auth/login",
        json={
            "account": "teacher_audit_login",
            "password": "Teacher123!",
            "user_type": "teacher",
        },
    )

    assert response.status_code == 200
    events = AuditService.list_events(limit=10, event_type="auth")
    assert events[0]["result"] == "success"
    assert events[0]["metadata"]["action"] == "login"


def test_failed_login_records_denied_audit_event(audit_env):
    client = audit_env["client"]

    response = client.post(
        "/api/auth/login",
        json={
            "account": "missing_teacher",
            "password": "wrong",
            "user_type": "teacher",
        },
    )

    assert response.status_code == 401
    events = AuditService.list_events(limit=10, event_type="auth")
    assert events[0]["result"] == "denied"
    assert events[0]["actor_id"] == "missing_teacher"
    assert events[0]["metadata"]["action"] == "login"


def test_admin_config_update_records_config_audit_event(audit_env):
    client = audit_env["client"]
    session_factory = audit_env["session_factory"]

    response = client.put(
        "/api/admin/config/models",
        json={
            "model_name": "gpt-4o-mini",
            "api_endpoint": "https://api.openai.com/v1/chat/completions",
            "api_key": "sk-config-audit-1234",
            "temperature": 0.7,
            "max_tokens": 1024,
        },
        headers=_admin_headers(session_factory),
    )

    assert response.status_code == 200
    events = AuditService.list_events(limit=10, event_type="config")
    assert events[0]["target_type"] == "model_config"
    assert events[0]["metadata"]["action"] == "update_model_config"


def test_admin_audit_endpoint_returns_recent_events(audit_env):
    client = audit_env["client"]
    session_factory = audit_env["session_factory"]

    AuditService.record_event(
        event_type="admin_action",
        actor_id="admin-user",
        actor_role="admin",
        target_type="system",
        target_id="seed",
        result="success",
        metadata={"action": "seed"},
    )

    response = client.get(
        "/api/admin/audit/events",
        headers=_admin_headers(session_factory),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert isinstance(payload, list)
    assert payload[0]["event_type"] in {"admin_action", "auth", "config", "upload"}


def test_admin_password_change_records_admin_action(audit_env):
    client = audit_env["client"]
    session_factory = audit_env["session_factory"]

    response = client.put(
        "/api/admin/password",
        json={
            "current_password": "Admin123!",
            "new_password": "Admin123!Updated",
        },
        headers=_admin_headers(session_factory),
    )

    assert response.status_code == 200
    events = AuditService.list_events(limit=10, event_type="admin_action")
    assert events[0]["target_type"] == "admin_password"
    assert events[0]["result"] == "success"
