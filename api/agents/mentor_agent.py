"""
辅助AI Agent
负责为学生提供实时辅助建议
"""
from logging_config import get_logger
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from services.config_service import ConfigService
from services.coze_client import CozeClient
from services.mode_policy_service import ModePolicyService
from services.prompt_pack_service import PromptBuildContext, PromptPackService
from config import settings

logger = get_logger(__name__)


class MentorAgent:
    """辅助AI Agent"""
    
    def __init__(self, db: Session):
        """
        初始化辅助AI
        
        Args:
            db: 数据库会话
        """
        self.db = db
        # 配置将在调用时动态获取
        self.bot_id = None
        self.api_token = None
        self.base_url = None
        self._coze_context: Optional[List[Dict]] = None

    def _build_prompt_pack_prompt(
        self,
        topic,
        stance,
        student_role,
        phase,
        task_prompt=None,
        context=None,
        task_type=None,
        task_data=None,
    ):
        normalized_stance = "pro" if stance == "positive" else "con"
        role = "affirmative" if stance == "positive" else "negative"
        mode = PromptPackService.resolve_mode_from_context(context)
        build_context = PromptBuildContext(
            agent="mentor",
            mode=mode,
            phase=phase,
            topic=topic,
            role=role,
            speaker_role=student_role or "mentor",
            stance=normalized_stance,
            history=list(context or []),
        )
        if task_type:
            normalized_task_data = dict(task_data or {})
            if task_type in {
                "real_time_suggestion",
                "counter_argument_suggestion",
                "closing_points_suggestion",
            }:
                mentor_length = ModePolicyService.get_policy(
                    mode=mode,
                    agent="mentor",
                    phase=phase,
                )["mentor_length"]
                normalized_task_data["max_chars"] = mentor_length["max_chars"]
            return PromptPackService.render_agent_task_prompt(
                build_context,
                task_type=task_type,
                task_data=normalized_task_data,
            )
        return PromptPackService.render_agent_prompt(build_context, task_prompt=task_prompt)
    
    async def _get_config(self):
        """获取Coze配置"""
        if not self.bot_id:
            config_service = ConfigService(self.db)
            coze_config = await config_service.get_coze_config()
            
            if not coze_config or not coze_config.mentor_bot_id:
                raise ValueError("辅助AI Bot ID未配置")
            
            self.bot_id = coze_config.mentor_bot_id
            self.api_token = coze_config.api_token
            self.base_url = coze_config.parameters.get("base_url", settings.COZE_BASE_URL) if coze_config.parameters else settings.COZE_BASE_URL
    
    async def _call_coze_bot(self, prompt: str) -> str:
        """
        调用Coze Bot
        
        Args:
            prompt: 提示词
            
        Returns:
            Bot的回复
        """
        try:
            # 确保配置已加载
            await self._get_config()

            bot_id = (self.bot_id or "").strip()
            if not bot_id:
                raise ValueError("辅助AI Bot ID未配置")
            coze = CozeClient(api_token=(self.api_token or ""), base_url=(self.base_url or ""))
            history = list(self._coze_context or [])
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
                user_id="mentor_ai",
                raw_messages=raw_messages,
                max_chars_hint=200,
            )
            reply_message = await coze.chat_coze_message_async(
                bot_id=params["bot_id"],
                user_id=params["user_id"],
                messages=params["messages"],
                max_output_chars=200,
            )
            return (reply_message.content or "").strip()
        
        except Exception as e:
            logger.error(f"调用辅助AI失败: {e}", exc_info=True)
            return ""
    
    async def generate_suggestion(
        self,
        topic: str,
        stance: str,
        student_role: str,
        current_phase: str,
        context: List[Dict],
        opponent_recent_speech: Optional[str] = None
    ) -> str:
        """Generate a real-time coaching suggestion through Prompt Pack."""
        prompt = self._build_prompt_pack_prompt(
            topic,
            stance,
            student_role,
            current_phase,
            context=context,
            task_type="real_time_suggestion",
            task_data={
                "opponent_recent_speech": opponent_recent_speech,
                "requirements": [
                    "give one concise actionable suggestion",
                    "help the student express a clearer claim",
                    "suggest usable reasoning or evidence",
                    "point out how to respond to the opponent when relevant",
                ],
                "max_chars": 80,
            },
        )
        self._coze_context = context
        try:
            suggestion = await self._call_coze_bot(prompt)
        finally:
            self._coze_context = None
        return suggestion if suggestion else "Keep the next point clear and logically connected."
    
    async def analyze_weakness(
        self,
        topic: str,
        stance: str,
        student_speeches: List[str],
        opponent_speeches: List[str]
    ) -> Dict[str, str]:
        """Analyze student weakness through Prompt Pack."""
        context = [
            {"speaker_role": "mentor", "content": speech, "phase": "report"}
            for speech in student_speeches
        ] + [
            {"speaker_role": "opponent", "content": speech, "phase": "report"}
            for speech in opponent_speeches
        ]
        prompt = self._build_prompt_pack_prompt(
            topic,
            stance,
            "mentor",
            "report",
            context=context,
            task_type="weakness_analysis",
            task_data={
                "student_speeches": list(student_speeches or []),
                "opponent_speeches": list(opponent_speeches or []),
                "requirements": [
                    "identify the student's main weaknesses",
                    "summarize the opponent's pressure points",
                    "provide concrete improvement advice",
                ],
                "max_chars": 200,
            },
        )
        self._coze_context = context
        try:
            analysis = await self._call_coze_bot(prompt)
        finally:
            self._coze_context = None
        return {
            "analysis": analysis if analysis else "Keep the current strengths and improve claim-evidence linkage.",
            "timestamp": ""
        }
    
    async def suggest_counter_argument(
        self,
        topic: str,
        stance: str,
        opponent_argument: str,
        context: List[Dict]
    ) -> str:
        """Suggest a counter argument through Prompt Pack."""
        prompt = self._build_prompt_pack_prompt(
            topic,
            stance,
            "mentor",
            "free_debate",
            context=context,
            task_type="counter_argument_suggestion",
            task_data={
                "opponent_argument": opponent_argument,
                "requirements": [
                    "identify a flaw or missing premise",
                    "offer a rebuttal angle",
                    "suggest supporting reasoning or evidence",
                ],
                "max_chars": 80,
            },
        )
        self._coze_context = context
        try:
            suggestion = await self._call_coze_bot(prompt)
        finally:
            self._coze_context = None
        return suggestion if suggestion else "Rebut from both logic and factual support."
    
    async def suggest_closing_points(
        self,
        topic: str,
        stance: str,
        key_arguments: List[str],
        debate_summary: str
    ) -> str:
        """Suggest closing points through Prompt Pack."""
        context = [
            {"speaker_role": "mentor", "content": argument, "phase": "closing"}
            for argument in key_arguments
        ]
        if debate_summary:
            context.append(
                {
                    "speaker_role": "mentor",
                    "content": debate_summary,
                    "phase": "closing",
                }
            )
        prompt = self._build_prompt_pack_prompt(
            topic,
            stance,
            "mentor",
            "closing",
            context=context,
            task_type="closing_points_suggestion",
            task_data={
                "key_arguments": list(key_arguments or []),
                "debate_summary": debate_summary,
                "requirements": [
                    "highlight the core claims to repeat",
                    "summarize advantages gained during debate",
                    "suggest a persuasive final lift",
                ],
                "max_chars": 100,
            },
        )
        self._coze_context = context
        try:
            suggestion = await self._call_coze_bot(prompt)
        finally:
            self._coze_context = None
        return suggestion if suggestion else "Review core claims, emphasize advantages, and close with the theme."
