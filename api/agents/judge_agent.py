"""
裁判AI Agent
负责实时评分、监控违规行为
"""
from logging_config import get_logger
from typing import List, Dict, Optional
import httpx
import json
from sqlalchemy.orm import Session

from services.config_service import ConfigService
from services.coze_client import CozeClient
from config import settings

logger = get_logger(__name__)


class ScoreBreakdown:
    """评分详情"""
    
    def __init__(
        self,
        logic_score: float = 0.0,
        argument_score: float = 0.0,
        response_score: float = 0.0,
        persuasion_score: float = 0.0,
        teamwork_score: float = 0.0,
        overall_score: float = 0.0,
        feedback: str = ""
    ):
        self.logic_score = logic_score
        self.argument_score = argument_score
        self.response_score = response_score
        self.persuasion_score = persuasion_score
        self.teamwork_score = teamwork_score
        self.overall_score = overall_score
        self.feedback = feedback
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "logic_score": self.logic_score,
            "argument_score": self.argument_score,
            "response_score": self.response_score,
            "persuasion_score": self.persuasion_score,
            "teamwork_score": self.teamwork_score,
            "overall_score": self.overall_score,
            "feedback": self.feedback
        }


class Violation:
    """违规行为"""
    
    def __init__(
        self,
        violation_type: str,
        description: str,
        penalty: float = 0.0
    ):
        self.violation_type = violation_type
        self.description = description
        self.penalty = penalty
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "violation_type": self.violation_type,
            "description": self.description,
            "penalty": self.penalty
        }


class JudgeAgent:
    """裁判AI Agent"""
    
    def __init__(self, db: Session):
        """
        初始化裁判AI
        
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
            
            if not coze_config or not coze_config.judge_bot_id:
                raise ValueError("裁判AI Bot ID未配置")
            
            self.bot_id = coze_config.judge_bot_id
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
                raise ValueError("裁判AI Bot ID未配置")
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
                user_id="judge_ai",
                raw_messages=raw_messages,
            )
            reply_message = await coze.chat_coze_message_async(
                bot_id=params["bot_id"],
                user_id=params["user_id"],
                messages=params["messages"],
            )
            return (reply_message.content or "").strip()
        
        except Exception as e:
            logger.error(f"调用裁判AI失败: {e}", exc_info=True)
            return ""

    async def _call_llm(self, prompt: str) -> str:
        try:
            config_service = ConfigService(self.db)
            model_config = await config_service.get_model_config()
            api_key = (model_config.api_key or "").strip() or (settings.OPENAI_API_KEY or "").strip()
            if not api_key:
                return ""
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

            messages = [
                {
                    "role": "system",
                    "content": "你是辩论裁判。严格按用户要求输出JSON，不要输出额外文本、不要代码块。",
                },
                {"role": "user", "content": prompt},
            ]
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": int(getattr(model_config, "max_tokens", 2000) or 2000),
            }
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            if response.status_code != 200:
                return ""
            data = response.json()
            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        except Exception as e:
            logger.error(f"调用LLM裁判失败: {e}", exc_info=True)
            return ""

    async def _call_agent(self, prompt: str) -> str:
        provider = (settings.DEBATE_AI_PROVIDER or "llm").strip().lower()
        if provider == "coze":
            reply = await self._call_coze_bot(prompt)
            if reply:
                return reply
            return await self._call_llm(prompt)
        return await self._call_llm(prompt)
    
    async def score_speech(
        self,
        speech_content: str,
        speaker_role: str,
        phase: str,
        context: List[Dict]
    ) -> ScoreBreakdown:
        """
        评分发言
        
        Args:
            speech_content: 发言内容
            speaker_role: 发言者角色
            phase: 辩论环节
            context: 辩论上下文
            
        Returns:
            评分详情
        """
        prompt = f"""
作为辩论裁判，请对以下发言进行评分：

发言者角色：{speaker_role}
辩论环节：{phase}
发言内容：{speech_content}

请从以下五个维度进行评分（每项0-100分）：
1. 逻辑建构力（logic_score）：论证结构是否严密、推理链条是否完整合理
2. AI核心知识运用（argument_score）：是否准确运用AI相关概念与术语（如情感计算、NLP、AIGC等），知识调用是否恰当
3. 批判性思维（response_score）：能否有效识别对方逻辑漏洞，提出有深度的质疑与反驳
4. 语言表达力（persuasion_score）：表达是否清晰流畅，语言是否有感染力和说服力
5. AI伦理与科技素养（teamwork_score）：是否体现对AI伦理议题的深度思考，是否展现科技人文关怀

