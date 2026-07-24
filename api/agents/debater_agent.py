"""
AI辩手Agent
负责生成AI辩手的发言内容
"""
import asyncio
import json
import os
import time

import httpx
from logging_config import get_logger
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from services.config_service import ConfigService
from services.coze_client import CozeClient
from services.knowledge_base import KnowledgeBase
from services.prompt_pack_service import PromptBuildContext, PromptPackService
from utils.http_client_pool import async_http_client_pool
from utils.voice_processor import voice_processor
from config import settings

logger = get_logger(__name__)


class AIDebaterAgent:
    """AI辩手Agent"""
    # 统一控制AI回复的最大字符数，避免不同模型输出过长。
    MAX_REPLY_CHARS = 300
    # 尽量在这些中文标点附近截断，减少生硬断句。
    _TRUNCATE_PUNCTUATION = "。！？；;.!?\n"
    # LLM HTTP 客户端超时时间，配合连接池按 timeout 分桶复用。
    # A single provider request has a bounded, deploy-time configurable timeout.
    # The flow controller deliberately waits a little longer than this value so
    # it never cancels a healthy request first and starts a competing fallback.
    LLM_HTTP_TIMEOUT_SECONDS = float(
        os.getenv("DEBATER_LLM_TIMEOUT_SECONDS", "45")
    )
    LLM_CONNECT_RETRY_COUNT = 2
    LLM_CONNECT_RETRY_BACKOFF_SECONDS = 0.4

    def __init__(self, position: int, db: Session):
        """
        初始化AI辩手
        
        Args:
            position: 辩手位置（1-4）
            db: 数据库会话
        """
        self.position = position
        self.db = db
        # 配置将在调用时动态获取
        self.bot_id = None
        self.api_token = None
        self.base_url = None

    @staticmethod
    def _knowledge_phase_for_speech(speech_type: str) -> str:
        return {
            "opening": "opening",
            "question": "questioning",
            "response": "questioning",
            "rebuttal": "free_debate",
            "free_debate": "free_debate",
            "closing": "closing",
        }.get(str(speech_type or "").strip(), "free_debate")

    def _load_knowledge_snippets(self, debate_id: Optional[str], speech_type: str) -> List[Dict[str, Any]]:
        if not debate_id:
            return []
        try:
            return KnowledgeBase(self.db).get_knowledge_snippets(
                str(debate_id),
                self._knowledge_phase_for_speech(speech_type),
            )
        except Exception as exc:
            logger.warning("Unable to load debate knowledge snippets: %s", exc)
            return []

    @staticmethod
    def _format_elapsed_seconds(elapsed_seconds: float) -> str:
        """
        统一格式化耗时日志，按秒输出并保留两位小数。
        """
        return f"{max(0.0, float(elapsed_seconds)):.2f}"

    def _log_llm_performance(self, stage: str, details: Dict[str, Any]) -> None:
        """
        统一输出 LLM 性能日志，便于后续按关键字检索。
        """
        logger.info(
            "LLM性能日志-%s: %s",
            stage,
            json.dumps(details, ensure_ascii=False),
        )

    @classmethod
    def limit_reply_text(cls, text: Optional[str], max_chars: int = MAX_REPLY_CHARS) -> str:
        """
        将AI回复限制在指定字符数以内。

        Args:
            text: 原始回复文本
            max_chars: 最大字符数

        Returns:
            截断后的回复文本
        """
        if not text:
            return ""

        cleaned = str(text).strip()
        if len(cleaned) <= max_chars:
            return cleaned

        # 优先在靠近上限的位置寻找合适的句末标点，再做截断。
        search_start = max(0, max_chars - 40)
        cut_index = max_chars
        for idx in range(max_chars, search_start, -1):
            if cleaned[idx - 1] in cls._TRUNCATE_PUNCTUATION:
                cut_index = idx
                break

        truncated = cleaned[:cut_index].strip()
        if len(truncated) > max_chars:
            truncated = cleaned[:max_chars].strip()
        return truncated

    def get_voice_id(self) -> str:
        """
        根据辩手位置返回固定音色。

        Returns:
            对应的音色ID
        """
        voice_map = {
            1: "Cherry",   # 一辩：稳重
            2: "Ethan",    # 二辩：清晰
            3: "Serena",   # 三辩：活泼
            4: "Moon",     # 四辩：深沉
        }
        return voice_map.get(self.position, "Cherry")

    def _build_prompt_pack_prompt(
        self,
        topic,
        stance,
        phase,
        task_prompt=None,
        context=None,
        knowledge_snippets=None,
        task_type=None,
        task_data=None,
    ):
        normalized_stance = "pro" if stance == "positive" else "con"
        role = "affirmative" if stance == "positive" else "negative"
        mode = PromptPackService.resolve_mode_from_context(context)
        build_context = PromptBuildContext(
            agent="debater",
            mode=mode,
            phase=phase,
            topic=topic,
            role=role,
            speaker_role=f"debater_{self.position}",
            stance=normalized_stance,
            history=list(context or [])[-8:],
            knowledge_snippets=list(knowledge_snippets or []),
        )
        if task_type:
            return PromptPackService.render_agent_task_prompt(
                build_context,
                task_type=task_type,
                task_data=task_data or {},
            )
        return PromptPackService.render_agent_prompt(build_context, task_prompt=task_prompt)

    def _build_runtime_system_prompt(
        self,
        *,
        rendered_prompt: str = "",
        context: Optional[List[Dict]] = None,
        stance: str = "negative",
        phase: str = "free_debate",
    ) -> str:
        prompt_phase = self._extract_prompt_pack_field(rendered_prompt, "phase", phase)
        prompt_stance = self._extract_prompt_pack_field(rendered_prompt, "stance", "")
        if prompt_stance == "pro":
            stance = "positive"
        elif prompt_stance == "con":
            stance = "negative"
        phase = prompt_phase
        role_focus = {
            1: "定义、判断标准、证明责任与核心框架",
            2: "盘问设计、证据检验与关键承诺锁定",
            3: "反驳整合、战场收束与即时回应",
            4: "全场总结、影响比较与胜负理由",
        }.get(self.position, "完成当前阶段对应的辩论任务")
        stance_text = "正方" if stance == "positive" else "反方"
        return "\n".join(
            [
                PromptPackService.render_agent_system_prompt("debater"),
                f"当前身份：{stance_text}{self.position}辩。",
                f"当前阶段：{phase}；辩位重点：{role_focus}。",
                f"最终回复不得超过 {self.MAX_REPLY_CHARS} 个中文字符。",
            ]
        )

    @staticmethod
    def _extract_prompt_pack_field(rendered_prompt: str, field_name: str, default: str = "") -> str:
        needle = f'"{field_name}": "'
        text = str(rendered_prompt or "")
        start = text.find(needle)
        if start < 0:
            return default
        start += len(needle)
        end = text.find('"', start)
        if end < 0:
            return default
        return text[start:end].strip() or default
    
    async def _get_config(self):
        """获取Coze配置"""
        if not self.bot_id:
            config_service = ConfigService(self.db)
            coze_config = await config_service.get_coze_config()
            if not coze_config:
                raise ValueError("Coze配置未设置")
            self.bot_id = getattr(coze_config, f"debater_{self.position}_bot_id", "") or ""
            if not self.bot_id:
                raise ValueError(f"AI辩手{self.position}的Bot ID未配置")
            self.api_token = (coze_config.api_token or "").strip()
            self.base_url = (coze_config.parameters.get("base_url") if coze_config.parameters else "") or settings.COZE_BASE_URL
    
    async def _call_coze_bot(
        self,
        prompt: str,
        context: Optional[List[Dict]] = None
    ) -> str:
        """
        调用Coze Bot
        
        Args:
            prompt: 提示词
            context: 上下文消息列表
            
        Returns:
            Bot的回复
        """
        try:
            # 确保配置已加载
            await self._get_config()

            bot_id = (self.bot_id or "").strip()
            if not bot_id:
                raise ValueError(f"AI辩手{self.position}的Bot ID未配置")
            
            coze = CozeClient(api_token=(self.api_token or ""), base_url=(self.base_url or ""))

            history = list(context or [])
            history = history[-10:]
            raw_messages: List[Dict] = []
            for msg in history:
                role = (msg.get("role") or "user").strip().lower()
                if role not in ("user", "assistant"):
                    role = "user"
                raw_messages.append(
                    {
                        "role": role,
                        "content": (msg.get("content") or ""),
                        "conversation_id": msg.get("conversation_id", None),
                    }
                )
            raw_messages.append({"role": "user", "content": prompt, "conversation_id": None})

            params = coze.build_chat_coze_params(
                bot_id=bot_id,
                user_id=f"ai_debater_{self.position}",
                raw_messages=raw_messages,
                max_chars_hint=self.MAX_REPLY_CHARS,
            )
            reply_message = await coze.chat_coze_message_async(
                bot_id=params["bot_id"],
                user_id=params["user_id"],
                messages=params["messages"],
                max_output_chars=self.MAX_REPLY_CHARS,
            )
            # Coze 端和本地端都做一次收口，避免模型偶发超长输出。
            reply = self.limit_reply_text(reply_message.content, self.MAX_REPLY_CHARS)
            if reply:
                logger.info(f"AI辩手{self.position}生成回复成功")
                return reply
            return f"[AI辩手{self.position}暂时无法回应]"
        
        except Exception as e:
            logger.error(f"调用Coze Bot失败: {e}", exc_info=True)
            return f"[AI辩手{self.position}暂时无法回应]"

    async def _call_llm_once_with_connect_retry(
        self,
        endpoint: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> str:
        """Retry only transient connection setup failures with a small bound."""
        max_attempts = self.LLM_CONNECT_RETRY_COUNT + 1
        for attempt in range(1, max_attempts + 1):
            try:
                return await self._call_llm_once(
                    endpoint=endpoint,
                    headers=headers,
                    payload=payload,
                )
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                if attempt >= max_attempts:
                    raise
                delay_seconds = self.LLM_CONNECT_RETRY_BACKOFF_SECONDS * attempt
                logger.warning(
                    "LLM connection failed; retrying position=%s attempt=%s/%s delay=%.1fs error=%s",
                    self.position,
                    attempt + 1,
                    max_attempts,
                    delay_seconds,
                    exc,
                )
                await asyncio.sleep(delay_seconds)

        raise RuntimeError("LLM connection retry loop exited unexpectedly")

    async def _call_llm(
        self,
        prompt: str,
        context: Optional[List[Dict]] = None,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        try:
            endpoint, headers, payload = await self._build_llm_request(
                prompt=prompt,
                context=context,
            )
            if not endpoint:
                return f"[AI辩手{self.position}未配置模型API Key]"

            # 需要增量文本时优先走流式输出；失败后在 helper 内自动回退。
            if stream_callback:
                return await self._call_llm_stream(
                    endpoint=endpoint,
                    headers=headers,
                    payload=payload,
                    stream_callback=stream_callback,
                )

            return await self._call_llm_once_with_connect_retry(
                endpoint=endpoint,
                headers=headers,
                payload=payload,
            )
        except (httpx.TimeoutException, asyncio.TimeoutError):
            raise
        except Exception as e:
            logger.error(f"调用LLM失败: {e}", exc_info=True)
            return f"[AI辩手{self.position}暂时无法回应]"

    async def _call_agent(
        self,
        prompt: str,
        context: Optional[List[Dict]] = None,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        provider = (settings.DEBATE_AI_PROVIDER or "llm").strip().lower()
        if provider == "coze":
            text = await self._call_coze_bot(prompt, context)
            if text and not text.startswith("[AI"):
                if stream_callback:
                    # Coze 当前仍是整段返回，这里把整段文本一次性回调给上层。
                    await stream_callback(text)
                return text
            return await self._call_llm(
                prompt,
                context,
                stream_callback=stream_callback,
            )
        return await self._call_llm(
            prompt,
            context,
            stream_callback=stream_callback,
        )

    async def generate_opening_statement(
        self,
        topic: str,
        stance: str,
        knowledge_base_content: Optional[str] = None,
        knowledge_snippets: Optional[List[Dict[str, Any]]] = None,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """Generate an opening statement through Prompt Pack."""
        prompt = self._build_prompt_pack_prompt(
            topic,
            stance,
            "opening",
            knowledge_snippets=knowledge_snippets,
            task_type="opening_statement",
            task_data={
                "speaker_position": self.position,
                "knowledge_base_content": knowledge_base_content,
                "requirements": [
                    "state the assigned stance clearly",
                    "provide two to three core claims",
                    "support each claim with reasoning or evidence",
                    "keep language concise and logically clear",
                ],
                "max_chars": self.MAX_REPLY_CHARS,
            },
        )
        return await self._call_agent(prompt, stream_callback=stream_callback)
    
    async def generate_question(
        self,
        topic: str,
        stance: str,
        context: List[Dict],
        opponent_arguments: List[str],
        segment_id: Optional[str] = None,
        speaker_role: Optional[str] = None,
        previous_questions: Optional[List[str]] = None,
        question_focus: Optional[str] = None,
        knowledge_snippets: Optional[List[Dict[str, Any]]] = None,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """Generate a cross-examination question through Prompt Pack."""
        normalized_role = str(speaker_role or "").strip()
        normalized_focus = str(question_focus or "").strip()
        cleaned_arguments = [
            str(argument or "").strip()
            for argument in opponent_arguments
            if str(argument or "").strip()
        ]
        cleaned_previous_questions = [
            str(question or "").strip()
            for question in (previous_questions or [])
            if str(question or "").strip()
        ][-3:]
        requirements = [
            "ask exactly one specific question",
            "avoid repeating previous questions",
            "press definition, evidence, logic, boundary, or unanswered points according to role focus",
            "do not invent a previous opponent speech when no opponent argument is supplied",
        ]
        if not cleaned_arguments:
            requirements.extend([
                "不需要等待对方先发言，可直接围绕辩题发问",
                "预判正方可能提出的核心理由并追问其依据",
                "不要引用不存在的上一轮发言",
            ])

        prompt = self._build_prompt_pack_prompt(
            topic,
            stance,
            "questioning",
            context=context,
            knowledge_snippets=knowledge_snippets,
            task_type="cross_examination_question",
            task_data={
                "speaker_position": self.position,
                "segment_id": str(segment_id or "").strip() or "questioning",
                "speaker_role": normalized_role,
                "question_focus": normalized_focus,
                "opponent_arguments": cleaned_arguments,
                "previous_questions": cleaned_previous_questions,
                "requirements": requirements,
                "max_chars": self.MAX_REPLY_CHARS,
            },
        )
        return await self._call_agent(prompt, context, stream_callback=stream_callback)
    
    async def generate_response(
        self,
        topic: str,
        stance: str,
        question: str,
        context: List[Dict],
        knowledge_snippets: Optional[List[Dict[str, Any]]] = None,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """Generate an answer through Prompt Pack."""
        prompt = self._build_prompt_pack_prompt(
            topic,
            stance,
            "questioning",
            context=context,
            knowledge_snippets=knowledge_snippets,
            task_type="question_response",
            task_data={
                "question": question,
                "requirements": [
                    "answer the core question directly",
                    "defend the assigned stance",
                    "provide sufficient reasoning",
                    "keep language concise and forceful",
                ],
                "max_chars": self.MAX_REPLY_CHARS,
            },
        )
        return await self._call_agent(prompt, context, stream_callback=stream_callback)
    
    async def generate_rebuttal(
        self,
        topic: str,
        stance: str,
        opponent_argument: str,
        context: List[Dict],
        knowledge_snippets: Optional[List[Dict[str, Any]]] = None,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """Generate a rebuttal through Prompt Pack."""
        prompt = self._build_prompt_pack_prompt(
            topic,
            stance,
            "free_debate",
            context=context,
            knowledge_snippets=knowledge_snippets,
            task_type="rebuttal",
            task_data={
                "opponent_argument": opponent_argument,
                "requirements": [
                    "identify the issue in the opponent argument",
                    "provide rebuttal reasoning",
                    "strengthen the assigned stance",
                    "avoid copying the opponent wording wholesale",
                ],
                "max_chars": self.MAX_REPLY_CHARS,
            },
        )
        return await self._call_agent(prompt, context, stream_callback=stream_callback)
    
    async def generate_closing_statement(
        self,
        topic: str,
        stance: str,
        context: List[Dict],
        key_points: List[str],
        knowledge_snippets: Optional[List[Dict[str, Any]]] = None,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """Generate a closing statement through Prompt Pack."""
        prompt = self._build_prompt_pack_prompt(
            topic,
            stance,
            "closing",
            context=context,
            knowledge_snippets=knowledge_snippets,
            task_type="closing_statement",
            task_data={
                "key_points": list(key_points or []),
                "requirements": [
                    "review the side's core claims",
                    "summarize advantages from the debate",
                    "reinforce why the stance is reasonable",
                    "use persuasive but concise language",
                ],
                "max_chars": self.MAX_REPLY_CHARS,
            },
        )
        return await self._call_agent(prompt, context, stream_callback=stream_callback)
    
    async def generate_free_debate_speech(
        self,
        topic: str,
        stance: str,
        context: List[Dict],
        recent_speeches: List[Dict],
        knowledge_snippets: Optional[List[Dict[str, Any]]] = None,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """Generate a free-debate speech through Prompt Pack."""
        prompt = self._build_prompt_pack_prompt(
            topic,
            stance,
            "free_debate",
            context=context,
            knowledge_snippets=knowledge_snippets,
            task_type="free_debate_speech",
            task_data={
                "recent_speeches": list(recent_speeches or [])[-5:],
                "requirements": [
                    "rebut recent opponent points when useful",
                    "add supporting reasoning for the assigned side",
                    "introduce a new angle only when it helps the current clash",
                    "keep language concise and forceful",
                ],
                "max_chars": self.MAX_REPLY_CHARS,
            },
        )
        return await self._call_agent(prompt, context, stream_callback=stream_callback)

    async def generate_speech_with_audio(
        self,
        speech_type: str,
        topic: str,
        stance: str,
        context: List[Dict],
        include_audio: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成发言内容并转换为语音
        
        Args:
            speech_type: 发言类型（opening, question, response, rebuttal, closing, free_debate）
            topic: 辩题
            stance: 立场
            context: 辩论上下文
            include_audio: 是否同步生成音频。实时TTS场景下可先只拿文本，再异步补音频。
            **kwargs: 其他参数（根据发言类型不同）
            
        Returns:
            Dict包含：
            - text: 文字内容
            - audio_data: 音频数据（bytes）
            - duration: 音频时长（估算）
        """
        try:
            # 根据发言类型生成文字内容
            # 流式模式下，这里接收上层传入的增量文本回调；非流式模式则保持为None。
            knowledge_snippets = list(kwargs.get("knowledge_snippets") or [])
            if not knowledge_snippets:
                knowledge_snippets = self._load_knowledge_snippets(
                    kwargs.get("debate_id"),
                    speech_type,
                )
            snippet_kwargs = {"knowledge_snippets": knowledge_snippets} if knowledge_snippets else {}
            stream_callback = kwargs.get("stream_callback")
            text = ""
            
            if speech_type == "opening":
                text = await self.generate_opening_statement(
                    topic,
                    stance,
                    kwargs.get("knowledge_base_content"),
                    **snippet_kwargs,
                    stream_callback=stream_callback,
                )
            elif speech_type == "question":
                text = await self.generate_question(
                    topic,
                    stance,
                    context,
                    kwargs.get("opponent_arguments", []),
                    segment_id=kwargs.get("segment_id"),
                    speaker_role=kwargs.get("speaker_role"),
                    previous_questions=kwargs.get("previous_questions", []),
                    question_focus=kwargs.get("question_focus"),
                    **snippet_kwargs,
                    stream_callback=stream_callback,
                )
            elif speech_type == "response":
                text = await self.generate_response(
                    topic,
                    stance,
                    kwargs.get("question", ""),
                    context,
                    **snippet_kwargs,
                    stream_callback=stream_callback,
                )
            elif speech_type == "rebuttal":
                text = await self.generate_rebuttal(
                    topic,
                    stance,
                    kwargs.get("opponent_argument", ""),
                    context,
                    **snippet_kwargs,
                    stream_callback=stream_callback,
                )
            elif speech_type == "closing":
                text = await self.generate_closing_statement(
                    topic,
                    stance,
                    context,
                    kwargs.get("key_points", []),
                    **snippet_kwargs,
                    stream_callback=stream_callback,
                )
            elif speech_type == "free_debate":
                text = await self.generate_free_debate_speech(
                    topic,
                    stance,
                    context,
                    kwargs.get("recent_speeches", []),
                    **snippet_kwargs,
                    stream_callback=stream_callback,
                )
            else:
                raise ValueError(f"Unknown speech type: {speech_type}")

            # 最终输出前再做一次硬限制，防止上游提示词或模型偶发失控。
            text = self.limit_reply_text(text, self.MAX_REPLY_CHARS)
            
            if not text:
                logger.warning(f"Empty text generated for speech type: {speech_type}")
                return {
                    "text": "",
                    "audio_data": None,
                    "duration": 0,
                    "error": "生成内容为空"
                }
            
            # 这里固定音色，保证前端文本先到、后续补音频时仍然使用同一声音。
            voice_id = self.get_voice_id()

            # 实时TTS场景下，先返回文本，音频由调用方异步补齐。
            if not include_audio:
                estimated_duration = len(text) / 2.5
                return {
                    "text": text,
                    "audio_data": None,
                    "duration": estimated_duration,
                    "voice_id": voice_id
                }
            
            # 调用TTS服务转换为语音
            logger.info(f"AI辩手{self.position}生成语音，文字长度: {len(text)}")
            # speed 传 None 时，会自动读取后台 TTS 配置里的语速。
            audio_data = await voice_processor.synthesize_speech(
                text,
                voice_id=voice_id,
                speed=None,
                db=self.db
            )
            
            if not audio_data:
                logger.warning(f"TTS failed for AI辩手{self.position}")
                return {
                    "text": text,
                    "audio_data": None,
                    "duration": 0,
                    "error": "语音合成失败"
                }
            
            # 估算音频时长（中文约2.5字/秒）
            estimated_duration = len(text) / 2.5
            
            logger.info(f"AI辩手{self.position}语音生成成功，时长约{estimated_duration:.1f}秒")
            
            return {
                "text": text,
                "audio_data": audio_data,
                "duration": estimated_duration,
                "voice_id": voice_id
            }
            
        except (httpx.TimeoutException, asyncio.TimeoutError):
            # Preserve the timeout signal so the flow controller can stop the
            # turn once and publish its deterministic fallback. Swallowing the
            # exception here produced an empty draft and triggered retries.
            raise
        except Exception as e:
            logger.error(f"AI辩手{self.position}生成语音失败: {e}", exc_info=True)
            return {
                "text": "",
                "audio_data": None,
                "duration": 0,
                "error": str(e)
            }

    async def _build_llm_request(
        self,
        prompt: str,
        context: Optional[List[Dict]] = None,
    ) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
        """
        统一构造 LLM 请求参数，避免普通调用和流式调用重复拼装。
        """
        config_service = ConfigService(self.db)
        model_config = await config_service.get_model_config()

        api_key = (model_config.api_key or "").strip() or (settings.OPENAI_API_KEY or "").strip()
        if not api_key:
            return "", {}, {}

        api_endpoint = (model_config.api_endpoint or "").strip()
        if not api_endpoint:
            api_endpoint = f"{settings.OPENAI_BASE_URL}/chat/completions"

        if api_endpoint.endswith("/chat/completions"):
            endpoint = api_endpoint
        elif api_endpoint.endswith("/v1") or api_endpoint.endswith("/compatible-mode/v1"):
            endpoint = f"{api_endpoint}/chat/completions"
        else:
            endpoint = f"{api_endpoint.rstrip('/')}/chat/completions"

        model_name = (model_config.model_name or "").strip() or settings.OPENAI_MODEL_NAME
        system_prompt = self._build_runtime_system_prompt(
            rendered_prompt=prompt,
            context=context,
        )

        # The Prompt Pack already contains the trimmed debate history. Sending
        # the same transcript again as chat messages doubled the request size,
        # slowed first-token latency and made provider timeouts much more likely.
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": float(getattr(model_config, "temperature", 0.7) or 0.7),
            "max_tokens": int(getattr(model_config, "max_tokens", 2000) or 2000),
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        return endpoint, headers, payload

    async def _call_llm_once(
        self,
        endpoint: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> str:
        """
        走原有整段返回链路，作为默认路径和流式失败后的兜底路径。
        """
        request_started_at = time.perf_counter()
        prompt_content = (
            ((payload.get("messages") or [{}])[-1] or {}).get("content", "")
        )
        self._log_llm_performance(
            "普通请求开始",
            {
                "position": self.position,
                "model": payload.get("model"),
                "endpoint": endpoint,
                "prompt_content": prompt_content,
            },
        )
        client = async_http_client_pool.get_client(
            purpose="debater_llm",
            timeout=self.LLM_HTTP_TIMEOUT_SECONDS,
        )
        response = await client.post(
            endpoint,
            headers=headers,
            json=payload,
        )
        if response.status_code != 200:
            logger.error(f"LLM API错误: {response.status_code} - {response.text}")
            self._log_llm_performance(
                "普通请求失败",
                {
                    "position": self.position,
                    "model": payload.get("model"),
                    "endpoint": endpoint,
                    "all_content_elapsed_seconds": self._format_elapsed_seconds(
                        time.perf_counter() - request_started_at
                    ),
                    "prompt_content": prompt_content,
                    "error": response.text,
                },
            )
            return f"[AI辩手{self.position}暂时无法回应]"
        data = response.json()
        reply = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        reply = self.limit_reply_text(reply, self.MAX_REPLY_CHARS)
        total_elapsed_seconds = time.perf_counter() - request_started_at
        self._log_llm_performance(
            "普通请求完成",
            {
                "position": self.position,
                "model": payload.get("model"),
                "endpoint": endpoint,
                "all_content_elapsed_seconds": self._format_elapsed_seconds(
                    total_elapsed_seconds
                ),
                "full_content": reply,
            },
        )
        return reply or f"[AI辩手{self.position}暂时无法回应]"

    @staticmethod
    def _extract_stream_delta_text(event: Dict[str, Any]) -> str:
        """
        从兼容 OpenAI 的流式事件中提取本次新增文本。
        """
        choices = event.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return ""

    async def _iter_llm_stream_lines(
        self,
        endpoint: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> AsyncIterator[str]:
        """
        统一解析 SSE 数据行，只向上层暴露 data 部分。
        """
        client = async_http_client_pool.get_client(
            purpose="debater_llm",
            timeout=self.LLM_HTTP_TIMEOUT_SECONDS,
        )
        async with client.stream(
            "POST",
            endpoint,
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise RuntimeError(
                    f"LLM API错误: {response.status_code} - {error_text.decode(errors='ignore')}"
                )

            async for raw_line in response.aiter_lines():
                line = (raw_line or "").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_line = line[5:].strip()
                if data_line:
                    yield data_line

    async def _call_llm_stream(
        self,
        endpoint: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        stream_callback: Callable[[str], Awaitable[None]],
    ) -> str:
        """
        流式拉取 LLM 文本，并把新增文本实时回调给调用方。
        """
        stream_payload = dict(payload)
        stream_payload["stream"] = True
        accumulated = ""
        reached_limit = False
        chunk_index = 0
        request_started_at = time.perf_counter()
        previous_chunk_at = request_started_at
        prompt_content = (
            ((payload.get("messages") or [{}])[-1] or {}).get("content", "")
        )
        self._log_llm_performance(
            "流式请求开始",
            {
                "position": self.position,
                "model": payload.get("model"),
                "endpoint": endpoint,
                "prompt_content": prompt_content,
            },
        )

        try:
            async for data_line in self._iter_llm_stream_lines(
                endpoint=endpoint,
                headers=headers,
                payload=stream_payload,
            ):
                if data_line == "[DONE]":
                    break

                try:
                    event = json.loads(data_line)
                except json.JSONDecodeError:
                    logger.warning(f"忽略无法解析的 LLM 流式片段: {data_line[:120]}")
                    continue

                delta_text = self._extract_stream_delta_text(event)
                if not delta_text or reached_limit:
                    continue

                remaining = self.MAX_REPLY_CHARS - len(accumulated)
                if remaining <= 0:
                    reached_limit = True
                    continue

                clipped_text = delta_text[:remaining]
                if not clipped_text:
                    continue

                accumulated += clipped_text
                chunk_index += 1
                chunk_received_at = time.perf_counter()
                # 这里记录单块增量耗时，便于区分首块慢还是块间间隔慢。
                # self._log_llm_performance(
                #     "流式块",
                #     {
                #         "position": self.position,
                #         "model": payload.get("model"),
                #         "chunk_index": chunk_index,
                #         "chunk_content": clipped_text,
                #         "chunk_elapsed_seconds": self._format_elapsed_seconds(
                #             chunk_received_at - previous_chunk_at
                #         ),
                #         "all_content_elapsed_seconds": self._format_elapsed_seconds(
                #             chunk_received_at - request_started_at
                #         ),
                #     },
                # )
                previous_chunk_at = chunk_received_at
                # 增量文本会立刻交给上层，用于文本秒回和后续句级 TTS。
                await stream_callback(clipped_text)

                if len(accumulated) >= self.MAX_REPLY_CHARS:
                    reached_limit = True

            final_text = self.limit_reply_text(accumulated, self.MAX_REPLY_CHARS)
            if final_text:
                self._log_llm_performance(
                    "流式请求完成",
                    {
                        "position": self.position,
                        "model": payload.get("model"),
                        "chunk_count": chunk_index,
                        "all_content_elapsed_seconds": self._format_elapsed_seconds(
                            time.perf_counter() - request_started_at
                        ),
                        "full_content": final_text,
                    },
                )
                return final_text
        except Exception as exc:
            logger.warning(f"流式 LLM 失败，回退普通请求: {exc}", exc_info=True)
            if accumulated:
                fallback_text = self.limit_reply_text(
                    accumulated, self.MAX_REPLY_CHARS
                )
                self._log_llm_performance(
                    "流式请求异常结束",
                    {
                        "position": self.position,
                        "model": payload.get("model"),
                        "chunk_count": chunk_index,
                        "all_content_elapsed_seconds": self._format_elapsed_seconds(
                            time.perf_counter() - request_started_at
                        ),
                        "full_content": fallback_text,
                        "error": str(exc),
                    },
                )
                return fallback_text
            if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
                # A second synchronous request would double the blocked turn.
                # Let the flow controller produce its context-aware fallback.
                raise

        return await self._call_llm_once_with_connect_retry(
            endpoint=endpoint,
            headers=headers,
            payload=payload,
        )
