import asyncio

from utils.http_client_pool import AsyncHttpClientPool


def test_get_client_reuses_same_client_in_same_loop():
    """同一事件循环、同一用途和超时时间应复用同一个客户端。"""

    async def _run():
        pool = AsyncHttpClientPool()
        try:
            # 这里验证连接池 key 生效，避免相同场景下重复创建 AsyncClient。
            first_client = pool.get_client("voice_tts", 30.0)
            second_client = pool.get_client("voice_tts", 30.0)
            assert first_client is second_client
        finally:
            await pool.aclose_all()

    asyncio.run(_run())


def test_use_client_keeps_client_open_until_pool_close():
    """use_client 退出上下文时不应立刻关闭客户端，而应由池统一回收。"""

    async def _run():
        pool = AsyncHttpClientPool()
        async with pool.use_client("voice_asr", 30.0) as client:
            pooled_client = client
            assert not pooled_client.is_closed

        # 上下文退出后客户端仍保持可复用，直到显式关闭整个池。
        assert not pooled_client.is_closed
        await pool.aclose_all()
        assert pooled_client.is_closed

    asyncio.run(_run())
