"""
WebSocket管理器
负责管理WebSocket连接、消息广播、房间订阅
"""

from typing import Dict, Set, Optional, List
from fastapi import WebSocket
from datetime import datetime
from logging_config import get_logger

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
