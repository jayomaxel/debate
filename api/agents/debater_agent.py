"""
AI辩手Agent
负责生成AI辩手的发言内容
"""
import json
import time

from logging_config import get_logger
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from services.config_service import ConfigService
from services.coze_client import CozeClient
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
    LLM_HTTP_TIMEOUT_SECONDS = 30.0

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

            return await self._call_llm_once(
                endpoint=endpoint,
                headers=headers,
                payload=payload,
            )

            config_service = ConfigService(self.db)
            model_config = await config_service.get_model_config()

            api_key = (model_config.api_key or "").strip() or (settings.OPENAI_API_KEY or "").strip()
            if not api_key:
                return f"[AI辩手{self.position}未配置模型API Key]"

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

            role_style = {
                1: "立论者：结构化输出，抓住对方漏洞并给出数据/事实反驳",
                2: "盘问者：提问尖锐，追问定义与证据，识别空泛论述并压缩对方空间",
                3: "对手：高压追问逻辑矛盾；当对方卡壳时转为引导性提问",
                4: "总结者：全场记忆，归纳对方未回答点并上升价值层面",
            }.get(self.position, "")

            system_prompt = (
                f"你是反方（反对方）的{self.position}辩手。{role_style}\n"
                f"要求：中文输出；简洁有力；优先引用对方刚才说法进行反驳；不要编造具体数据来源；不要输出Markdown代码块；回复不超过{self.MAX_REPLY_CHARS}字。"
            )

            messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
            if context:
                for msg in context[-20:]:
                    role = msg.get("role") or "user"
                    content = msg.get("content") or ""
                    if not content:
                        continue
                    if role not in ("system", "user", "assistant"):
                        role = "user"
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": float(getattr(model_config, "temperature", 0.7) or 0.7),
                "max_tokens": int(getattr(model_config, "max_tokens", 2000) or 2000),
            }

            # 这里改成复用 LLM 连接池，减少每次 AI 发言重新建连的固定耗时。
            client = async_http_client_pool.get_client(
                purpose="debater_llm",
                timeout=self.LLM_HTTP_TIMEOUT_SECONDS,
            )
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            if response.status_code != 200:
                logger.error(f"LLM API错误: {response.status_code} - {response.text}")
                return f"[AI辩手{self.position}暂时无法回应]"
            data = response.json()
            reply = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            # 无论底层模型返回多长，都在这里统一做字符数收口。
            reply = self.limit_reply_text(reply, self.MAX_REPLY_CHARS)
            return reply or f"[AI辩手{self.position}暂时无法回应]"
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
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """
        生成立论陈词
        
        Args:
            topic: 辩题
            stance: 立场（positive/negative）
            knowledge_base_content: 知识库内容（可选）
            
        Returns:
            立论陈词
        """
        stance_text = "正方" if stance == "positive" else "反方"
        
        prompt = f"""
你是{stance_text}的{self.position}辩手，请针对以下辩题进行立论陈词：

辩题：{topic}

要求：
1. 明确表达{stance_text}立场
2. 提出2-3个核心论点
3. 每个论点要有充分的论据支持
4. 语言简洁有力，逻辑清晰
5. 控制在{self.MAX_REPLY_CHARS}字以内
"""
        
        if knowledge_base_content:
            prompt += f"\n\n参考资料：\n{knowledge_base_content}"
        
        return await self._call_agent(prompt, stream_callback=stream_callback)
    
    async def generate_question(
        self,
        topic: str,
        stance: str,
        context: List[Dict],
        opponent_arguments: List[str],
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """
        生成盘问问题
        
        Args:
            topic: 辩题
            stance: 立场
            context: 辩论上下文
            opponent_arguments: 对方论点列表
            
        Returns:
            盘问问题
        """
        stance_text = "正方" if stance == "positive" else "反方"
        opponent_stance = "反方" if stance == "positive" else "正方"
        
        prompt = f"""
你是{stance_text}的{self.position}辩手，现在是盘问环节。

辩题：{topic}

对方（{opponent_stance}）的主要论点：
{chr(10).join(f"- {arg}" for arg in opponent_arguments)}

请提出一个尖锐的问题，要求：
1. 针对对方论点的薄弱环节
2. 问题要具体、明确
3. 能够揭示对方逻辑漏洞或事实错误
4. 控制在{self.MAX_REPLY_CHARS}字以内
"""
        
        return await self._call_agent(prompt, context, stream_callback=stream_callback)
    
    async def generate_response(
        self,
        topic: str,
        stance: str,
        question: str,
        context: List[Dict],
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """
        生成回答
        
        Args:
            topic: 辩题
            stance: 立场
            question: 对方的问题
            context: 辩论上下文
            
        Returns:
            回答
        """
        stance_text = "正方" if stance == "positive" else "反方"
        
        prompt = f"""
你是{stance_text}的{self.position}辩手，对方刚刚提出了以下问题：

问题：{question}

请给出有力的回答，要求：
1. 直接回应问题核心
2. 维护己方立场
3. 提供充分的论据
4. 语言简洁有力
5. 控制在{self.MAX_REPLY_CHARS}字以内
"""
        
        return await self._call_agent(prompt, context, stream_callback=stream_callback)
    
    async def generate_rebuttal(
        self,
        topic: str,
        stance: str,
        opponent_argument: str,
        context: List[Dict],
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """
        生成反驳
        
        Args:
            topic: 辩题
            stance: 立场
            opponent_argument: 对方论点
            context: 辩论上下文
            
        Returns:
            反驳内容
        """
        stance_text = "正方" if stance == "positive" else "反方"
        
        prompt = f"""
你是{stance_text}的{self.position}辩手，对方刚刚提出了以下论点：

对方论点：{opponent_argument}

请进行有力的反驳，要求：
1. 指出对方论点的问题
2. 提供反驳论据
3. 强化己方立场
4. 语言简洁有力
5. 控制在{self.MAX_REPLY_CHARS}字以内
"""
        
        return await self._call_agent(prompt, context, stream_callback=stream_callback)
    
    async def generate_closing_statement(
        self,
        topic: str,
        stance: str,
        context: List[Dict],
        key_points: List[str],
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """
        生成总结陈词
        
        Args:
            topic: 辩题
            stance: 立场
            context: 辩论上下文
            key_points: 己方关键论点
            
        Returns:
            总结陈词
        """
        stance_text = "正方" if stance == "positive" else "反方"
        
        prompt = f"""
你是{stance_text}的{self.position}辩手，现在是总结陈词环节。

辩题：{topic}

己方关键论点：
{chr(10).join(f"- {point}" for point in key_points)}

请进行总结陈词，要求：
1. 回顾己方核心论点
2. 总结辩论中的优势
3. 强调己方立场的合理性
4. 语言有感染力和说服力
5. 控制在{self.MAX_REPLY_CHARS}字以内
"""
        
        return await self._call_agent(prompt, context, stream_callback=stream_callback)
    
    async def generate_free_debate_speech(
        self,
        topic: str,
        stance: str,
        context: List[Dict],
        recent_speeches: List[Dict],
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """
        生成自由辩论发言
        
        Args:
            topic: 辩题
            stance: 立场
            context: 辩论上下文
            recent_speeches: 最近的发言列表
            
        Returns:
            自由辩论发言
        """
        stance_text = "正方" if stance == "positive" else "反方"
        
        # 构建最近发言的摘要
        recent_summary = "\n".join([
            f"{speech.get('speaker', '未知')}: {speech.get('content', '')}"
            for speech in recent_speeches[-5:]  # 最近5条发言
        ])
        
        prompt = f"""
你是{stance_text}的{self.position}辩手，现在是自由辩论环节。

辩题：{topic}

最近的发言：
{recent_summary}

请发表你的观点，要求：
1. 可以反驳对方最近的论点
2. 可以补充己方论据
3. 可以提出新的角度
4. 语言简洁有力
5. 控制在{self.MAX_REPLY_CHARS}字以内
"""
        
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
            stream_callback = kwargs.get("stream_callback")
            text = ""
            
            if speech_type == "opening":
                text = await self.generate_opening_statement(
                    topic,
                    stance,
                    kwargs.get("knowledge_base_content"),
                    stream_callback=stream_callback,
                )
            elif speech_type == "question":
                text = await self.generate_question(
                    topic,
                    stance,
                    context,
                    kwargs.get("opponent_arguments", []),
                    stream_callback=stream_callback,
                )
            elif speech_type == "response":
                text = await self.generate_response(
                    topic,
                    stance,
                    kwargs.get("question", ""),
                    context,
                    stream_callback=stream_callback,
                )
            elif speech_type == "rebuttal":
                text = await self.generate_rebuttal(
                    topic,
                    stance,
                    kwargs.get("opponent_argument", ""),
                    context,
                    stream_callback=stream_callback,
                )
            elif speech_type == "closing":
                text = await self.generate_closing_statement(
                    topic,
                    stance,
                    context,
                    kwargs.get("key_points", []),
                    stream_callback=stream_callback,
                )
            elif speech_type == "free_debate":
                text = await self.generate_free_debate_speech(
                    topic,
                    stance,
                    context,
                    kwargs.get("recent_speeches", []),
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
        role_style = {
            1: "负责开篇立论，先建立己方核心框架。",
            2: "负责补强论证，推进论点展开。",
            3: "负责攻防转换，强化反驳与追问。",
            4: "负责总结收束，突出己方结论与优势。",
        }.get(self.position, "请根据当前轮次自然完成辩论发言。")
        system_prompt = (
            f"你是辩论赛中的第{self.position}位AI辩手，{role_style}\n"
            f"请结合上下文生成自然、口语化、适合直接朗读的中文发言。"
            f"不要输出标题、列表或 Markdown 标记。"
            f"输出必须控制在{self.MAX_REPLY_CHARS}字以内。"
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if context:
            for msg in context[-20:]:
                role = msg.get("role") or "user"
                content = msg.get("content") or ""
                if not content:
                    continue
                if role not in ("system", "user", "assistant"):
                    role = "user"
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})

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
                    f"LLM API閿欒: {response.status_code} - {error_text.decode(errors='ignore')}"
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

        return await self._call_llm_once(
            endpoint=endpoint,
            headers=headers,
            payload=payload,
        )