注意：在feedback评语中，请至少引用一个与辩题相关的AI课程术语
（如：情感计算、自然语言处理、AIGC、人机交互、图灵测试、AI伦理等），
并结合辩手的实际发言进行具体点评。

请以JSON格式返回评分结果：
{{
    "logic_score": 85,
    "argument_score": 80,
    "response_score": 90,
    "persuasion_score": 75,
    "teamwork_score": 85,
    "overall_score": 83,
    "feedback": "简短的评价（50字以内）"
}}
"""
        
        try:
            self._coze_context = context
            try:
                reply = await self._call_agent(prompt)
            finally:
                self._coze_context = None
            
            # 尝试解析JSON
            # 提取JSON部分（可能包含在markdown代码块中）
            if "```json" in reply:
                json_str = reply.split("```json")[1].split("```")[0].strip()
            elif "```" in reply:
                json_str = reply.split("```")[1].split("```")[0].strip()
            else:
                json_str = reply.strip()
            
            data = json.loads(json_str)
            
            return ScoreBreakdown(
                logic_score=float(data.get("logic_score", 70)),
                argument_score=float(data.get("argument_score", 70)),
                response_score=float(data.get("response_score", 70)),
                persuasion_score=float(data.get("persuasion_score", 70)),
                teamwork_score=float(data.get("teamwork_score", 70)),
                overall_score=float(data.get("overall_score", 70)),
                feedback=data.get("feedback", "")
            )
        
        except Exception as e:
            logger.error(f"解析评分结果失败: {e}", exc_info=True)
            # 返回默认评分
            return ScoreBreakdown(
                logic_score=70.0,
                argument_score=70.0,
                response_score=70.0,
                persuasion_score=70.0,
                teamwork_score=70.0,
                overall_score=70.0,
                feedback="评分系统暂时不可用"
            )
    
    async def check_violations(
        self,
        speech_content: str,
        speaker_role: str
    ) -> List[Violation]:
        """
        检查违规行为
        
        Args:
            speech_content: 发言内容
            speaker_role: 发言者角色
            
        Returns:
            违规行为列表
        """
        prompt = f"""
作为辩论裁判，请检查以下发言是否存在违规行为：

发言者：{speaker_role}
发言内容：{speech_content}

需要检查的违规类型：
1. 人身攻击：针对对方个人而非观点的攻击
2. 性别歧视：含有性别歧视的言论
3. 不当言论：粗俗、侮辱性语言
4. 偏离主题：严重偏离辩题
5. 恶意打断：频繁打断对方发言

如果发现违规，请以JSON格式返回：
{{
    "violations": [
        {{
            "violation_type": "人身攻击",
            "description": "具体描述",
            "penalty": 10
        }}
    ]
}}

如果没有违规，返回：
{{
    "violations": []
}}
"""
        
        try:
            reply = await self._call_agent(prompt)
            
            # 提取JSON部分
            if "```json" in reply:
                json_str = reply.split("```json")[1].split("```")[0].strip()
            elif "```" in reply:
                json_str = reply.split("```")[1].split("```")[0].strip()
            else:
                json_str = reply.strip()
            
            data = json.loads(json_str)
            violations = []
            
            for v in data.get("violations", []):
                violations.append(Violation(
                    violation_type=v.get("violation_type", "未知"),
                    description=v.get("description", ""),
                    penalty=float(v.get("penalty", 0))
                ))
            
            return violations
        
        except Exception as e:
            logger.error(f"检查违规失败: {e}", exc_info=True)
            return []
    
    def calculate_final_score(
        self,
        all_scores: List[ScoreBreakdown],
        violations: List[Violation]
    ) -> float:
        """
        计算最终得分
        
        Args:
            all_scores: 所有评分列表
            violations: 违规行为列表
            
        Returns:
            最终得分
        """
        if not all_scores:
            return 0.0
        
        # 计算平均分
        total_score = sum(score.overall_score for score in all_scores)
        avg_score = total_score / len(all_scores)
        
        # 扣除违规分数
        penalty = sum(v.penalty for v in violations)
        final_score = max(0, avg_score - penalty)
        
        return round(final_score, 2)
    
    async def generate_feedback(
        self,
        speech_content: str,
        score: ScoreBreakdown,
        violations: List[Violation]
    ) -> str:
        """
        生成反馈意见
        
        Args:
            speech_content: 发言内容
            score: 评分详情
            violations: 违规行为列表
            
        Returns:
            反馈意见
        """
        violation_text = ""
        if violations:
            violation_text = "\n违规行为：\n" + "\n".join([
                f"- {v.violation_type}: {v.description}"
                for v in violations
            ])
        
        prompt = f"""
作为辩论裁判，请对以下发言给出建设性的反馈意见：

发言内容：{speech_content}

