"""Manage debate WebSocket connections and room-scoped broadcasts."""

from datetime import datetime
from typing import Dict, List, Optional, Set

from fastapi import WebSocket

from logging_config import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """Track every browser connection without mixing messages across rooms."""

    def __init__(self):
        # A user can have multiple tabs and can be connected to multiple rooms.
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.room_members: Dict[str, Set[str]] = {}
        # Legacy single-room lookup kept for compatibility with existing callers.
        self.user_rooms: Dict[str, str] = {}
        # The authoritative room binding is per websocket connection.
        self.connection_rooms: Dict[int, str] = {}

    def _connections_in_room(self, user_id: str, room_id: str) -> List[WebSocket]:
        """Return only this user's websocket connections belonging to room_id."""
        connections = self.active_connections.get(user_id) or []
        scoped = [
            ws
            for ws in connections
            if self.connection_rooms.get(id(ws)) == room_id
        ]
        if scoped:
            return scoped

        # Compatibility for tests or connections created before room scoping was
        # introduced. An untracked connection is safe only when the legacy room
        # marker explicitly points to the requested room.
        if self.user_rooms.get(user_id) == room_id:
            return [ws for ws in connections if id(ws) not in self.connection_rooms]
        return []

    async def connect(self, websocket: WebSocket, user_id: str, room_id: str) -> None:
        """Accept and register one browser connection for a debate room."""
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)
        self.connection_rooms[id(websocket)] = room_id
        self.room_members.setdefault(room_id, set()).add(user_id)
        self.user_rooms[user_id] = room_id
        logger.info(f"User {user_id} connected to room {room_id}")

    async def disconnect(
        self, user_id: str, websocket: Optional[WebSocket] = None
    ) -> Optional[str]:
        """Disconnect one tab or all tabs without corrupting other rooms."""
        connections = self.active_connections.get(user_id) or []
        target_rooms: Set[str] = set()

        if websocket is not None:
            room_id = self.connection_rooms.pop(id(websocket), None)
            if room_id is None:
                room_id = self.user_rooms.get(user_id)
            if room_id:
                target_rooms.add(room_id)
            remaining = [ws for ws in connections if ws is not websocket]
        else:
            for ws in connections:
                room_id = self.connection_rooms.pop(id(ws), None)
                if room_id:
                    target_rooms.add(room_id)
            legacy_room = self.user_rooms.get(user_id)
            if legacy_room:
                target_rooms.add(legacy_room)
            remaining = []

        if remaining:
            self.active_connections[user_id] = remaining
        else:
            self.active_connections.pop(user_id, None)

        remaining_rooms = {
            self.connection_rooms[id(ws)]
            for ws in remaining
            if id(ws) in self.connection_rooms
        }
        if remaining_rooms:
            self.user_rooms[user_id] = next(iter(remaining_rooms))
        elif not remaining:
            self.user_rooms.pop(user_id, None)

        disconnected_rooms: List[str] = []
        for room_id in target_rooms:
            if self._connections_in_room(user_id, room_id):
                continue

            disconnected_rooms.append(room_id)
            if room_id in self.room_members:
                self.room_members[room_id].discard(user_id)

            await self.broadcast_to_room(
                room_id,
                {
                    "type": "user_left",
                    "data": {
                        "user_id": user_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                },
            )

            if room_id in self.room_members and not self.room_members[room_id]:
                del self.room_members[room_id]
            logger.info(f"User {user_id} disconnected from room {room_id}")

        return disconnected_rooms[0] if disconnected_rooms else None

    async def broadcast_to_room(
        self, room_id: str, message: dict, exclude_user: Optional[str] = None
    ) -> None:
        """Send a message only to websocket connections bound to room_id."""
        if room_id not in self.room_members:
            return

        stale_members: List[str] = []
        broken_connections: List[tuple[str, WebSocket]] = []
        for user_id in list(self.room_members[room_id]):
            if exclude_user and user_id == exclude_user:
                continue

            connections = self._connections_in_room(user_id, room_id)
            if not connections:
                stale_members.append(user_id)
                continue

            for ws in connections:
                try:
                    if ws.client_state.name != "CONNECTED":
                        broken_connections.append((user_id, ws))
                        continue
                    await ws.send_json(message)
                except Exception as exc:
                    logger.debug(f"Failed to send message to user {user_id}: {exc}")
                    broken_connections.append((user_id, ws))

        for user_id, ws in broken_connections:
            await self.disconnect(user_id, ws)

        # A stale member can exist after an abrupt process/browser failure. Remove
        # it from this room only; connections in the user's other rooms stay alive.
        for user_id in stale_members:
            if self._connections_in_room(user_id, room_id):
                continue
            self.room_members.get(room_id, set()).discard(user_id)

        if room_id in self.room_members and not self.room_members[room_id]:
            del self.room_members[room_id]

    async def send_to_user(
        self, user_id: str, message: dict, room_id: Optional[str] = None
    ) -> bool:
        """Send to a user's tabs, optionally restricted to one debate room."""
        connections = (
            self._connections_in_room(user_id, room_id)
            if room_id is not None
            else (self.active_connections.get(user_id) or [])
        )
        if not connections:
            return False

        broken: List[WebSocket] = []
        sent = False
        for ws in connections:
            try:
                if ws.client_state.name != "CONNECTED":
                    broken.append(ws)
                    continue
                await ws.send_json(message)
                sent = True
            except Exception as exc:
                logger.debug(f"Failed to send message to user {user_id}: {exc}")
                broken.append(ws)

        for ws in broken:
            await self.disconnect(user_id, ws)
        return sent

    def get_room_connections(self, room_id: str) -> Set[str]:
        """Return the connected user ids recorded for a room."""
        return self.room_members.get(room_id, set()).copy()

    def get_user_room(self, user_id: str) -> Optional[str]:
        """Return the legacy most-recent room for a user."""
        return self.user_rooms.get(user_id)

    def is_user_connected(
        self, user_id: str, room_id: Optional[str] = None
    ) -> bool:
        """Check whether a user has any connection, optionally in one room."""
        if room_id is None:
            return bool(self.active_connections.get(user_id))
        return bool(self._connections_in_room(user_id, room_id))


websocket_manager = WebSocketManager()
