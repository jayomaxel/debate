"""
辅助AI Agent
负责为学生提供实时辅助建议
"""
from logging_config import get_logger
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from services.config_service import ConfigService
from services.coze_client import CozeClient
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
        """
        生成辅助建议
        
        Args:
            topic: 辩题
            stance: 立场（positive/negative）
            student_role: 学生角色（debater_1-4）
            current_phase: 当前环节
            context: 辩论上下文
            opponent_recent_speech: 对方最近的发言（可选）
            
        Returns:
            辅助建议
        """
        stance_text = "正方" if stance == "positive" else "反方"
        phase_text = {
            "opening": "立论",
            "questioning": "盘问",
            "free_debate": "自由辩论",
            "closing": "总结陈词"
        }.get(current_phase, current_phase)
        
        prompt = f"""
你是一位经验丰富的辩论教练，正在为{stance_text}的{student_role}辩手提供实时指导。

辩题：{topic}
当前环节：{phase_text}
"""
        
        if opponent_recent_speech:
            prompt += f"\n对方刚刚说：{opponent_recent_speech}\n"
        
        prompt += """
请给出简短的建议（50字以内），帮助学生：
1. 如何更好地表达观点
2. 可以使用哪些论据
3. 如何回应对方
4. 注意事项

建议要具体、实用、易于理解。
"""
        
        self._coze_context = context
        try:
            suggestion = await self._call_coze_bot(prompt)
        finally:
            self._coze_context = None
        return suggestion if suggestion else "继续保持，注意逻辑清晰。"
    
    async def analyze_weakness(
        self,
        topic: str,
        stance: str,
        student_speeches: List[str],
        opponent_speeches: List[str]
    ) -> Dict[str, str]:
        """
        分析学生的弱点
        
        Args:
            topic: 辩题
            stance: 立场
            student_speeches: 学生的发言列表
            opponent_speeches: 对方的发言列表
            
        Returns:
            分析结果（包含弱点和改进建议）
        """
        stance_text = "正方" if stance == "positive" else "反方"
        
        student_text = "\n".join([f"- {speech}" for speech in student_speeches])
        opponent_text = "\n".join([f"- {speech}" for speech in opponent_speeches])
        
        prompt = f"""
作为辩论教练，请分析{stance_text}学生在辩论中的表现：

辩题：{topic}

学生的发言：
{student_text}

对方的发言：
{opponent_text}

请分析：
1. 学生的主要弱点（逻辑、论据、表达等方面）
2. 对方的攻击点
3. 具体的改进建议

请简洁明了地给出分析（200字以内）。
"""
        
        analysis = await self._call_coze_bot(prompt)
        
        return {
            "analysis": analysis if analysis else "继续保持当前表现",
            "timestamp": ""
        }
    
    async def suggest_counter_argument(
        self,
        topic: str,
        stance: str,
        opponent_argument: str,
        context: List[Dict]
    ) -> str:
        """
        建议反驳论点
        
        Args:
            topic: 辩题
            stance: 立场
            opponent_argument: 对方论点
            context: 辩论上下文
            
        Returns:
            反驳建议
        """
        stance_text = "正方" if stance == "positive" else "反方"
        
        prompt = f"""
你是{stance_text}的辩论教练，对方刚刚提出了以下论点：

对方论点：{opponent_argument}

请建议如何反驳（80字以内）：
1. 指出对方论点的漏洞
2. 提供反驳的角度
3. 建议使用的论据

建议要具体、可操作。
"""
        
        self._coze_context = context
        try:
            suggestion = await self._call_coze_bot(prompt)
        finally:
            self._coze_context = None
        return suggestion if suggestion else "可以从逻辑和事实两方面进行反驳。"
    
    async def suggest_closing_points(
        self,
        topic: str,
        stance: str,
        key_arguments: List[str],
        debate_summary: str
    ) -> str:
        """
        建议总结要点
        
        Args:
            topic: 辩题
            stance: 立场
            key_arguments: 己方关键论点
            debate_summary: 辩论摘要
            
        Returns:
            总结建议
        """
        stance_text = "正方" if stance == "positive" else "反方"
        
        arguments_text = "\n".join([f"- {arg}" for arg in key_arguments])
        
        prompt = f"""
你是{stance_text}的辩论教练，现在是总结陈词环节。

辩题：{topic}

己方关键论点：
{arguments_text}

辩论情况：{debate_summary}

请建议总结陈词应该包含哪些要点（100字以内）：
1. 需要强调的核心论点
2. 辩论中的优势
3. 如何升华主题

建议要有感染力和说服力。
"""
        
        suggestion = await self._call_coze_bot(prompt)
        return suggestion if suggestion else "回顾核心论点，强调己方优势，升华主题。"
