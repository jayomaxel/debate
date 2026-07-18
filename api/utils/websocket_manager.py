"""
WebSocket管理器
负责管理WebSocket连接、消息广播、房间订阅
"""

import asyncio
import json
import os
import time
import uuid
from typing import Any, Dict, Set, Optional, List
from fastapi import WebSocket
from datetime import datetime
from logging_config import get_logger
from config import settings
from database import get_redis

logger = get_logger(__name__)


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # 存储活跃连接: {user_id: [WebSocket, ...]}
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # 存储房间成员: {room_id: Set[user_id]}
        self.room_members: Dict[str, Set[str]] = {}
        # 存储用户所在房间: {user_id: room_id}
        self.user_rooms: Dict[str, str] = {}
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

    async def connect(self, websocket: WebSocket, user_id: str, room_id: str) -> None:
        """
        建立WebSocket连接

        Args:
            websocket: WebSocket连接对象
            user_id: 用户ID
            room_id: 房间ID
        """
        await websocket.accept()

        # 存储连接
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

        # 添加到房间
        if room_id not in self.room_members:
            self.room_members[room_id] = set()
        self.room_members[room_id].add(user_id)

        # 记录用户所在房间
        self.user_rooms[user_id] = room_id
        await self._set_presence(room_id, user_id)

        logger.info(f"User {user_id} connected to room {room_id}")

    async def disconnect(
        self, user_id: str, websocket: Optional[WebSocket] = None
    ) -> Optional[str]:
        """
        断开WebSocket连接

        Args:
            user_id: 用户ID
            websocket: 具体断开的 WebSocket（可选）

        Returns:
            断开连接的房间ID，如果用户不在任何房间则返回None
        """
        # 获取用户所在房间（在移除连接前）
        room_id = self.user_rooms.get(user_id)

        # 检查是否还有其他连接
        connections = self.active_connections.get(user_id) or []
        if websocket is not None:
            connections = [ws for ws in connections if ws is not websocket]
        else:
            connections = []

        # 如果还有其他连接，只更新连接列表，不广播离开事件
        if connections:
            self.active_connections[user_id] = connections
            return None

        # 所有连接都断开了，先移除连接记录和房间成员，再广播
        # 移除连接记录
        if user_id in self.active_connections:
            del self.active_connections[user_id]

        # 从房间移除
        if room_id:
            if room_id in self.room_members:
                self.room_members[room_id].discard(user_id)

            # 移除用户房间记录
            if user_id in self.user_rooms:
                del self.user_rooms[user_id]
            await self._delete_presence(room_id, user_id)

            # 现在广播user_left事件（此时用户已不在房间成员列表中）
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

            # 如果房间为空，删除房间
            if room_id in self.room_members and not self.room_members[room_id]:
                del self.room_members[room_id]

            logger.info(f"User {user_id} disconnected from room {room_id}")

        return room_id

    async def broadcast_to_room(
        self, room_id: str, message: dict, exclude_user: Optional[str] = None
    ) -> None:
        """
        向房间内所有成员广播消息

        Args:
            room_id: 房间ID
            message: 消息内容
            exclude_user: 排除的用户ID（可选）
        """
        await self._publish_room_event(room_id, message, exclude_user)
        await self._broadcast_local(room_id, message, exclude_user=exclude_user)

    async def _broadcast_local(
        self, room_id: str, message: dict, exclude_user: Optional[str] = None
    ) -> None:
        if room_id not in self.room_members:
            return

        # 获取房间成员
        members = self.room_members[room_id]

        # 发送消息给所有成员
        disconnected_users: List[str] = []
        for user_id in list(members):
            if exclude_user and user_id == exclude_user:
                continue

            connections = self.active_connections.get(user_id) or []
            if not connections:
                disconnected_users.append(user_id)
                continue
            broken: List[WebSocket] = []
            for ws in connections:
                try:
                    # 检查连接状态
                    if ws.client_state.name != "CONNECTED":
                        broken.append(ws)
                        continue
                    await ws.send_json(message)
                except Exception as e:
                    logger.debug(f"Failed to send message to user {user_id}: {e}")
                    broken.append(ws)
            if broken:
                remaining = [ws for ws in connections if ws not in broken]
                if remaining:
                    self.active_connections[user_id] = remaining
                else:
                    disconnected_users.append(user_id)

        # 清理断开的连接
        for user_id in disconnected_users:
            await self.disconnect(user_id)

    async def send_to_user(self, user_id: str, message: dict) -> bool:
        """
        向指定用户发送消息

        Args:
            user_id: 用户ID
            message: 消息内容

        Returns:
            是否发送成功
        """
        connections = self.active_connections.get(user_id) or []
        if not connections:
            return False

        broken: List[WebSocket] = []
        ok = False
        for ws in connections:
            try:
                # 检查连接状态
                if ws.client_state.name != "CONNECTED":
                    broken.append(ws)
                    continue
                await ws.send_json(message)
                ok = True
            except Exception as e:
                logger.debug(f"Failed to send message to user {user_id}: {e}")
                broken.append(ws)
        if broken:
            remaining = [ws for ws in connections if ws not in broken]
            if remaining:
                self.active_connections[user_id] = remaining
            else:
                await self.disconnect(user_id)
        return ok

    def get_room_connections(self, room_id: str) -> Set[str]:
        """
        获取房间内的所有连接用户ID

        Args:
            room_id: 房间ID

        Returns:
            用户ID集合
        """
        return self.room_members.get(room_id, set()).copy()

    def get_user_room(self, user_id: str) -> Optional[str]:
        """
        获取用户所在的房间ID

        Args:
            user_id: 用户ID

        Returns:
            房间ID，如果用户不在任何房间则返回None
        """
        return self.user_rooms.get(user_id)

    def is_user_connected(self, user_id: str) -> bool:
        """
        检查用户是否已连接

        Args:
            user_id: 用户ID

        Returns:
            是否已连接
        """
        return bool(self.active_connections.get(user_id))


# 创建全局WebSocket管理器实例
websocket_manager = WebSocketManager()
