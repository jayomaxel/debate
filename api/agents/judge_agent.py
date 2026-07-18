"""
裁判AI Agent
负责实时评分、监控违规行为
"""
from logging_config import get_logger
from typing import Any, List, Dict, Optional
import httpx
import json
from sqlalchemy.orm import Session

from services.config_service import ConfigService
from services.coze_client import CozeClient
from services.prompt_pack_service import PromptBuildContext, PromptPackService
from services.score_validation_service import ScoreValidationService
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
        feedback: str = "",
        report_meta: Optional[Dict] = None
    ):
        self.logic_score = logic_score
        self.argument_score = argument_score
        self.response_score = response_score
        self.persuasion_score = persuasion_score
        self.teamwork_score = teamwork_score
        self.overall_score = overall_score
        self.feedback = feedback
        self.report_meta = dict(report_meta or {})
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "logic_score": self.logic_score,
            "argument_score": self.argument_score,
            "response_score": self.response_score,
            "persuasion_score": self.persuasion_score,
            "teamwork_score": self.teamwork_score,
            "overall_score": self.overall_score,
            "feedback": self.feedback,
            "report_meta": dict(self.report_meta),
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
                    "content": PromptPackService.render_agent_system_prompt("judge"),
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

    @staticmethod
    def _provider_name() -> str:
        provider = (settings.DEBATE_AI_PROVIDER or "llm").strip().lower()
        return "coze" if provider == "coze" else "llm"

    @staticmethod
    def _topic_from_context(context: List[Dict]) -> str:
        for item in reversed(list(context or [])):
            if isinstance(item, dict) and item.get("topic"):
                return str(item.get("topic") or "")
        return ""

    def _build_score_prompt(
        self,
        prompt: str,
        speaker_role: str,
        phase: str,
        context: List[Dict],
        *,
        task_type: str = "speech_score",
        task_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        mode = PromptPackService.resolve_mode_from_context(context)
        build_context = PromptBuildContext(
            agent="judge",
            mode=mode,
            phase=phase,
            topic=self._topic_from_context(context),
            role="judge",
            speaker_role=speaker_role or "judge",
            stance="neutral",
            history=list(context or []),
            output_contract=ScoreValidationService.expected_speech_score_contract(),
        )
        if task_data is not None:
            return PromptPackService.render_agent_task_prompt(
                build_context,
                task_type=task_type,
                task_data=task_data,
            )
        return PromptPackService.render_agent_prompt(build_context, task_prompt=prompt)

    @staticmethod
    def _batch_output_contract() -> Dict[str, Any]:
        return {
            "speech_scores": [
                {
                    "speech_id": "string",
                    "scores": ScoreValidationService.expected_speech_score_contract(),
                    "violations": [
                        {
                            "violation_type": "string",
                            "description": "string",
                            "penalty": "number",
                        }
                    ],
                }
            ],
            "global_report": {
                "winner": "positive | negative | draw",
                "winning_reason": "string",
                "scores": {
                    "positive": "team score object",
                    "negative": "team score object",
                },
                "overall_comment": "string",
                "suggestions": "string | list",
            },
            "report_meta": "ReportMeta object",
        }

    def _build_batch_prompt(
        self,
        prompt: str,
        context: List[Dict],
        output_contract: Dict[str, Any],
        *,
        task_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        mode = PromptPackService.resolve_mode_from_context(context)
        build_context = PromptBuildContext(
            agent="judge",
            mode=mode,
            phase="report",
            topic=self._topic_from_context(context),
            role="judge",
            speaker_role="judge",
            stance="neutral",
            history=list(context or []),
            output_contract=output_contract,
        )
        if task_data is not None:
            return PromptPackService.render_agent_task_prompt(
                build_context,
                task_type="batch_debate_evaluation",
                task_data=task_data,
            )
        return PromptPackService.render_agent_prompt(build_context, task_prompt=prompt)

    async def _call_batch_with_validation(
        self,
        prompt: str,
        context: List[Dict],
        *,
        mode: str,
        provider: str,
        output_contract: Dict[str, Any],
    ) -> Dict[str, Any]:
        self._coze_context = context
        try:
            reply = await self._call_agent(prompt)
        finally:
            self._coze_context = None

        try:
            data = ScoreValidationService.extract_json(reply)
            return self._normalize_batch_result(
                data,
                context,
                mode=mode,
                provider=provider,
                scoring_quality="validated",
                retry_count=0,
            )
        except Exception as exc:
            first_error = exc
            repair_prompt = ScoreValidationService.build_repair_prompt(
                reply,
                expected_contract=output_contract,
            )

        self._coze_context = context
        try:
            repaired_reply = await self._call_agent(repair_prompt)
        finally:
            self._coze_context = None

        try:
            data = ScoreValidationService.extract_json(repaired_reply)
            return self._normalize_batch_result(
                data,
                context,
                mode=mode,
                provider=provider,
                scoring_quality="repaired",
                retry_count=1,
            )
        except Exception as repair_error:
            logger.error(
                "Batch judge output repair failed: %s; first error: %s",
                repair_error,
                first_error,
                exc_info=True,
            )
            return self._build_batch_fallback_report(
                context,
                reason="Judge model unavailable or returned invalid JSON.",
                mode=mode,
                provider=provider,
                retry_count=1,
            )

    def _normalize_batch_result(
        self,
        data: Dict[str, Any],
        context: List[Dict],
        *,
        mode: str,
        provider: str,
        scoring_quality: str,
        retry_count: int,
    ) -> Dict[str, Any]:
        speech_scores = data.get("speech_scores")
        global_report = data.get("global_report")
        if not isinstance(speech_scores, list) or not isinstance(global_report, dict):
            raise ValueError("batch judge JSON missing speech_scores or global_report")

        normalized_scores = []
        expected_speech_ids = {
            str(item.get("speech_id") or "").strip()
            for item in context
            if isinstance(item, dict)
            and str(item.get("speech_id") or "").strip()
            and str(item.get("content") or "").strip()
        }
        seen_speech_ids = set()
        partial = False
        for item in speech_scores:
            if not isinstance(item, dict):
                partial = True
                continue
            speech_id = str(item.get("speech_id") or "").strip()
            if (
                not speech_id
                or speech_id not in expected_speech_ids
                or speech_id in seen_speech_ids
            ):
                partial = True
                continue
            seen_speech_ids.add(speech_id)
            scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}
            validation = ScoreValidationService.validate_speech_score(scores)
            if validation.errors:
                partial = True
                normalized_score = ScoreValidationService.build_fallback_score(
                    "partial batch score could not be validated"
                )
                score_meta = ScoreValidationService.build_report_meta(
                    scoring_source="fallback",
                    scoring_quality="fallback",
                    provider=provider,
                    mode=mode,
                    retry_count=retry_count,
                ).to_dict()
            else:
                normalized_score = validation.payload
                score_meta = ScoreValidationService.build_report_meta(
                    scoring_source="judge_model",
                    scoring_quality=scoring_quality,
                    provider=provider,
                    mode=mode,
                    retry_count=retry_count,
                ).to_dict()
            normalized_score["report_meta"] = score_meta
            violations = item.get("violations") if isinstance(item.get("violations"), list) else []
            normalized_scores.append(
                {
                    "speech_id": speech_id,
                    "scores": normalized_score,
                    "violations": violations,
                }
            )

        missing_speech_ids = expected_speech_ids - seen_speech_ids
        if missing_speech_ids:
            partial = True
            fallback_meta = ScoreValidationService.build_report_meta(
                scoring_source="fallback",
                scoring_quality="fallback",
                provider=provider,
                mode=mode,
                retry_count=retry_count,
            ).to_dict()
            for missing_speech_id in sorted(missing_speech_ids):
                normalized_scores.append(
                    {
                        "speech_id": missing_speech_id,
                        "scores": {
                            **ScoreValidationService.build_fallback_score(
                                "judge batch output omitted this speech"
                            ),
                            "report_meta": fallback_meta,
                        },
                        "violations": [],
                    }
                )

        report_quality = "partial" if partial else scoring_quality
        report_meta = ScoreValidationService.build_report_meta(
            scoring_source="judge_model",
            scoring_quality=report_quality,
            provider=provider,
            mode=mode,
            retry_count=retry_count,
        ).to_dict()
        global_report["report_meta"] = report_meta

        result = {
            "speech_scores": normalized_scores,
            "global_report": global_report,
            "report_meta": report_meta,
        }
        samples = ScoreValidationService.collect_anomaly_samples(
            {
                "report_meta": report_meta,
                "evidence_anchors": data.get("evidence_anchors", []),
                "participant_scores": [
                    item.get("scores", {}) for item in normalized_scores
                ],
            }
        )
        result["anomaly_samples"] = samples
        result["calibration_summary"] = ScoreValidationService.build_calibration_summary(samples)
        return result

    def _build_batch_fallback_report(
        self,
        context: List[Dict],
        *,
        reason: str,
        mode: str,
        provider: str,
        retry_count: int,
    ) -> Dict[str, Any]:
        speech_scores = []
        side_counts = {"positive": 0, "negative": 0}
        report_meta = ScoreValidationService.build_report_meta(
            scoring_source="fallback",
            scoring_quality="fallback",
            provider=provider,
            mode=mode,
            retry_count=retry_count,
        ).to_dict()

        for msg in context:
            speech_id = str(msg.get("speech_id") or "").strip()
            content = str(msg.get("content") or "").strip()
            role = str(msg.get("speaker_role") or "").strip()
            if not speech_id or not content:
                continue
            length_bonus = min(10, max(0, len(content) // 80))
            base = min(88, 68 + length_bonus)
            scores = {
                **ScoreValidationService.build_fallback_score(reason),
                "logic_score": base + 2,
                "argument_score": base + 1,
                "response_score": base,
                "persuasion_score": base + 1,
                "teamwork_score": base,
                "overall_score": base + 1,
                "report_meta": report_meta,
            }
            speech_scores.append(
                {"speech_id": speech_id, "scores": scores, "violations": []}
            )
            side = "negative" if role.startswith("ai_") else "positive"
            side_counts[side] += 1

        if side_counts["positive"] > side_counts["negative"]:
            winner = "positive"
        elif side_counts["negative"] > side_counts["positive"]:
            winner = "negative"
        else:
            winner = "draw"

        side_scores = {
            "logical_thinking": 72,
            "argument_quality": 72,
            "reaction_speed": 70,
            "persuasion": 72,
            "teamwork": 72,
            "total_score": 72,
        }
        result = {
            "speech_scores": speech_scores,
            "global_report": {
                "winner": winner,
                "winning_reason": reason,
                "scores": {
                    "positive": dict(side_scores),
                    "negative": dict(side_scores),
                },
                "overall_comment": "Report generated with deterministic fallback scoring because the judge model did not return valid JSON.",
                "suggestions": "Review the transcript and judge model configuration if detailed AI comments are required.",
                "report_meta": report_meta,
            },
            "report_meta": report_meta,
        }
        samples = ScoreValidationService.collect_anomaly_samples(
            {
                "report_meta": report_meta,
                "evidence_anchors": [],
                "participant_scores": [item["scores"] for item in speech_scores],
            }
        )
        result["anomaly_samples"] = samples
        result["calibration_summary"] = ScoreValidationService.build_calibration_summary(samples)
        return result
    
    async def score_speech(
        self,
        speech_content: str,
        speaker_role: str,
        phase: str,
        context: List[Dict]
    ) -> ScoreBreakdown:
        """Score a speech through Prompt Pack and validated Judge JSON."""
        mode = PromptPackService.resolve_mode_from_context(context)
        provider = self._provider_name()
        prompt = self._build_score_prompt(
            "",
            speaker_role,
            phase,
            context,
            task_type="speech_score",
            task_data={
                "speaker_role": speaker_role,
                "phase": phase,
                "speech_content": speech_content,
                "rubric_dimensions": list(ScoreValidationService.SCORE_FIELDS),
                "requirements": [
                    "score each dimension from 0 to 100",
                    "return JSON only",
                    "include concise feedback grounded in the speech",
                ],
            },
        )

        try:
            self._coze_context = context
            try:
                reply = await self._call_agent(prompt)
                validation = ScoreValidationService.validate_or_fallback(
                    reply,
                    mode=mode,
                    provider=provider,
                )
                if validation.scoring_quality == "fallback" and validation.repair_prompt:
                    repaired_reply = await self._call_agent(validation.repair_prompt)
                    validation = ScoreValidationService.validate_or_fallback(
                        reply,
                        repaired_text=repaired_reply,
                        mode=mode,
                        provider=provider,
                    )
            finally:
                self._coze_context = None
            data = validation.payload
            return ScoreBreakdown(
                logic_score=float(data.get("logic_score", 70)),
                argument_score=float(data.get("argument_score", 70)),
                response_score=float(data.get("response_score", 70)),
                persuasion_score=float(data.get("persuasion_score", 70)),
                teamwork_score=float(data.get("teamwork_score", 70)),
                overall_score=float(data.get("overall_score", 70)),
                feedback=data.get("feedback", ""),
                report_meta=validation.report_meta.to_dict(),
            )
        except Exception as e:
            logger.error(f"Failed to parse judge scoring result: {e}", exc_info=True)
            fallback = ScoreValidationService.validate_or_fallback(
                "",
                repaired_text="",
                mode=mode,
                provider=provider,
                fallback_reason=str(e) or "Judge scoring failed.",
            )
            data = fallback.payload
            return ScoreBreakdown(
                logic_score=float(data.get("logic_score", 60)),
                argument_score=float(data.get("argument_score", 60)),
                response_score=float(data.get("response_score", 60)),
                persuasion_score=float(data.get("persuasion_score", 60)),
                teamwork_score=float(data.get("teamwork_score", 60)),
                overall_score=float(data.get("overall_score", 60)),
                feedback=data.get("feedback", ""),
                report_meta=fallback.report_meta.to_dict(),
            )
    
    async def check_violations(
        self,
        speech_content: str,
        speaker_role: str
    ) -> List[Violation]:
        """Check violations through Prompt Pack."""
        prompt = PromptPackService.render_agent_task_prompt(
            PromptBuildContext(
                agent="judge",
                phase="free_debate",
                topic="",
                role="judge",
                speaker_role=speaker_role or "judge",
                stance="neutral",
                output_contract={"violations": []},
            ),
            task_type="violation_check",
            task_data={
                "speaker_role": speaker_role,
                "speech_content": speech_content,
                "violation_types": [
                    "personal_attack",
                    "discrimination",
                    "inappropriate_language",
                    "off_topic",
                    "malicious_interruption",
                ],
                "requirements": ["return JSON only", "return an empty violations list when no violation exists"],
            },
        )
        try:
            reply = await self._call_agent(prompt)
            if "```json" in reply:
                json_str = reply.split("```json")[1].split("```")[0].strip()
            elif "```" in reply:
                json_str = reply.split("```")[1].split("```")[0].strip()
            else:
                json_str = reply.strip()
            data = json.loads(json_str)
            violations = []
            for item in data.get("violations", []):
                violations.append(Violation(
                    violation_type=item.get("violation_type", "unknown"),
                    description=item.get("description", ""),
                    penalty=float(item.get("penalty", 0)),
                ))
            return violations
        except Exception as e:
            logger.error(f"Failed to check violations: {e}", exc_info=True)
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
        """Generate judge feedback through Prompt Pack."""
        prompt = PromptPackService.render_agent_task_prompt(
            PromptBuildContext(
                agent="judge",
                phase="report",
                topic="",
                role="judge",
                speaker_role="judge",
                stance="neutral",
                output_contract={"feedback": "string"},
            ),
            task_type="speech_feedback",
            task_data={
                "speech_content": speech_content,
                "scores": score.to_dict(),
                "violations": [violation.to_dict() for violation in violations],
                "requirements": [
                    "summarize strengths",
                    "identify concrete improvement points",
                    "keep the feedback concise",
                ],
                "max_chars": 200,
            },
        )
        feedback = await self._call_agent(prompt)
        return feedback if feedback else score.feedback

    async def batch_evaluate_debate(self, context: List[Dict]) -> Dict:
        """Batch-score a full debate through Prompt Pack."""
        transcript = []
        for msg in context:
            transcript.append(
                {
                    "speech_id": msg.get("speech_id", "unknown"),
                    "speaker_role": msg.get("speaker_role", "Unknown"),
                    "phase": msg.get("phase", ""),
                    "content": msg.get("content", ""),
                }
            )
        mode = PromptPackService.resolve_mode_from_context(context)
        provider = self._provider_name()
        output_contract = self._batch_output_contract()
        prompt = self._build_batch_prompt(
            "",
            context,
            output_contract,
            task_data={
                "transcript": transcript,
                "requirements": [
                    "score every speech by speech_id",
                    "return JSON only",
                    "preserve global_report field names",
                    "include report_meta compatible quality fields",
                ],
                "output_contract": output_contract,
            },
        )

        try:
            return await self._call_batch_with_validation(
                prompt,
                context,
                mode=mode,
                provider=provider,
                output_contract=output_contract,
            )
        except Exception as e:
            logger.error(f"Batch debate evaluation failed: {e}", exc_info=True)
            return self._build_batch_fallback_report(
                context,
                reason="Judge model unavailable or returned invalid JSON.",
                mode=mode,
                provider=provider,
                retry_count=1,
            )
