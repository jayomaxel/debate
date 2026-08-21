"""Manage debate WebSocket connections and room-scoped broadcasts."""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

from logging_config import get_logger
from config import settings
from database import get_redis

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
        self.instance_id = settings.INSTANCE_ID or f"api-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._redis = None
        self._subscriber_task: Optional[asyncio.Task] = None
        self._presence_task: Optional[asyncio.Task] = None
        self._bridge_running = False
        self._bridge_error: Optional[str] = None
        self._seen_events: Dict[str, float] = {}
        self._room_versions: Dict[str, int] = {}
        self._channel = "realtime:room-events"
        self._presence_ttl_seconds = 30

    async def start(self) -> bool:
        if self._bridge_running:
            return True
        try:
            self._redis = get_redis()
            if self._redis is None:
                self._bridge_error = "redis_disabled"
                return False
            await asyncio.to_thread(self._redis.ping)
            self._bridge_running = True
            self._bridge_error = None
            self._subscriber_task = asyncio.create_task(self._subscriber_loop())
            self._presence_task = asyncio.create_task(self._presence_refresh_loop())
            return True
        except Exception as exc:
            self._bridge_running = False
            self._bridge_error = str(exc)
            logger.warning("Realtime Redis bridge unavailable: %s", exc)
            return False

    async def stop(self) -> None:
        self._bridge_running = False
        tasks = [task for task in (self._subscriber_task, self._presence_task) if task]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._subscriber_task = None
        self._presence_task = None

    def bridge_status(self) -> dict[str, Any]:
        mode = "multi_instance" if settings.REALTIME_MULTI_INSTANCE else "single_instance"
        return {
            "mode": mode,
            "instance_id": self.instance_id,
            "redis_bridge": "connected" if self._bridge_running else "disconnected",
            "ready": bool(self._bridge_running or not settings.REALTIME_MULTI_INSTANCE),
            "error": self._bridge_error,
        }

    def get_global_presence_user_ids(self, room_id: str) -> Set[str]:
        if not self._bridge_running or self._redis is None:
            return self.get_room_connections(room_id)
        prefix = f"realtime:presence:{room_id}:"
        users: Set[str] = set()
        try:
            for key in self._redis.scan_iter(match=f"{prefix}*", count=100):
                suffix = str(key)[len(prefix):]
                user_id, separator, _instance_id = suffix.rpartition(":")
                if separator and user_id:
                    users.add(user_id)
        except Exception as exc:
            self._bridge_error = str(exc)
            return self.get_room_connections(room_id)
        return users

    @staticmethod
    def _presence_key(room_id: str, user_id: str, instance_id: str) -> str:
        return f"realtime:presence:{room_id}:{user_id}:{instance_id}"

    async def _set_presence(self, room_id: str, user_id: str) -> None:
        if not self._bridge_running or self._redis is None:
            return
        key = self._presence_key(room_id, user_id, self.instance_id)
        try:
            await asyncio.to_thread(
                self._redis.set,
                key,
                str(int(time.time())),
                ex=self._presence_ttl_seconds,
            )
        except Exception as exc:
            self._bridge_error = str(exc)

    async def _delete_presence(self, room_id: str, user_id: str) -> None:
        if not self._bridge_running or self._redis is None:
            return
        try:
            await asyncio.to_thread(
                self._redis.delete,
                self._presence_key(room_id, user_id, self.instance_id),
            )
        except Exception as exc:
            self._bridge_error = str(exc)

    async def _presence_refresh_loop(self) -> None:
        try:
            while self._bridge_running:
                for user_id, room_id in list(self.user_rooms.items()):
                    await self._set_presence(room_id, user_id)
                await asyncio.sleep(max(1, self._presence_ttl_seconds // 3))
        except asyncio.CancelledError:
            raise

    def _remember_event(self, event_id: str) -> None:
        now = time.monotonic()
        self._seen_events[event_id] = now
        if len(self._seen_events) > 4096:
            cutoff = now - 300
            self._seen_events = {
                key: timestamp
                for key, timestamp in self._seen_events.items()
                if timestamp >= cutoff
            }

    async def _publish_room_event(
        self,
        room_id: str,
        message: dict,
        exclude_user: Optional[str],
    ) -> None:
        if not self._bridge_running or self._redis is None:
            return
        event_id = uuid.uuid4().hex
        self._remember_event(event_id)
        state_version = int(message.get("state_version") or 0)
        envelope = {
            "event_id": event_id,
            "source_instance": self.instance_id,
            "room_id": str(room_id),
            "state_version": state_version,
            "exclude_user": exclude_user,
            "message": message,
        }
        try:
            await asyncio.to_thread(
                self._redis.publish,
                self._channel,
                json.dumps(envelope, ensure_ascii=False, default=str),
            )
        except Exception as exc:
            self._bridge_error = str(exc)
            logger.warning("Failed to publish realtime event: %s", exc)

    async def _subscriber_loop(self) -> None:
        pubsub = None
        try:
            pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
            await asyncio.to_thread(pubsub.subscribe, self._channel)
            while self._bridge_running:
                raw = await asyncio.to_thread(pubsub.get_message, timeout=1.0)
                if not raw or raw.get("type") != "message":
                    await asyncio.sleep(0.01)
                    continue
                try:
                    envelope = json.loads(raw.get("data") or "{}")
                except (TypeError, json.JSONDecodeError):
                    continue
                event_id = str(envelope.get("event_id") or "")
                room_id = str(envelope.get("room_id") or "")
                if not event_id or not room_id or event_id in self._seen_events:
                    continue
                state_version = int(envelope.get("state_version") or 0)
                previous_version = self._room_versions.get(room_id, -1)
                if state_version and state_version < previous_version:
                    self._remember_event(event_id)
                    continue
                self._remember_event(event_id)
                if state_version:
                    self._room_versions[room_id] = max(previous_version, state_version)
                message = envelope.get("message")
                if not isinstance(message, dict):
                    continue
                if message.get("type") == "state_update" and isinstance(message.get("data"), dict):
                    from services.room_manager import room_manager

                    room_manager.apply_remote_state(room_id, message["data"], state_version)
                await self._broadcast_local(
                    room_id,
                    message,
                    exclude_user=envelope.get("exclude_user"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._bridge_running = False
            self._bridge_error = str(exc)
            logger.warning("Realtime subscriber stopped: %s", exc)
        finally:
            if pubsub is not None:
                try:
                    await asyncio.to_thread(pubsub.close)
                except Exception:
                    pass

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
        await self._set_presence(room_id, user_id)
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

            await self._delete_presence(room_id, user_id)
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
        """Publish and send a message only to connections bound to room_id."""
        await self._publish_room_event(room_id, message, exclude_user)
        await self._broadcast_local(room_id, message, exclude_user=exclude_user)

    async def _broadcast_local(
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
