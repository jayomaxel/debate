import asyncio
from unittest.mock import AsyncMock, Mock

from utils.websocket_manager import WebSocketManager


def _socket():
    websocket = Mock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.client_state = Mock()
    websocket.client_state.name = "CONNECTED"
    return websocket


def test_same_user_in_two_rooms_receives_only_current_room_broadcasts():
    async def scenario():
        manager = WebSocketManager()
        room_a_socket = _socket()
        room_b_socket = _socket()

        await manager.connect(room_a_socket, "student-4", "room-a")
        await manager.connect(room_b_socket, "student-4", "room-b")

        await manager.broadcast_to_room(
            "room-a",
            {"type": "state_update", "data": {"current_phase": "free_debate"}},
        )

        room_a_socket.send_json.assert_awaited_once()
        room_b_socket.send_json.assert_not_awaited()

        room_a_socket.send_json.reset_mock()
        await manager.broadcast_to_room(
            "room-b",
            {"type": "state_update", "data": {"current_phase": "questioning"}},
        )

        room_a_socket.send_json.assert_not_awaited()
        room_b_socket.send_json.assert_awaited_once()

    asyncio.run(scenario())


def test_disconnecting_one_room_keeps_same_users_other_room_connected():
    async def scenario():
        manager = WebSocketManager()
        room_a_socket = _socket()
        room_b_socket = _socket()

        await manager.connect(room_a_socket, "student-4", "room-a")
        await manager.connect(room_b_socket, "student-4", "room-b")
        disconnected_room = await manager.disconnect("student-4", room_a_socket)

        assert disconnected_room == "room-a"
        assert not manager.is_user_connected("student-4", "room-a")
        assert manager.is_user_connected("student-4", "room-b")
        assert "student-4" not in manager.get_room_connections("room-a")
        assert "student-4" in manager.get_room_connections("room-b")

        await manager.broadcast_to_room(
            "room-b",
            {"type": "state_update", "data": {"current_phase": "questioning"}},
        )
        room_b_socket.send_json.assert_awaited_once()

    asyncio.run(scenario())

