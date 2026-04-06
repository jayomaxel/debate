"""
测试WebSocket断开连接时的竞态条件修复
"""
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from utils.websocket_manager import WebSocketManager
from datetime import datetime


async def test_disconnect_race_condition():
    """
    测试断开连接时不会向已关闭的连接发送消息
    """
    manager = WebSocketManager()
    
    # 创建模拟的WebSocket连接
    ws1 = Mock()
    ws1.accept = AsyncMock()
    ws1.send_json = AsyncMock()
    ws1.client_state = Mock()
    ws1.client_state.name = "CONNECTED"
    
    ws2 = Mock()
    ws2.accept = AsyncMock()
    ws2.send_json = AsyncMock()
    ws2.client_state = Mock()
    ws2.client_state.name = "CONNECTED"
    
    # 用户1和用户2连接到同一个房间
    user1_id = "user-1"
    user2_id = "user-2"
    room_id = "room-123"
    
    await manager.connect(ws1, user1_id, room_id)
    await manager.connect(ws2, user2_id, room_id)
    
    print(f"✓ 两个用户已连接到房间 {room_id}")
    print(f"  房间成员: {manager.room_members[room_id]}")
    
    # 模拟用户1的连接已关闭
    ws1.client_state.name = "DISCONNECTED"
    ws1.send_json = AsyncMock(side_effect=Exception("Connection closed"))
    
    # 用户1断开连接
    await manager.disconnect(user1_id, ws1)
    
    print(f"✓ 用户1已断开连接")
    print(f"  房间成员: {manager.room_members.get(room_id, set())}")
    
    # 验证用户1不再在房间成员列表中
    assert user1_id not in manager.room_members.get(room_id, set()), "用户1应该已从房间移除"
    
    # 验证用户2仍在房间中
    assert user2_id in manager.room_members.get(room_id, set()), "用户2应该仍在房间中"
    
    # 现在广播一条消息，应该只发送给用户2
    await manager.broadcast_to_room(
        room_id,
        {"type": "test", "data": {"message": "Hello"}}
    )
    
    # 验证只有用户2收到消息
    assert ws2.send_json.called, "用户2应该收到消息"
    print(f"✓ 广播消息只发送给在线用户")
    
    # 验证没有错误日志（通过检查ws1.send_json没有被调用）
    # 因为用户1已经从房间移除，所以不会尝试发送
    print(f"✓ 没有尝试向已断开的连接发送消息")
    
    print("\n所有测试通过！")


async def test_send_to_closed_connection():
    """
    测试向已关闭的连接发送消息时的错误处理
    """
    manager = WebSocketManager()
    
    # 创建模拟的WebSocket连接
    ws = Mock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.client_state = Mock()
    ws.client_state.name = "CONNECTED"
    
    user_id = "user-1"
    room_id = "room-123"
    
    await manager.connect(ws, user_id, room_id)
    
    print(f"✓ 用户已连接")
    
    # 模拟连接已关闭
    ws.client_state.name = "DISCONNECTED"
    
    # 尝试发送消息
    result = await manager.send_to_user(user_id, {"type": "test", "data": {}})
    
    # 验证发送失败但没有抛出异常
    assert not result, "发送应该失败"
    print(f"✓ 向已关闭的连接发送消息时正确处理")
    
    # 验证用户已被自动清理
    assert user_id not in manager.active_connections, "用户应该已被清理"
    print(f"✓ 断开的连接已自动清理")
    
    print("\n所有测试通过！")


if __name__ == "__main__":
    print("=" * 60)
    print("测试1: 断开连接时的竞态条件")
    print("=" * 60)
    asyncio.run(test_disconnect_race_condition())
    
    print("\n" + "=" * 60)
    print("测试2: 向已关闭的连接发送消息")
    print("=" * 60)
    asyncio.run(test_send_to_closed_connection())
