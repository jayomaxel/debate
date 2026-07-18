import asyncio
import http.client
import json
import os
from pathlib import Path
import socket
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import websockets

from models.debate import Debate, DebateParticipation
from models.user import User
from services.auth_service import AuthService
from services.room_manager import DebatePhase, DebateRoomManager
from services.runtime_state_store import RuntimeStateStore


pytestmark = [pytest.mark.e2e, pytest.mark.integration]


class _DockerSocketConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str):
        super().__init__("localhost")
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


def _kill_test_container(container_name: str) -> None:
    socket_path = os.environ["RUNTIME_DOCKER_SOCKET"]
    if not Path(socket_path).is_socket():
        pytest.fail("Docker control socket is unavailable in the isolated test controller")
    connection = _DockerSocketConnection(socket_path)
    try:
        connection.request(
            "POST",
            f"/v1.41/containers/{container_name}/kill?signal=SIGKILL",
        )
        response = connection.getresponse()
        response.read()
        assert response.status == 204
    finally:
        connection.close()


async def _receive_type(websocket, expected_type: str, timeout: float = 10.0) -> dict:
    async def receive():
        while True:
            message = json.loads(await websocket.recv())
            if message.get("type") == expected_type:
                return message

    return await asyncio.wait_for(receive(), timeout=timeout)


async def _receive_types(websocket, expected_types: set[str], timeout: float = 10.0) -> dict:
    async def receive():
        messages = {}
        while set(messages) != expected_types:
            message = json.loads(await websocket.recv())
            message_type = message.get("type")
            if message_type in expected_types:
                messages[message_type] = message
        return messages

    return await asyncio.wait_for(receive(), timeout=timeout)


async def _connect_and_read_state(base_url: str, room_id: str, ticket: str):
    websocket = await websockets.connect(f"{base_url}/ws/{room_id}?ticket={ticket}")
    await _receive_type(websocket, "room_joined")
    state_message = await _receive_type(websocket, "state_update")
    return websocket, state_message


@pytest.mark.asyncio
async def test_two_uvicorn_instances_survive_owner_failure_with_shared_state():
    database_url = os.environ["E2E_DATABASE_URL"]
    engine = create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()

    room_id = str(uuid.uuid4())
    first_user = User(
        id=uuid.uuid4(),
        account=f"network-first-{uuid.uuid4().hex[:8]}",
        password_hash="test-only",
        user_type="student",
        name="Network First",
        email=f"{uuid.uuid4().hex}@example.test",
    )
    second_user = User(
        id=uuid.uuid4(),
        account=f"network-second-{uuid.uuid4().hex[:8]}",
        password_hash="test-only",
        user_type="student",
        name="Network Second",
        email=f"{uuid.uuid4().hex}@example.test",
    )
    debate = Debate(
        id=uuid.UUID(room_id),
        topic="Network multi-instance acceptance",
        duration=10,
        invitation_code=uuid.uuid4().hex[:6],
        status="in_progress",
        mode="teacher_assigned",
        visibility="private",
        capacity=4,
    )
    db.add_all(
        [
            first_user,
            second_user,
            debate,
            DebateParticipation(
                id=uuid.uuid4(),
                debate_id=debate.id,
                user_id=first_user.id,
                role="debater_1",
                stance="positive",
                seat_order=1,
            ),
            DebateParticipation(
                id=uuid.uuid4(),
                debate_id=debate.id,
                user_id=second_user.id,
                role="debater_2",
                stance="negative",
                seat_order=2,
            ),
        ]
    )
    db.commit()

    setup_manager = DebateRoomManager()
    setup_state = await setup_manager.create_room(room_id, room_id, db)
    setup_state.current_phase = DebatePhase.FREE_DEBATE
    setup_state.current_segment_id = "free_debate"
    setup_state.current_segment_title = "Free debate"
    setup_state.speaker_mode = "free"
    assert setup_manager._persist_runtime_state(setup_state, db)

    first_ticket = AuthService.issue_ws_ticket(user=first_user, room_id=room_id)["ticket"]
    second_ticket = AuthService.issue_ws_ticket(user=second_user, room_id=room_id)["ticket"]
    first_ws = second_ws = None
    try:
        first_ws, first_state = await _connect_and_read_state(
            os.environ["RUNTIME_API_ONE_WS"], room_id, first_ticket
        )
        second_ws, second_state = await _connect_and_read_state(
            os.environ["RUNTIME_API_TWO_WS"], room_id, second_ticket
        )
        assert first_state["data"]["current_phase"] == DebatePhase.FREE_DEBATE.value
        assert second_state["data"]["current_phase"] == DebatePhase.FREE_DEBATE.value

        await asyncio.gather(
            first_ws.send(
                json.dumps({"type": "grab_mic", "data": {"request_id": "network-first"}})
            ),
            second_ws.send(
                json.dumps({"type": "grab_mic", "data": {"request_id": "network-second"}})
            ),
        )
        first_messages, second_messages = await asyncio.gather(
            _receive_types(first_ws, {"mic_grab_result", "mic_grabbed"}),
            _receive_types(second_ws, {"mic_grab_result", "mic_grabbed"}),
        )
        first_result = first_messages["mic_grab_result"]
        second_result = second_messages["mic_grab_result"]
        allowed = [
            bool(first_result["data"]["allowed"]),
            bool(second_result["data"]["allowed"]),
        ]
        assert allowed.count(True) == 1
        winner_user_id = str(first_user.id if allowed[0] else second_user.id)

        first_event = first_messages["mic_grabbed"]
        second_event = second_messages["mic_grabbed"]
        assert first_event["data"]["user_id"] == winner_user_id
        assert second_event["data"]["user_id"] == winner_user_id

        _kill_test_container(os.environ["RUNTIME_FAILOVER_CONTAINER"])
        await asyncio.sleep(0.5)
        await second_ws.send(json.dumps({"type": "ping", "data": {}}))
        assert (await _receive_type(second_ws, "pong"))["type"] == "pong"

        db.expire_all()
        authoritative = RuntimeStateStore(db).load(room_id)
        assert authoritative.state["mic_owner_user_id"] == winner_user_id
        assert authoritative.version >= 1
    finally:
        for websocket in (first_ws, second_ws):
            if websocket is not None:
                try:
                    await websocket.close()
                except Exception:
                    pass
        db.close()
        engine.dispose()
