"""
模型配置测试服务
用于复用项目当前的模型配置，主动发起一次最小化 LLM 调用，验证配置是否可用。
"""

import time
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from config import settings
from logging_config import get_logger
from services.config_service import ConfigService

logger = get_logger(__name__)


class ModelTestService:
    """模型配置测试服务类"""

    def __init__(self, db: Session):
        """初始化模型测试服务"""
        self.db = db

    @staticmethod
    def build_chat_completion_endpoint(api_endpoint: str) -> str:
        """
        按项目正式调用逻辑拼装聊天补全地址。

        这样测试类与 AI 辩手正式链路保持一致，避免测试通过但正式调用失败。
        """
        normalized_endpoint = (api_endpoint or "").strip()
        if not normalized_endpoint:
            return f"{settings.OPENAI_BASE_URL}/chat/completions"

        if normalized_endpoint.endswith("/chat/completions"):
            return normalized_endpoint
        if normalized_endpoint.endswith("/v1") or normalized_endpoint.endswith(
            "/compatible-mode/v1"
        ):
            return f"{normalized_endpoint}/chat/completions"
        return f"{normalized_endpoint.rstrip('/')}/chat/completions"

    @staticmethod
    def mask_secret(secret: str) -> str:
        """对 API Key 做脱敏显示，避免调试输出泄露完整密钥。"""
        if not secret:
            return ""
        if len(secret) <= 8:
            return "*" * len(secret)
        return f"{secret[:4]}***{secret[-4:]}"

    async def test_model_connection(
        self,
        prompt: str = "请只回复：模型连接测试成功",
        timeout_seconds: float = 30.0,
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        测试当前数据库中的模型配置是否可用。

        Returns:
            (是否成功, 错误信息, 结果详情)
        """
        try:
            config_service = ConfigService(self.db)
            model_config = await config_service.get_model_config()

            api_key = (model_config.api_key or "").strip() or (
                settings.OPENAI_API_KEY or ""
            ).strip()
            if not api_key:
                return False, "模型 API Key 未配置", None

            endpoint = self.build_chat_completion_endpoint(
                (model_config.api_endpoint or "").strip()
            )
            model_name = (model_config.model_name or "").strip() or settings.OPENAI_MODEL_NAME
            temperature = float(getattr(model_config, "temperature", 0.7) or 0.7)
            max_tokens = min(int(getattr(model_config, "max_tokens", 2000) or 2000), 128)

            # 这里刻意使用极简消息体，只验证“配置和连通性”，避免测试本身受复杂提示词影响。
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是模型配置连通性测试助手，请严格简短作答。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            start_time = time.perf_counter()
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            result = {
                "model_name": model_name,
                "api_endpoint": endpoint,
                "api_key_masked": self.mask_secret(api_key),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "latency_ms": latency_ms,
                "status_code": response.status_code,
            }

            if response.status_code != 200:
                error_text = (response.text or "").strip()
                if len(error_text) > 300:
                    error_text = f"{error_text[:300]}..."
                result["error_response"] = error_text
                return False, f"模型接口返回异常状态码: {response.status_code}", result

            response_data = response.json()
            reply = (
                response_data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            result["reply"] = reply
            return True, None, result

        except httpx.ReadTimeout:
            logger.error("模型连接测试超时", exc_info=True)
            return False, f"模型接口读取超时，超过 {timeout_seconds} 秒仍未返回", None
        except httpx.ConnectTimeout:
            logger.error("模型连接测试连接超时", exc_info=True)
            return False, f"模型接口连接超时，超过 {timeout_seconds} 秒仍未连接成功", None
        except httpx.ConnectError as exc:
            logger.error(f"模型连接测试连接失败: {exc}", exc_info=True)
            return False, f"模型接口连接失败: {exc}", None
        except Exception as exc:
            logger.error(f"模型连接测试失败: {exc}", exc_info=True)
            return False, str(exc), None