评分情况：
- 逻辑建构力：{score.logic_score}分
- AI核心知识运用：{score.argument_score}分
- 批判性思维：{score.response_score}分
- 语言表达力：{score.persuasion_score}分
- AI伦理与科技素养：{score.teamwork_score}分
- 总分：{score.overall_score}分
{violation_text}

请给出简短的反馈意见（100字以内），包括：
1. 优点
2. 需要改进的地方
3. 具体建议
4. 至少引用一个与辩题相关的AI课程术语，并结合辩手实际发言进行点评
"""
        
        feedback = await self._call_agent(prompt)
        return feedback if feedback else score.feedback

    async def batch_evaluate_debate(self, context: List[Dict]) -> Dict:
        """
        批量评分整场辩论（包含每条发言的评分和全场报告）
        
        Args:
            context: 辩论上下文（包含speech_id, content等）
            
        Returns:
            包含speech_scores和global_report的字典
        """
        # Format context for prompt
        transcript = ""
        for msg in context:
            speech_id = msg.get("speech_id", "unknown")
            role = msg.get("speaker_role", "Unknown")
            content = msg.get("content", "")
            phase = msg.get("phase", "")
            transcript += f"Speech ID: {speech_id}\nRole: {role}\nPhase: {phase}\nContent: {content}\n\n"
            
        prompt = f"""
作为专业辩论裁判，请对整场辩论进行批量评分和综合复盘。

以下是辩论实录（包含每条发言的ID）：
{transcript}

请对每条发言按以下五个维度评分，并确保返回JSON中的字段与这些维度严格对应：
1. logic_score = 逻辑建构力：论证结构是否严密、推理链条是否完整合理
2. argument_score = AI核心知识运用：是否准确运用AI相关概念与术语（如情感计算、NLP、AIGC等），知识调用是否恰当
3. response_score = 批判性思维：能否有效识别对方逻辑漏洞，提出有深度的质疑与反驳
4. persuasion_score = 语言表达力：表达是否清晰流畅，语言是否有感染力和说服力
5. teamwork_score = AI伦理与科技素养：是否体现对AI伦理议题的深度思考，是否展现科技人文关怀

注意：
1. 每条 speech_scores[*].scores.feedback 都必须至少引用一个与辩题相关的AI课程术语
（如：情感计算、自然语言处理、AIGC、人机交互、图灵测试、AI伦理等），并结合该辩手实际发言进行具体点评。
2. global_report.scores 中各字段含义固定为：
   - logical_thinking = 逻辑建构力
   - argument_quality = AI核心知识运用
   - reaction_speed = 批判性思维
   - persuasion = 语言表达力
   - teamwork = AI伦理与科技素养

请严格按照以下JSON格式返回结果，不要输出任何其他内容：
{{
    "speech_scores": [
        {{
            "speech_id": "发言ID",
            "scores": {{
                "logic_score": 85,
                "argument_score": 80,
                "response_score": 90,
                "persuasion_score": 75,
                "teamwork_score": 85,
                "overall_score": 83,
                "feedback": "简短评价（50字以内）"
            }},
            "violations": [
                {{
                    "violation_type": "违规类型（如无则为空）",
                    "description": "描述",
                    "penalty": 0
                }}
            ]
        }}
    ],
    "global_report": {{
        "winner": "positive/negative/draw",
        "winning_reason": "获胜理由",
        "scores": {{
            "positive": {{
                "logical_thinking": 85,
                "argument_quality": 88,
                "reaction_speed": 80,
                "persuasion": 82,
                "teamwork": 90,
                "total_score": 85
            }},
            "negative": {{
                "logical_thinking": 80,
                "argument_quality": 85,
                "reaction_speed": 85,
                "persuasion": 78,
                "teamwork": 82,
                "total_score": 82
            }}
        }},
        "overall_comment": "整体点评",
        "suggestions": "建议"
    }}
}}
"""
        try:
            self._coze_context = context
            try:
                reply = await self._call_agent(prompt)
            finally:
                self._coze_context = None

            # JSON extraction logic
            if "```json" in reply:
                json_str = reply.split("```json")[1].split("```")[0].strip()
            elif "```" in reply:
                json_str = reply.split("```")[1].split("```")[0].strip()
            else:
                json_str = reply.strip()
                
            return json.loads(json_str)
            
        except Exception as e:
            logger.error(f"批量评分失败: {e}", exc_info=True)
            return {
                "speech_scores": [],
                "global_report": {
                    "winner": "draw",
                    "winning_reason": "评分系统暂时不可用",
                    "scores": {
                        "positive": {"total_score": 0},
                        "negative": {"total_score": 0}
                    }
                }
            }


