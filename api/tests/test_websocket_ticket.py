import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from database import get_db
from routers import auth, websocket as websocket_router
from services.auth_service import AuthService
from utils.security import persist_ws_ticket


@pytest.fixture
def ws_client(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(websocket_router.router)

    def override_get_db():
        yield db_session

    async def fake_connect(websocket, user_id, room_id):
        await websocket.accept()

    async def fake_disconnect(user_id, websocket):
        return None

    async def fake_create_room(room_id, debate_id, db):
        return True

    async def fake_join_room(room_id, user_id, db):
        return True

    async def fake_leave_room(room_id, user_id, db):
        return True

    async def fake_cleanup_room(room_id):
        return None

    monkeypatch.setattr(
        websocket_router.websocket_manager,
        "connect",
        fake_connect,
    )
    monkeypatch.setattr(
        websocket_router.websocket_manager,
        "disconnect",
        fake_disconnect,
    )
    monkeypatch.setattr(
        websocket_router.websocket_manager,
        "is_user_connected",
        lambda user_id: False,
    )
    monkeypatch.setattr(
        websocket_router.room_manager,
        "get_room_state",
        lambda room_id: None,
    )
    monkeypatch.setattr(
        websocket_router.room_manager,
        "create_room",
        fake_create_room,
    )
    monkeypatch.setattr(
        websocket_router.room_manager,
        "join_room",
        fake_join_room,
    )
    monkeypatch.setattr(
        websocket_router.room_manager,
        "leave_room",
        fake_leave_room,
    )
    monkeypatch.setattr(
        websocket_router.flow_controller,
        "cleanup_room",
        fake_cleanup_room,
    )

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _login_teacher(client: TestClient, db_session, *, account: str) -> dict:
    AuthService.register_teacher(
        db=db_session,
        account=account,
        email=f"{account}@test.com",
        phone="13800138021",
        password="Teacher123!",
        name="Ticket Teacher",
    )

    response = client.post(
        "/api/auth/login",
        json={
            "account": account,
            "password": "Teacher123!",
            "user_type": "teacher",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_ws_ticket_mock_endpoint_uses_ticket_query_only(ws_client):
    room_id = "room_contract_001"
    response = ws_client.get("/api/auth/ws-ticket/mock", params={"room_id": room_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["room_id"] == room_id
    assert payload["ticket"] in payload["connection_url"]
    assert f"/ws/{room_id}?ticket=" in payload["connection_url"]
    assert "token=" not in payload["connection_url"]


def test_real_ws_ticket_endpoint_returns_frozen_shape(ws_client, db_session):
    login_payload = _login_teacher(
        ws_client,
        db_session,
        account="teacher_ws_ticket_real",
    )
    response = ws_client.get(
        "/api/auth/ws-ticket",
        params={"room_id": "room_real_ticket_001"},
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["room_id"] == "room_real_ticket_001"
    assert payload["ticket"]
    assert payload["ticket"] in payload["connection_url"]
    assert payload["connection_url"] == (
        f"/ws/room_real_ticket_001?ticket={payload['ticket']}"
    )
    assert "token=" not in payload["connection_url"]


def test_websocket_connection_rejects_missing_ticket(ws_client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect("/ws/room_without_ticket"):
            pass

    assert exc_info.value.code == 1008


def test_websocket_connection_rejects_access_token_query(ws_client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect("/ws/room_using_token?token=legacy"):
            pass

    assert exc_info.value.code == 1008


def test_websocket_connection_accepts_valid_single_use_ticket(ws_client, db_session):
    login_payload = _login_teacher(
        ws_client,
        db_session,
        account="teacher_ws_ticket_once",
    )
    response = ws_client.get(
        "/api/auth/ws-ticket",
        params={"room_id": "room_ticket_once_001"},
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )
    assert response.status_code == 200
    ticket = response.json()["ticket"]

    with ws_client.websocket_connect(f"/ws/room_ticket_once_001?ticket={ticket}") as websocket:
        websocket.close()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect(f"/ws/room_ticket_once_001?ticket={ticket}"):
            pass

    assert exc_info.value.code == 1008


def test_websocket_connection_rejects_wrong_room_ticket(ws_client, db_session):
    login_payload = _login_teacher(
        ws_client,
        db_session,
        account="teacher_ws_ticket_room",
    )
    response = ws_client.get(
        "/api/auth/ws-ticket",
        params={"room_id": "room_bound_001"},
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )
    assert response.status_code == 200
    ticket = response.json()["ticket"]

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect(f"/ws/room_bound_002?ticket={ticket}"):
            pass

    assert exc_info.value.code == 1008


def test_websocket_connection_rejects_expired_ticket(ws_client, db_session):
    login_payload = _login_teacher(
        ws_client,
        db_session,
        account="teacher_ws_ticket_expired",
    )
    persist_ws_ticket(
        ticket="ws_expired_ticket",
        room_id="room_expired_001",
        user_id=login_payload["user"]["id"],
        user_type="teacher",
        session_id=login_payload["session_id"],
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect("/ws/room_expired_001?ticket=ws_expired_ticket"):
            pass

    assert exc_info.value.code == 1008
