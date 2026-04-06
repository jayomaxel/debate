"""
httpx 异步客户端连接池。
用于复用 LLM/TTS 等高频 HTTP 调用的连接，减少重复建连和 TLS 握手开销。
"""

import asyncio
from contextlib import asynccontextmanager
from threading import RLock
from typing import AsyncIterator, Dict, Tuple

import httpx


class AsyncHttpClientPool:
    """
    轻量级 AsyncClient 连接池。

    这里按“用途 + timeout + 当前事件循环”分桶，
    既能在服务运行期复用连接，也能避免测试场景跨事件循环复用同一客户端。
    """

    def __init__(self) -> None:
        """
        初始化连接池。
        """
        self._clients: Dict[Tuple[str, float, int], httpx.AsyncClient] = {}
        self._lock = RLock()

    def _build_key(self, purpose: str, timeout: float) -> Tuple[str, float, int]:
        """
        生成连接池 key。

        Args:
            purpose: 客户端用途标识
            timeout: 当前客户端超时时间

        Returns:
            连接池 key
        """
        try:
            loop_key = id(asyncio.get_running_loop())
        except RuntimeError:
            loop_key = 0
        return (purpose, float(timeout), loop_key)

    def get_client(self, purpose: str, timeout: float) -> httpx.AsyncClient:
        """
        获取可复用的 AsyncClient。

        Args:
            purpose: 客户端用途标识
            timeout: 当前客户端超时时间

        Returns:
            可复用的 AsyncClient 实例
        """
        key = self._build_key(purpose, timeout)
        with self._lock:
            client = self._clients.get(key)
            if client is None:
                # 为高频调用保留更多 keep-alive 连接，减少重复握手开销。
                client = httpx.AsyncClient(
                    timeout=timeout,
                    limits=httpx.Limits(
                        max_connections=100,
                        max_keepalive_connections=20,
                        keepalive_expiry=30.0,
                    ),
                )
                self._clients[key] = client
            return client

    @asynccontextmanager
    async def use_client(
        self,
        purpose: str,
        timeout: float,
    ) -> AsyncIterator[httpx.AsyncClient]:
        """
        以 async with 的方式复用池中的客户端。
        这里不会在退出上下文时关闭客户端，而是在应用关闭时统一释放连接。
        """
        client = self.get_client(purpose, timeout)
        yield client

    async def aclose_all(self) -> None:
        """
        关闭连接池中的全部客户端。
        应用关闭时调用，避免遗留未关闭连接。
        """
        with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()

        for client in clients:
            await client.aclose()


async_http_client_pool = AsyncHttpClientPool()
