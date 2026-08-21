import asyncio
import os

import pytest


class _ConnectedState:
    name = "CONNECTED"


class FakeWebSocket:
    def __init__(self):
        self.client_state = _ConnectedState()
        self.messages = []
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        self.messages.append(message)


@pytest.mark.integration
def test_two_websocket_instances_forward_events_and_presence_via_redis(monkeypatch):
    redis_port = os.getenv("RUNTIME_TEST_REDIS_PORT")
    if not redis_port:
        pytest.skip("set RUNTIME_TEST_REDIS_PORT to an isolated Redis endpoint")

    import redis
    import database
    from utils.websocket_manager import WebSocketManager

    redis_client = redis.Redis(
        host=os.getenv("RUNTIME_TEST_REDIS_HOST", "127.0.0.1"),
        port=int(redis_port),
        db=int(os.getenv("RUNTIME_TEST_REDIS_DB", "15")),
        decode_responses=True,
    )
    redis_client.flushdb()
    monkeypatch.setattr(database, "redis_client", redis_client)

    async def scenario():
        first = WebSocketManager()
        second = WebSocketManager()
        first.instance_id = "instance-a"
        second.instance_id = "instance-b"
        assert await first.start() is True
        assert await second.start() is True
        await asyncio.sleep(0.1)
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()
        await first.connect(ws_a, "user-a", "room-1")
        await second.connect(ws_b, "user-b", "room-1")
        assert redis_client.exists(first._presence_key("room-1", "user-a", "instance-a")) == 1
        assert redis_client.ttl(first._presence_key("room-1", "user-a", "instance-a")) > 0

        await first.broadcast_to_room(
            "room-1",
            {"type": "state_update", "data": {"segment_id": "s2"}, "state_version": 2},
        )
        for _ in range(50):
            if any(message.get("state_version") == 2 for message in ws_b.messages):
                break
            await asyncio.sleep(0.02)
        assert any(message.get("state_version") == 2 for message in ws_b.messages)

        before = len(ws_b.messages)
        await first.broadcast_to_room(
            "room-1",
            {"type": "state_update", "data": {"segment_id": "stale"}, "state_version": 1},
        )
        await asyncio.sleep(0.1)
        assert len(ws_b.messages) == before

        await first.disconnect("user-a", ws_a)
        assert redis_client.exists(first._presence_key("room-1", "user-a", "instance-a")) == 0
        await first.stop()
        await second.stop()

    try:
        asyncio.run(scenario())
    finally:
        redis_client.flushdb()
        redis_client.close()
