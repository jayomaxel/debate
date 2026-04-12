"""
配置管理服务。
负责统一读取和更新系统配置，并为高频链路提供进程内缓存。
"""
from copy import deepcopy
import os
from threading import RLock
from typing import Optional, Type, TypeVar
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from logging_config import get_logger
from models.config import AsrConfig as AsrConfigModel
from models.config import CozeConfig as CozeConfigModel
from models.config import EmailConfig as EmailConfigModel
from models.config import ModelConfig as ModelConfigModel
from models.config import TtsConfig as TtsConfigModel
from models.config import VectorConfig as VectorConfigModel

logger = get_logger(__name__)
ConfigModelT = TypeVar("ConfigModelT")


class ConfigService:
    """
    配置服务类。
    用于统一管理模型、TTS、ASR、Coze、向量和邮件配置。
    """

    # 进程内配置缓存，减少 AI 发言等高频链路里的重复查库。
    _config_cache: dict[str, dict] = {}
    _cache_lock = RLock()

    def __init__(self, db: Session):
        """
        初始化配置服务。

        Args:
            db: 数据库会话
        """
        self.db = db

    @staticmethod
    def _clone_cache_value(value):
        """
        复制可变对象，避免调用方修改返回值时污染缓存。
        """
        if isinstance(value, (dict, list)):
            return deepcopy(value)
        return value

    def _build_cache_key(self, model_cls: Type[ConfigModelT]) -> str:
        """
        统一生成缓存 key。
        这里额外带上当前数据库连接标识，避免测试环境或多数据库场景串缓存。
        """
        bind = self.db.get_bind() if self.db is not None else None
        bind_key = str(id(bind))
        model_key = str(getattr(model_cls, "__tablename__", model_cls.__name__))
        return f"{bind_key}:{model_key}"

    @classmethod
    def _build_cache_payload(cls, config: ConfigModelT) -> dict:
        """
        将 ORM 配置对象转成纯数据快照，避免把带 session 状态的对象直接跨请求复用。
        """
        payload = {}
        for column in config.__table__.columns:
            payload[column.name] = cls._clone_cache_value(
                getattr(config, column.name, None)
            )
        return payload

    @classmethod
    def _restore_cached_config(
        cls, model_cls: Type[ConfigModelT], payload: Optional[dict]
    ) -> Optional[ConfigModelT]:
        """
        从缓存快照恢复轻量配置对象，只用于只读场景。
        """
        if not payload:
            return None

        restored_config = model_cls()
        for field_name, field_value in payload.items():
            setattr(
                restored_config,
                field_name,
                cls._clone_cache_value(field_value),
            )
        return restored_config

    def _get_cached_config(self, model_cls: Type[ConfigModelT]) -> Optional[ConfigModelT]:
        """
        优先从进程内缓存读取配置，降低数据库访问耗时。
        """
        cache_key = self._build_cache_key(model_cls)
        with self._cache_lock:
            payload = self._config_cache.get(cache_key)
        return self._restore_cached_config(model_cls, payload)

    def _set_cached_config(self, config: ConfigModelT) -> None:
        """
        用最新配置覆盖缓存。管理端保存成功后会立即调用，保证缓存同步。
        """
        cache_key = self._build_cache_key(type(config))
        payload = self._build_cache_payload(config)
        with self._cache_lock:
            self._config_cache[cache_key] = payload

    @classmethod
    def invalidate_cache(cls, model_cls: Optional[Type[ConfigModelT]] = None) -> None:
        """
        清理指定配置缓存；不传类型时清空全部缓存。
        """
        with cls._cache_lock:
            if model_cls is None:
                cls._config_cache.clear()
                return
            model_key = str(getattr(model_cls, "__tablename__", model_cls.__name__))
            cache_keys = [
                cache_key
                for cache_key in cls._config_cache.keys()
                if cache_key.endswith(f":{model_key}")
            ]
            for cache_key in cache_keys:
                cls._config_cache.pop(cache_key, None)

    def _normalize_tts_parameters(self, parameters: Optional[dict]) -> dict:
        """
        统一整理 TTS 参数，确保后端语速和音色字段始终可用。
        """
        normalized_parameters = (
            dict(parameters) if isinstance(parameters, dict) else {}
        )

        if not str(normalized_parameters.get("provider") or "").strip():
            normalized_parameters["provider"] = "dashscope"

        if not str(normalized_parameters.get("voice") or "").strip():
            normalized_parameters["voice"] = "Cherry"

        if not str(normalized_parameters.get("language_type") or "").strip():
            normalized_parameters["language_type"] = "Chinese"

        raw_speed = normalized_parameters.get("speed")
        try:
            speed = float(raw_speed)
        except (TypeError, ValueError):
            speed = settings.TTS_DEFAULT_SPEED

        if speed < 0.25 or speed > 4.0:
            speed = settings.TTS_DEFAULT_SPEED

        normalized_parameters["speed"] = speed
        return normalized_parameters

    @staticmethod
    def _get_public_base_url() -> str:
        return os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")

    @staticmethod
    def _is_cpolar_host(hostname: str) -> bool:
        host = (hostname or "").lower()
        return host.endswith(".cpolar.cn") or host.endswith(".cpolar.top")

    @staticmethod
    def _is_valid_public_file_url_prefix(url: Optional[str]) -> bool:
        normalized_url = (url or "").strip()
        if not normalized_url:
            return False

        parsed_url = urlparse(normalized_url)
        if parsed_url.scheme not in {"http", "https"}:
            return False
        if not parsed_url.netloc:
            return False

        hostname = (parsed_url.hostname or "").lower()
        return hostname not in {"localhost", "127.0.0.1"}

    @classmethod
    def _resolve_public_file_url_prefix(
        cls,
        current_prefix: Optional[str],
        public_base_url: str,
    ) -> Optional[str]:
        public_base_url = (public_base_url or "").strip().rstrip("/")
        if not public_base_url:
            return None

        desired_prefix = f"{public_base_url}/uploads/asr"
        normalized_current = (current_prefix or "").strip().rstrip("/")
        if not normalized_current:
            return desired_prefix
        if normalized_current == desired_prefix:
            return desired_prefix
        if not cls._is_valid_public_file_url_prefix(normalized_current):
            return desired_prefix

        current_host = urlparse(normalized_current).hostname or ""
        if cls._is_cpolar_host(current_host):
            return desired_prefix

        return normalized_current

    async def get_model_config(self) -> ModelConfigModel:
        """
        获取当前 AI 模型配置。
        """
        try:
            cached_config = self._get_cached_config(ModelConfigModel)
            if cached_config is not None:
                logger.debug("命中模型配置缓存")
                return cached_config

            config = self.db.execute(
                select(ModelConfigModel).limit(1)
            ).scalar_one_or_none()

            if config:
                self._set_cached_config(config)
                logger.info(f"获取模型配置成功: {config.model_name}")
                return config

            logger.info("数据库中无模型配置，使用环境变量创建默认配置")
            default_config = ModelConfigModel(
                model_name=settings.OPENAI_MODEL_NAME,
                api_endpoint=f"{settings.OPENAI_BASE_URL}/chat/completions",
                api_key=settings.OPENAI_API_KEY or "",
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                parameters={},
            )
            self.db.add(default_config)
            self.db.commit()
            self.db.refresh(default_config)
            self._set_cached_config(default_config)
            logger.info(f"默认模型配置已创建: {default_config.model_name}")
            return default_config

        except Exception as e:
            logger.error(f"获取模型配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def update_model_config(
        self,
        model_name: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        parameters: Optional[dict] = None,
    ) -> ModelConfigModel:
        """
        更新 AI 模型配置。
        """
        try:
            config = self.db.execute(
                select(ModelConfigModel).limit(1)
            ).scalar_one_or_none()

            if not config:
                config = ModelConfigModel(
                    model_name=model_name or "gpt-3.5-turbo",
                    api_endpoint=api_endpoint
                    or "https://api.openai.com/v1/chat/completions",
                    api_key=api_key or "",
                    temperature=temperature if temperature is not None else 0.7,
                    max_tokens=max_tokens or 2000,
                    parameters=parameters or {},
                )
                self.db.add(config)
                logger.info("创建新的模型配置")
            else:
                if model_name is not None:
                    config.model_name = model_name
                if api_endpoint is not None:
                    config.api_endpoint = api_endpoint
                if api_key is not None:
                    config.api_key = api_key
                if temperature is not None:
                    config.temperature = temperature
                if max_tokens is not None:
                    config.max_tokens = max_tokens
                if parameters is not None:
                    config.parameters = parameters
                logger.info(f"更新模型配置: {config.model_name}")

            self.db.commit()
            self.db.refresh(config)
            self._set_cached_config(config)
            return config

        except Exception as e:
            logger.error(f"更新模型配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def get_asr_config(self) -> AsrConfigModel:
        """
        获取 ASR 配置。
        """
        try:
            cached_config = self._get_cached_config(AsrConfigModel)
            if cached_config is not None:
                logger.debug("命中ASR配置缓存")
                return cached_config

            config = self.db.execute(
                select(AsrConfigModel).limit(1)
            ).scalar_one_or_none()
            if config:
                updated = False
                params = (
                    dict(config.parameters or {})
                    if isinstance(config.parameters, dict)
                    else {}
                )
                if "file_url_prefix" not in params and isinstance(
                    params.get("fileUrlPrefix"), str
                ):
                    params["file_url_prefix"] = params.get("fileUrlPrefix")
                    updated = True

                provider = params.get("provider")
                should_need_file_url = (
                    provider == "dashscope"
                    or (config.model_name or "").startswith("qwen")
                    or ("dashscope" in (config.api_endpoint or ""))
                )
                public_base_url = self._get_public_base_url()
                if should_need_file_url:
                    current_prefix = (params.get("file_url_prefix") or "").strip()
                    resolved_prefix = self._resolve_public_file_url_prefix(
                        current_prefix,
                        public_base_url,
                    )
                    if resolved_prefix and resolved_prefix != current_prefix.rstrip("/"):
                        params["file_url_prefix"] = resolved_prefix
                        updated = True

                if updated:
                    # 读取时顺手补齐旧字段，避免后续链路再做兜底判断。
                    config.parameters = params
                    self.db.commit()
                    self.db.refresh(config)

                self._set_cached_config(config)
                logger.info(f"获取ASR配置成功: {config.model_name}")
                return config

            logger.info("数据库中无ASR配置，使用环境变量创建默认配置")
            public_base_url = self._get_public_base_url()
            default_config = AsrConfigModel(
                model_name=settings.ASR_MODEL_NAME,
                api_endpoint=settings.ASR_API_ENDPOINT,
                api_key=(
                    settings.ASR_API_KEY
                    or os.getenv("DASHSCOPE_API_KEY", "")
                    or settings.OPENAI_API_KEY
                    or ""
                ),
                parameters={
                    "provider": "dashscope",
                    "language_type": "Chinese",
                    "channel_id": [0],
                    "enable_itn": False,
                    "enable_words": True,
                },
            )
            resolved_prefix = self._resolve_public_file_url_prefix(
                default_config.parameters.get("file_url_prefix"),
                public_base_url,
            )
            if resolved_prefix:
                default_config.parameters["file_url_prefix"] = resolved_prefix
            self.db.add(default_config)
            self.db.commit()
            self.db.refresh(default_config)
            self._set_cached_config(default_config)
            return default_config
        except Exception as e:
            logger.error(f"获取ASR配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def update_asr_config(
        self,
        model_name: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        parameters: Optional[dict] = None,
    ) -> AsrConfigModel:
        """
        更新 ASR 配置。
        """
        try:
            config = self.db.execute(
                select(AsrConfigModel).limit(1)
            ).scalar_one_or_none()
            public_base_url = self._get_public_base_url()
            if not config:
                normalized_parameters = (
                    dict(parameters) if isinstance(parameters, dict) else None
                )
                if normalized_parameters and "file_url_prefix" not in normalized_parameters:
                    if isinstance(normalized_parameters.get("fileUrlPrefix"), str):
                        normalized_parameters["file_url_prefix"] = (
                            normalized_parameters.get("fileUrlPrefix")
                        )
                config = AsrConfigModel(
                    model_name=model_name or settings.ASR_MODEL_NAME,
                    api_endpoint=api_endpoint or settings.ASR_API_ENDPOINT,
                    api_key=(
                        api_key
                        or settings.ASR_API_KEY
                        or os.getenv("DASHSCOPE_API_KEY", "")
                        or settings.OPENAI_API_KEY
                        or ""
                    ),
                    parameters=normalized_parameters
                    or {
                        "provider": "dashscope",
                        "language_type": "Chinese",
                        "channel_id": [0],
                        "enable_itn": False,
                        "enable_words": True,
                    },
                )
                resolved_prefix = self._resolve_public_file_url_prefix(
                    config.parameters.get("file_url_prefix"),
                    public_base_url,
                )
                if resolved_prefix:
                    config.parameters["file_url_prefix"] = resolved_prefix
                self.db.add(config)
            else:
                if model_name is not None:
                    config.model_name = model_name
                if api_endpoint is not None:
                    config.api_endpoint = api_endpoint
                if api_key is not None:
                    config.api_key = api_key
                if parameters is not None:
                    normalized_parameters = (
                        dict(parameters) if isinstance(parameters, dict) else {}
                    )
                    if "file_url_prefix" not in normalized_parameters and isinstance(
                        normalized_parameters.get("fileUrlPrefix"), str
                    ):
                        normalized_parameters["file_url_prefix"] = (
                            normalized_parameters.get("fileUrlPrefix")
                        )

                    provider = normalized_parameters.get("provider") or (
                        config.parameters or {}
                    ).get("provider")
                    next_model_name = (
                        model_name if model_name is not None else config.model_name
                    ) or ""
                    next_api_endpoint = (
                        api_endpoint if api_endpoint is not None else config.api_endpoint
                    ) or ""
                    should_need_file_url = (
                        provider == "dashscope"
                        or next_model_name.startswith("qwen")
                        or ("dashscope" in next_api_endpoint)
                    )
                    if should_need_file_url:
                        resolved_prefix = self._resolve_public_file_url_prefix(
                            normalized_parameters.get("file_url_prefix"),
                            public_base_url,
                        )
                        if resolved_prefix:
                            normalized_parameters["file_url_prefix"] = resolved_prefix

                    config.parameters = normalized_parameters

            self.db.commit()
            self.db.refresh(config)
            self._set_cached_config(config)
            return config
        except Exception as e:
            logger.error(f"更新ASR配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def get_tts_config(self) -> TtsConfigModel:
        """
        获取 TTS 配置。
        """
        try:
            cached_config = self._get_cached_config(TtsConfigModel)
            if cached_config is not None:
                logger.debug("命中TTS配置缓存")
                return cached_config

            config = self.db.execute(
                select(TtsConfigModel).limit(1)
            ).scalar_one_or_none()
            if config:
                normalized_parameters = self._normalize_tts_parameters(
                    config.parameters
                )
                if normalized_parameters != (config.parameters or {}):
                    # 读取时补齐旧字段，避免 AI 发言链路每次都做兜底。
                    config.parameters = normalized_parameters
                    self.db.commit()
                    self.db.refresh(config)
                self._set_cached_config(config)
                logger.info(f"获取TTS配置成功: {config.model_name}")
                return config

            logger.info("数据库中无TTS配置，使用环境变量创建默认配置")
            default_config = TtsConfigModel(
                model_name=settings.TTS_MODEL_NAME,
                api_endpoint=settings.TTS_API_ENDPOINT,
                api_key=(
                    settings.TTS_API_KEY
                    or os.getenv("DASHSCOPE_API_KEY", "")
                    or settings.OPENAI_API_KEY
                    or ""
                ),
                parameters=self._normalize_tts_parameters(None),
            )
            self.db.add(default_config)
            self.db.commit()
            self.db.refresh(default_config)
            self._set_cached_config(default_config)
            return default_config
        except Exception as e:
            logger.error(f"获取TTS配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def update_tts_config(
        self,
        model_name: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        parameters: Optional[dict] = None,
    ) -> TtsConfigModel:
        """
        更新 TTS 配置。
        """
        try:
            config = self.db.execute(
                select(TtsConfigModel).limit(1)
            ).scalar_one_or_none()
            normalized_parameters = (
                self._normalize_tts_parameters(parameters)
                if parameters is not None
                else None
            )
            if not config:
                config = TtsConfigModel(
                    model_name=model_name or settings.TTS_MODEL_NAME,
                    api_endpoint=api_endpoint or settings.TTS_API_ENDPOINT,
                    api_key=(
                        api_key
                        or settings.TTS_API_KEY
                        or os.getenv("DASHSCOPE_API_KEY", "")
                        or settings.OPENAI_API_KEY
                        or ""
                    ),
                    parameters=normalized_parameters
                    or self._normalize_tts_parameters(None),
                )
                self.db.add(config)
            else:
                if model_name is not None:
                    config.model_name = model_name
                if api_endpoint is not None:
                    config.api_endpoint = api_endpoint
                if api_key is not None:
                    config.api_key = api_key
                if parameters is not None:
                    # 保存前统一规整参数，避免脏输入直接影响 AI 发言 TTS。
                    config.parameters = normalized_parameters

            self.db.commit()
            self.db.refresh(config)
            self._set_cached_config(config)
            return config
        except Exception as e:
            logger.error(f"更新TTS配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def get_coze_config(self) -> CozeConfigModel:
        """
        获取当前 Coze 配置。
        """
        try:
            cached_config = self._get_cached_config(CozeConfigModel)
            if cached_config is not None:
                logger.debug("命中Coze配置缓存")
                return cached_config

            config = self.db.execute(
                select(CozeConfigModel).limit(1)
            ).scalar_one_or_none()

            if config:
                self._set_cached_config(config)
                logger.info("获取Coze配置成功")
                return config

            logger.info("数据库中无Coze配置，使用环境变量创建默认配置")
            default_config = CozeConfigModel(
                api_token=settings.COZE_API_KEY or "",
                parameters={"base_url": settings.COZE_BASE_URL},
            )
            self.db.add(default_config)
            self.db.commit()
            self.db.refresh(default_config)
            self._set_cached_config(default_config)
            logger.info("默认Coze配置已创建")
            return default_config

        except Exception as e:
            logger.error(f"获取Coze配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def update_coze_config(
        self,
        debater_1_bot_id: Optional[str] = None,
        debater_2_bot_id: Optional[str] = None,
        debater_3_bot_id: Optional[str] = None,
        debater_4_bot_id: Optional[str] = None,
        judge_bot_id: Optional[str] = None,
        mentor_bot_id: Optional[str] = None,
        api_token: Optional[str] = None,
        parameters: Optional[dict] = None,
    ) -> CozeConfigModel:
        """
        更新 Coze 配置。
        """
        try:
            config = self.db.execute(
                select(CozeConfigModel).limit(1)
            ).scalar_one_or_none()

            if not config:
                config = CozeConfigModel(
                    debater_1_bot_id=debater_1_bot_id or "",
                    debater_2_bot_id=debater_2_bot_id or "",
                    debater_3_bot_id=debater_3_bot_id or "",
                    debater_4_bot_id=debater_4_bot_id or "",
                    judge_bot_id=judge_bot_id or "",
                    mentor_bot_id=mentor_bot_id or "",
                    api_token=api_token or "",
                    parameters=parameters or {},
                )
                self.db.add(config)
                logger.info("创建新的Coze配置")
            else:
                if debater_1_bot_id is not None:
                    config.debater_1_bot_id = debater_1_bot_id
                if debater_2_bot_id is not None:
                    config.debater_2_bot_id = debater_2_bot_id
                if debater_3_bot_id is not None:
                    config.debater_3_bot_id = debater_3_bot_id
                if debater_4_bot_id is not None:
                    config.debater_4_bot_id = debater_4_bot_id
                if judge_bot_id is not None:
                    config.judge_bot_id = judge_bot_id
                if mentor_bot_id is not None:
                    config.mentor_bot_id = mentor_bot_id
                if api_token is not None:
                    config.api_token = api_token
                if parameters is not None:
                    config.parameters = parameters
                logger.info("更新Coze配置")

            self.db.commit()
            self.db.refresh(config)
            self._set_cached_config(config)
            return config

        except Exception as e:
            logger.error(f"更新Coze配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def get_vector_config(self) -> VectorConfigModel:
        """
        获取当前向量模型配置。
        """
        try:
            cached_config = self._get_cached_config(VectorConfigModel)
            if cached_config is not None:
                logger.debug("命中向量配置缓存")
                return cached_config

            config = self.db.execute(
                select(VectorConfigModel).limit(1)
            ).scalar_one_or_none()

            if config:
                self._set_cached_config(config)
                logger.info(f"获取向量配置成功: {config.model_name}")
                return config

            logger.info("数据库中无向量配置，使用环境变量创建默认配置")
            embedding_model = os.getenv(
                "OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"
            )
            api_key = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

            default_config = VectorConfigModel(
                model_name=embedding_model,
                api_endpoint=f"{base_url.rstrip('/')}/embeddings",
                api_key=api_key,
                embedding_dimension=1536,
                parameters={},
            )
            self.db.add(default_config)
            self.db.commit()
            self.db.refresh(default_config)
            self._set_cached_config(default_config)
            logger.info(f"默认向量配置已创建: {default_config.model_name}")
            return default_config

        except Exception as e:
            logger.error(f"获取向量配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def update_vector_config(
        self,
        model_name: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        embedding_dimension: Optional[int] = None,
        parameters: Optional[dict] = None,
    ) -> VectorConfigModel:
        """
        更新向量模型配置。
        """
        try:
            from services.kb_vector_schema_service import KBVectorSchemaService

            config = self.db.execute(
                select(VectorConfigModel).limit(1)
            ).scalar_one_or_none()

            if not config:
                config = VectorConfigModel(
                    model_name=model_name or "text-embedding-ada-002",
                    api_endpoint=api_endpoint
                    or "https://api.openai.com/v1/embeddings",
                    api_key=api_key or "",
                    embedding_dimension=embedding_dimension or 1536,
                    parameters=parameters or {},
                )
                self.db.add(config)
                logger.info("创建新的向量配置")
            else:
                if model_name is not None:
                    config.model_name = model_name
                if api_endpoint is not None:
                    config.api_endpoint = api_endpoint
                if api_key is not None:
                    config.api_key = api_key
                if embedding_dimension is not None:
                    config.embedding_dimension = embedding_dimension
                if parameters is not None:
                    config.parameters = parameters
                logger.info(f"更新向量配置: {config.model_name}")

            self.db.flush()
            KBVectorSchemaService.ensure_schema_matches_dimension(
                db=self.db,
                target_dimension=int(config.embedding_dimension or 1536),
            )
            self.db.commit()
            self.db.refresh(config)
            self._set_cached_config(config)
            return config

        except Exception as e:
            logger.error(f"更新向量配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def get_email_config(self) -> EmailConfigModel:
        """
        获取邮件配置。
        """
        try:
            cached_config = self._get_cached_config(EmailConfigModel)
            if cached_config is not None:
                logger.debug("命中邮件配置缓存")
                return cached_config

            config = self.db.execute(
                select(EmailConfigModel).limit(1)
            ).scalar_one_or_none()

            if config:
                self._set_cached_config(config)
                logger.info("获取邮件配置成功")
                return config

            logger.info("数据库中无邮件配置，使用环境变量创建默认配置")
            default_config = EmailConfigModel(
                smtp_host=settings.SMTP_HOST or "smtp.gmail.com",
                smtp_port=settings.SMTP_PORT or 587,
                smtp_user=settings.SMTP_USER or "",
                smtp_password=settings.SMTP_PASSWORD or "",
                from_email=settings.SMTP_FROM_EMAIL or settings.SMTP_USER or "",
                auto_send_enabled=False,
            )
            self.db.add(default_config)
            self.db.commit()
            self.db.refresh(default_config)
            self._set_cached_config(default_config)
            return default_config
        except Exception as e:
            logger.error(f"获取邮件配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def update_email_config(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
        auto_send_enabled: Optional[bool] = None,
    ) -> EmailConfigModel:
        """
        更新邮件配置。
        """
        try:
            config = self.db.execute(
                select(EmailConfigModel).limit(1)
            ).scalar_one_or_none()

            if not config:
                config = EmailConfigModel(
                    smtp_host=smtp_host or settings.SMTP_HOST or "smtp.gmail.com",
                    smtp_port=smtp_port or settings.SMTP_PORT or 587,
                    smtp_user=smtp_user or settings.SMTP_USER or "",
                    smtp_password=smtp_password or settings.SMTP_PASSWORD or "",
                    from_email=from_email
                    or settings.SMTP_FROM_EMAIL
                    or settings.SMTP_USER
                    or "",
                    auto_send_enabled=(
                        auto_send_enabled if auto_send_enabled is not None else False
                    ),
                )
                self.db.add(config)
            else:
                if smtp_host is not None:
                    config.smtp_host = smtp_host
                if smtp_port is not None:
                    config.smtp_port = smtp_port
                if smtp_user is not None:
                    config.smtp_user = smtp_user
                if smtp_password is not None:
                    config.smtp_password = smtp_password
                if from_email is not None:
                    config.from_email = from_email
                if auto_send_enabled is not None:
                    config.auto_send_enabled = auto_send_enabled

            self.db.commit()
            self.db.refresh(config)
            self._set_cached_config(config)
            return config
        except Exception as e:
            logger.error(f"更新邮件配置失败: {e}", exc_info=True)
            self.db.rollback()
            raise
