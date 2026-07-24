"""
评分服务
负责通过裁判模型完成语义评分、违规检测与最终得分计算。

评分的主链路必须由裁判模型根据完整辩论语境判断；当模型不可用或
输出无法修复时，只能产出带有明确降级标记的兜底结果，不能用关键词
或发言长度等确定性规则伪装成正常评分。
"""
import asyncio
import uuid

from logging_config import get_logger
from typing import Any, List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime

from models.speech import Speech
from models.score import Score
from models.debate import Debate, DebateParticipation
from agents.judge_agent import JudgeAgent, Violation
from services.domain_pack_service import DEFAULT_DOMAIN_PACK_ID
from services.mode_policy_service import ModePolicyService
from services.prompt_pack_service import PromptPackService
from services.rubric_service import RubricService
from services.score_validation_service import ScoreValidationService

logger = get_logger(__name__)


class ScoringService:
    """评分服务"""

    # Report reads and the end-of-debate background task can arrive together.
    # Serialise judge runs per debate in this API process so they cannot charge
    # twice or race while creating scores/participations.
    _debate_scoring_locks: Dict[str, asyncio.Lock] = {}
    @staticmethod
    def _uuid_value(value: Any) -> Any:
        if value is None or isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            return value
    
    @staticmethod
    def _speech_stance(speaker_type: str) -> str:
        # Product rule: human is always affirmative, AI is always negative.
        return "positive" if str(speaker_type) == "human" else "negative"

    @staticmethod
    def _normalize_speaker_role(speaker_role: Optional[str]) -> str:
        role = str(speaker_role or "").strip()
        if role.startswith("ai_"):
            parts = role.split("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                return f"debater_{parts[1]}"
        if role.startswith("debater_"):
            return role
        return "debater_1"

    @staticmethod
    def _build_a_report_contract_patch(
        *,
        topic: str,
        speech_score_items: List[Dict],
        speech_map: Dict[str, Speech],
        context: List[Dict],
        existing_report: Optional[Dict] = None,
        scoring_meta: Optional[Dict[str, Any]] = None,
        calibration_summary: Optional[Dict[str, Any]] = None,
        anomaly_samples: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        existing_report = existing_report if isinstance(existing_report, dict) else {}
        mode = PromptPackService.resolve_mode_from_context(
            context,
            mode=existing_report.get("mode"),
        )
        domain_pack_id = str(existing_report.get("domain_pack_id") or DEFAULT_DOMAIN_PACK_ID)
        report_meta = ScoreValidationService.build_report_meta(mode=mode).to_dict()
        if isinstance(scoring_meta, dict):
            report_meta.update(scoring_meta)
        report_meta["mode"] = ModePolicyService.normalize_mode(
            report_meta.get("mode") or mode
        )

        anchors: List[Dict[str, Any]] = []
        turning_candidates: List[Dict[str, Any]] = []
        role_buckets: Dict[str, Dict[str, Any]] = {}
        team_scores: Dict[str, List[float]] = {"positive": [], "negative": []}
        team_speech_count: Dict[str, int] = {"positive": 0, "negative": 0}

        for index, item in enumerate(speech_score_items, start=1):
            speech_id = str(item.get("speech_id") or "").strip()
            speech = speech_map.get(speech_id)
            scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}
            if not speech or not scores:
                continue

            content = str(getattr(speech, "content", "") or "").strip()
            speaker_role = ScoringService._normalize_speaker_role(
                getattr(speech, "speaker_role", "")
            )
            stance = ScoringService._speech_stance(str(getattr(speech, "speaker_type", "")))
            try:
                overall_score = float(scores.get("overall_score") or 0.0)
            except (TypeError, ValueError):
                overall_score = 0.0

            if content:
                anchors.append(
                    {
                        "anchor_id": f"anchor_{index}",
                        "anchor_type": "turn",
                        "turn_id": speech_id,
                        "speaker_role": speaker_role,
                        "excerpt": content[:180],
                        "source_document_id": "",
                        "source_location": f"speech:{speech_id}",
                        "evidence_source": "debate_speech",
                        "source_type": "debate_speech",
                        "source_kind": "speech_turn",
                        "source_label": "Debate speech transcript",
                        "evidence_relation": "support",
                    }
                )

            turning_candidates.append(
                {
                    "turn_id": speech_id,
                    "speaker_role": speaker_role,
                    "summary": "highest impact turn by current scoring data",
                    "impact": f"overall_score={overall_score}",
                    "_score": overall_score,
                }
            )

            bucket = role_buckets.setdefault(
                speaker_role,
                {
                    "speaker_role": speaker_role,
                    "stance": stance,
                    "speech_count": 0,
                    "scores": {
                        "logic_score": [],
                        "argument_score": [],
                        "response_score": [],
                        "persuasion_score": [],
                        "teamwork_score": [],
                        "overall_score": [],
                    },
                },
            )
            bucket["speech_count"] += 1
            for field in bucket["scores"]:
                try:
                    bucket["scores"][field].append(float(scores.get(field) or 0.0))
                except (TypeError, ValueError):
                    bucket["scores"][field].append(0.0)

            if stance in team_scores:
                team_scores[stance].append(overall_score)
                team_speech_count[stance] += 1

        participant_scores: List[Dict[str, Any]] = []
        for role, bucket in role_buckets.items():
            averaged_scores = {
                field: round(sum(values) / len(values), 2) if values else 0.0
                for field, values in bucket["scores"].items()
            }
            participant_score = RubricService.build_participant_score(
                role,
                averaged_scores,
                mode=mode,
            )
            participant_score.update(
                {
                    "stance": bucket["stance"],
                    "speech_count": bucket["speech_count"],
                    "score_status": "ready",
                }
            )
            participant_scores.append(participant_score)

        turning_points: List[Dict[str, Any]] = []
        if turning_candidates:
            best_turn = max(turning_candidates, key=lambda item: item["_score"])
            best_turn.pop("_score", None)
            turning_points.append(best_turn)

        improvement_actions = []
        for item in participant_scores:
            if float(item.get("overall_score") or 0.0) < 65:
                improvement_actions.append(
                    {
                        "speaker_role": item.get("speaker_role"),
                        "action": "strengthen claim-evidence-warrant links in the next review",
                        "priority": "medium",
                    }
                )

        def _team_average(stance: str) -> float:
            values = team_scores.get(stance, [])
            return round(sum(values) / len(values), 2) if values else 0.0

        team_participant_count = {"positive": 0, "negative": 0}
        for item in participant_scores:
            stance = str(item.get("stance") or "")
            if stance in team_participant_count:
                team_participant_count[stance] += 1

        team_summary = {
            "positive": {
                "participant_count": team_participant_count["positive"],
                "speech_count": team_speech_count["positive"],
                "average_score": _team_average("positive"),
            },
            "negative": {
                "participant_count": team_participant_count["negative"],
                "speech_count": team_speech_count["negative"],
                "average_score": _team_average("negative"),
            },
        }

        report_patch = {
            "mode": ModePolicyService.normalize_mode(mode),
            "domain_pack_id": domain_pack_id,
            "report_meta": report_meta,
            "score_generation_mode": "semantic_judge",
            "score_fallback_generated": report_meta.get("scoring_source") == "fallback"
            or report_meta.get("scoring_quality") in {"fallback", "partial"},
            "turning_points": turning_points,
            "evidence_anchors": anchors,
            "improvement_actions": improvement_actions,
            "participant_scores": participant_scores,
            "team_summary": team_summary,
            "teaching_summary": {
                "learning_objectives": [],
                "common_issues": [],
                "improvement_actions": improvement_actions,
            }
            if mode == "teaching"
            else {},
        }
        samples = (
            list(anomaly_samples)
            if isinstance(anomaly_samples, list)
            else ScoreValidationService.collect_anomaly_samples(report_patch)
        )
        report_patch["anomaly_samples"] = samples
        report_patch["calibration_summary"] = (
            dict(calibration_summary)
            if isinstance(calibration_summary, dict)
            else ScoreValidationService.build_calibration_summary(samples)
        )
        return report_patch

    @staticmethod
    async def score_speech(
        db: Session,
        speech_id: str,
        participation_id: str,
        speech_content: str,
        speaker_role: str,
        phase: str,
        context: List[Dict]
    ) -> Score:
        """
        评分发言
        
        Args:
            db: 数据库会话
            speech_id: 发言ID
            participation_id: 参与ID
            speech_content: 发言内容
            speaker_role: 发言者角色
            phase: 辩论环节
            context: 辩论上下文
            
        Returns:
            评分记录
        """
        try:
            speech_uuid = ScoringService._uuid_value(speech_id)
            participation_uuid = ScoringService._uuid_value(participation_id)
            # 调用裁判AI进行评分
            judge = JudgeAgent(db)
            score_breakdown = await judge.score_speech(
                speech_content=speech_content,
                speaker_role=speaker_role,
                phase=phase,
                context=context
            )
            
            # 检查违规行为
            violations = await judge.check_violations(
                speech_content=speech_content,
                speaker_role=speaker_role
            )
            
            # 计算违规扣分
            violation_penalty = sum(v.penalty for v in violations)
            
            # 语义评分是唯一的基础分；违规处罚是唯一允许的规则性调整。
            base_score = score_breakdown.overall_score
            final_score = max(0, min(100, base_score - violation_penalty))
            
            # 生成反馈
            feedback = await judge.generate_feedback(
                speech_content=speech_content,
                score=score_breakdown,
                violations=violations
            )
            
            # 只披露可审计的违规处罚，不再按关键词额外加分。
            if violations:
                feedback += f"\n[违规扣分: -{violation_penalty}分]"
            
            # 创建评分记录
            score = Score(
                participation_id=participation_uuid,
                speech_id=speech_uuid,
                logic_score=score_breakdown.logic_score,
                argument_score=score_breakdown.argument_score,
                response_score=score_breakdown.response_score,
                persuasion_score=score_breakdown.persuasion_score,
                teamwork_score=score_breakdown.teamwork_score,
                overall_score=final_score,
                feedback=feedback
            )
            
            db.add(score)
            db.commit()
            db.refresh(score)
            
            logger.info(f"发言评分完成: speech_id={speech_id}, score={final_score}")
            
            return score
        
        except Exception as e:
            logger.error(f"评分失败: {e}", exc_info=True)
            db.rollback()
            
            # 返回默认评分
            score = Score(
                participation_id=ScoringService._uuid_value(participation_id),
                speech_id=ScoringService._uuid_value(speech_id),
                logic_score=60.0,
                argument_score=60.0,
                response_score=60.0,
                persuasion_score=60.0,
                teamwork_score=60.0,
                overall_score=60.0,
                feedback="评分系统暂时不可用（已标记为降级评分）"
            )
            
            db.add(score)
            db.commit()
            db.refresh(score)
            
            return score
    
    @staticmethod
    async def batch_score_debate(
        db: Session,
        debate_id: str,
        speeches: List[Speech],
        context: List[Dict]
    ) -> Dict:
        debate_key = str(debate_id)
        lock = ScoringService._debate_scoring_locks.setdefault(
            debate_key, asyncio.Lock()
        )
        async with lock:
            speech_ids = [speech.id for speech in speeches if speech.id is not None]
            if speech_ids:
                scored_ids = {
                    str(value)
                    for value in db.execute(
                        select(Score.speech_id).where(Score.speech_id.in_(speech_ids))
                    ).scalars().all()
                    if value is not None
                }
                if all(str(speech_id) in scored_ids for speech_id in speech_ids):
                    debate = db.execute(
                        select(Debate).where(
                            Debate.id == ScoringService._uuid_value(debate_id)
                        )
                    ).scalar_one_or_none()
                    existing_report = (
                        debate.report if debate and isinstance(debate.report, dict) else {}
                    )
                    global_report = existing_report.get("global_report")
                    return global_report if isinstance(global_report, dict) else existing_report

            return await ScoringService._batch_score_debate_unlocked(
                db=db,
                debate_id=debate_id,
                speeches=speeches,
                context=context,
            )

    @staticmethod
    async def _batch_score_debate_unlocked(
        db: Session,
        debate_id: str,
        speeches: List[Speech],
        context: List[Dict]
    ) -> Dict:
        """
        批量评分整场辩论
        
        Args:
            db: 数据库会话
            debate_id: 辩论ID
            speeches: 发言列表
            context: 辩论上下文
            
        Returns:
            全场评分报告
        """
        try:
            debate_uuid = ScoringService._uuid_value(debate_id)
            debate = db.execute(select(Debate).where(Debate.id == debate_uuid)).scalar_one_or_none()
            topic = str(debate.topic) if debate else ""
            speech_map = {str(s.id): s for s in speeches}
            supplied_context = [item for item in context if isinstance(item, dict)]
            context_by_speech_id = {
                str(item.get("speech_id")): item
                for item in supplied_context
                if str(item.get("speech_id") or "").strip()
            }
            scoring_context = [
                item
                for item in supplied_context
                if not str(item.get("speech_id") or "").strip()
            ]
            for speech in speeches:
                speech_id = str(speech.id)
                source = context_by_speech_id.get(speech_id, {})
                scoring_context.append(
                    {
                        **source,
                        "speech_id": speech_id,
                        "topic": source.get("topic") or topic,
                        "speaker_role": speech.speaker_role,
                        "speaker_type": speech.speaker_type,
                        "phase": speech.phase,
                        "content": speech.content,
                        "timestamp": speech.timestamp.isoformat() if speech.timestamp else None,
                    }
                )

            # 语义评分主链路：模型根据完整转写和上下文给出逐条及全场结论。
            evaluation = await JudgeAgent(db).batch_evaluate_debate(scoring_context)
            speech_scores = evaluation.get("speech_scores")
            if not isinstance(speech_scores, list):
                raise ValueError("judge batch evaluation returned no speech scores")

            scoring_meta = evaluation.get("report_meta")
            if not isinstance(scoring_meta, dict):
                scoring_meta = ScoreValidationService.build_report_meta(
                    scoring_source="fallback",
                    scoring_quality="fallback",
                    mode=PromptPackService.resolve_mode_from_context(scoring_context),
                ).to_dict()

            # 处理每条由裁判模型验证过的评分结果；不再叠加关键词、长度等规则分。
            score_quality_states = set()
            for item in speech_scores:
                if not isinstance(item, dict):
                    continue
                speech_id = str(item.get("speech_id") or "")
                scores_data = item.get("scores", {})
                violations_data = item.get("violations", [])
                if not isinstance(scores_data, dict) or speech_id not in speech_map:
                    continue
                speech = speech_map[speech_id]
                score_meta = scores_data.get("report_meta")
                if isinstance(score_meta, dict):
                    score_quality_states.add(str(score_meta.get("scoring_quality") or ""))
                
                participation_id = None
                if speech.speaker_type == "ai":
                    mapped_role = speech.speaker_role
                    if mapped_role.startswith("ai_"):
                        try:
                            num = mapped_role.split("_")[1]
                            mapped_role = f"debater_{num}"
                        except IndexError:
                            pass
                    
                    ai_participation = db.execute(
                        select(DebateParticipation).where(
                            DebateParticipation.debate_id == debate_uuid,
                            DebateParticipation.role == mapped_role,
                            DebateParticipation.user_id == None,
                        )
                    ).scalar_one_or_none()
                    
                    if not ai_participation:
                        ai_participation = db.execute(
                            select(DebateParticipation).where(
                                DebateParticipation.debate_id == debate_uuid,
                                DebateParticipation.role == mapped_role,
                                DebateParticipation.stance == "negative",
                            )
                        ).scalar_one_or_none()

                    if not ai_participation:
                        ai_participation = DebateParticipation(
                            debate_id=debate_uuid,
                            user_id=None,
                            role=mapped_role,
                            stance="negative"
                        )
                        db.add(ai_participation)
                        db.flush()
                    participation_id = str(ai_participation.id)
                else:
                    participation = db.execute(
                        select(DebateParticipation).where(
                            DebateParticipation.debate_id == debate_uuid,
                            DebateParticipation.user_id == speech.speaker_id
                        )
                    ).scalar_one_or_none()
                    if participation:
                        participation_id = str(participation.id)
                
                if not participation_id:
                    role = str(speech.speaker_role or "debater_1")
                    if not role.startswith("debater_"):
                        role = "debater_1"
                    participation = DebateParticipation(
                        debate_id=debate_uuid,
                        user_id=speech.speaker_id,
                        role=role,
                        stance="positive",
                    )
                    db.add(participation)
                    db.flush()
                    participation_id = str(participation.id)
                
                violations = violations_data if isinstance(violations_data, list) else []
                violation_penalty = sum(
                    float(violation.get("penalty", 0) or 0)
                    for violation in violations
                    if isinstance(violation, dict)
                )
                base_score = float(scores_data.get("overall_score", 60))
                final_score = max(0, min(100, base_score - violation_penalty))
                scores_data["overall_score"] = final_score
                
                feedback = str(scores_data.get("feedback") or "")
                if violations:
                    violation_text = "\n".join(
                        f"- {v.get('violation_type')}: {v.get('description')}"
                        for v in violations
                        if isinstance(v, dict)
                    )
                    feedback += f"\n[违规扣分: -{violation_penalty}分]\n违规详情:\n{violation_text}"
                if str((score_meta or {}).get("scoring_quality") or "") in {"fallback", "partial"}:
                    feedback += "\n[评分质量: 降级结果，建议复核]"
                
                existing_score = db.execute(
                    select(Score).where(Score.speech_id == speech.id)
                ).scalar_one_or_none()

                if existing_score:
                    existing_score.participation_id = ScoringService._uuid_value(participation_id)
                    existing_score.speech_id = ScoringService._uuid_value(speech.id)
                    existing_score.logic_score = float(scores_data.get("logic_score", 60))
                    existing_score.argument_score = float(scores_data.get("argument_score", 60))
                    existing_score.response_score = float(scores_data.get("response_score", 60))
                    existing_score.persuasion_score = float(scores_data.get("persuasion_score", 60))
                    existing_score.teamwork_score = float(scores_data.get("teamwork_score", 60))
                    existing_score.overall_score = final_score
                    existing_score.feedback = feedback
                    continue

                new_score = Score(
                    participation_id=ScoringService._uuid_value(participation_id),
                    speech_id=ScoringService._uuid_value(speech.id),
                    logic_score=float(scores_data.get("logic_score", 60)),
                    argument_score=float(scores_data.get("argument_score", 60)),
                    response_score=float(scores_data.get("response_score", 60)),
                    persuasion_score=float(scores_data.get("persuasion_score", 60)),
                    teamwork_score=float(scores_data.get("teamwork_score", 60)),
                    overall_score=final_score,
                    feedback=feedback
                )
                db.add(new_score)

            if score_quality_states.intersection({"fallback", "partial"}):
                scoring_meta = {
                    **scoring_meta,
                    "scoring_quality": "partial",
                }
            global_report = evaluation.get("global_report")
            if not isinstance(global_report, dict):
                raise ValueError("judge batch evaluation returned no global report")
            global_report["report_meta"] = dict(scoring_meta)

            if debate:
                existing_report = debate.report if isinstance(debate.report, dict) else {}
                report_patch = ScoringService._build_a_report_contract_patch(
                    topic=topic,
                    speech_score_items=speech_scores,
                    speech_map=speech_map,
                    context=scoring_context,
                    existing_report=existing_report,
                    scoring_meta=scoring_meta,
                    calibration_summary=evaluation.get("calibration_summary"),
                    anomaly_samples=evaluation.get("anomaly_samples"),
                )
                debate.report = {
                    **existing_report,
                    **report_patch,
                    "global_report": global_report,
                }

            db.commit()
            return global_report
            
        except Exception as e:
            logger.error(f"批量评分服务失败: {e}", exc_info=True)
            db.rollback()
            raise

    @staticmethod
    async def ensure_debate_scored(db: Session, debate_id: str) -> Dict[str, Any]:
        """
        Ensure every valid non-empty speech has a score before a report is read.

        Report viewing can race the background end-of-debate scoring task. It
        only starts a judge run when at least one score is missing, but that run
        evaluates the complete valid transcript so its semantic comparison and
        report conclusion stay coherent.
        """
        debate_uuid = ScoringService._uuid_value(debate_id)
        speeches: List[Speech] = (
            db.execute(
                select(Speech)
                .where(Speech.debate_id == debate_uuid)
                .where(Speech.is_valid_for_scoring.is_(True))
                .order_by(Speech.timestamp)
            )
            .scalars()
            .all()
        )
        speeches = [
            speech
            for speech in speeches
            if str(getattr(speech, "content", "") or "").strip()
        ]

        if not speeches:
            status = {
                "generated": False,
                "ready": True,
                "speech_count": 0,
                "scored_count": 0,
                "missing_score_count": 0,
                "report_status": "empty",
            }
            ScoringService._merge_report_score_status(db, debate_uuid, status)
            return status

        speech_ids = [speech.id for speech in speeches]
        existing_scores = (
            db.execute(select(Score).where(Score.speech_id.in_(speech_ids)))
            .scalars()
            .all()
        )
        scored_speech_ids = {
            str(score.speech_id) for score in existing_scores if score.speech_id is not None
        }
        missing_speeches = [
            speech for speech in speeches if str(speech.id) not in scored_speech_ids
        ]

        debate = db.execute(
            select(Debate).where(Debate.id == debate_uuid)
        ).scalar_one_or_none()
        existing_report = (
            debate.report if debate and isinstance(debate.report, dict) else {}
        )
        room_meta = existing_report.get("__room_meta")
        room_meta = room_meta if isinstance(room_meta, dict) else {}
        report_job = room_meta.get("report_job")
        report_job = report_job if isinstance(report_job, dict) else {}
        report_job_status = str(report_job.get("status") or "")
        scoring_owned_by_background = report_job_status in {"queued", "running"}

        generated = False
        if missing_speeches and not scoring_owned_by_background:
            context = [
                {
                    "speech_id": str(speech.id),
                    "speaker_role": speech.speaker_role,
                    "speaker_type": speech.speaker_type,
                    "phase": speech.phase,
                    "content": speech.content,
                    "timestamp": speech.timestamp.isoformat() if speech.timestamp else None,
                }
                for speech in speeches
            ]
            await ScoringService.batch_score_debate(
                db=db,
                debate_id=debate_uuid,
                speeches=speeches,
                context=context,
            )
            generated = True

        refreshed_scores = (
            db.execute(select(Score).where(Score.speech_id.in_(speech_ids)))
            .scalars()
            .all()
        )
        refreshed_scored_ids = {
            str(score.speech_id) for score in refreshed_scores if score.speech_id is not None
        }
        missing_score_count = max(0, len(speeches) - len(refreshed_scored_ids))
        status = {
            "generated": generated,
            "ready": missing_score_count == 0,
            "speech_count": len(speeches),
            "scored_count": len(refreshed_scored_ids),
            "missing_score_count": missing_score_count,
            "report_status": (
                "ready"
                if missing_score_count == 0
                else "processing"
                if scoring_owned_by_background
                else "failed"
                if report_job_status == "failed"
                else "processing"
            ),
            "report_job_status": report_job_status or None,
        }
        ScoringService._merge_report_score_status(db, debate_uuid, status)
        return status

    @staticmethod
    def _merge_report_score_status(
        db: Session,
        debate_id: str,
        status: Dict[str, Any],
    ) -> None:
        debate_uuid = ScoringService._uuid_value(debate_id)
        debate = db.execute(select(Debate).where(Debate.id == debate_uuid)).scalar_one_or_none()
        if not debate:
            return

        existing_report = debate.report if isinstance(debate.report, dict) else {}
        generated = bool(status.get("generated"))
        current_revision = int(existing_report.get("score_revision") or 0)
        next_revision = current_revision + 1 if generated else current_revision
        now = datetime.utcnow().isoformat()

        debate.report = {
            **existing_report,
            "report_status": status.get("report_status", "ready"),
            "score_revision": next_revision,
            "score_speech_count": int(status.get("speech_count") or 0),
            "score_ready_count": int(status.get("scored_count") or 0),
            "score_missing_count": int(status.get("missing_score_count") or 0),
            "score_checked_at": now,
            **({"score_generated_at": now} if generated else {}),
        }
        db.commit()

    @staticmethod
    async def check_violations(
        db: Session,
        speech_content: str,
        speaker_role: str
    ) -> List[Violation]:
        """
        检查违规行为
        
        Args:
            db: 数据库会话
            speech_content: 发言内容
            speaker_role: 发言者角色
            
        Returns:
            违规行为列表
        """
        try:
            judge = JudgeAgent(db)
            violations = await judge.check_violations(
                speech_content=speech_content,
                speaker_role=speaker_role
            )
            
            return violations
        
        except Exception as e:
            logger.error(f"违规检测失败: {e}", exc_info=True)
            return []
    
    @staticmethod
    def calculate_final_score(
        db: Session,
        participation_id: str
    ) -> Dict[str, float]:
        """
        计算最终得分
        
        Args:
            db: 数据库会话
            participation_id: 参与ID
            
        Returns:
            最终得分详情
        """
        participation_uuid = ScoringService._uuid_value(participation_id)
        participation = db.execute(
            select(DebateParticipation).where(DebateParticipation.id == participation_uuid)
        ).scalar_one_or_none()

        if not participation:
            return {
                "logic_score": 0.0,
                "argument_score": 0.0,
                "response_score": 0.0,
                "persuasion_score": 0.0,
                "teamwork_score": 0.0,
                "overall_score": 0.0,
                "speech_count": 0,
                "total_duration": 0,
            }

        def _map_speech_role_to_participation_role(speaker_type: str, speaker_role: Optional[str]) -> Optional[str]:
            if not speaker_role:
                return None
            role = str(speaker_role)
            if speaker_type == "ai" and role.startswith("ai_"):
                parts = role.split("_", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    return f"debater_{parts[1]}"
                return None
            if role.startswith("debater_"):
                return role
            return None

        speeches = (
            db.execute(
                select(Speech)
                .where(Speech.debate_id == participation.debate_id)
                .where(Speech.is_valid_for_scoring.is_(True))
            )
            .scalars()
            .all()
        )

        participant_speeches: List[Speech] = []
        if participation.user_id:
            participant_speeches = [
                s for s in speeches if s.speaker_id == participation.user_id
            ]
        else:
            participant_speeches = [
                s
                for s in speeches
                if s.speaker_type == "ai"
                and _map_speech_role_to_participation_role(s.speaker_type, s.speaker_role)
                == str(participation.role)
            ]

        speech_count = len(participant_speeches)
        total_duration = sum(max(0, int(s.duration or 0)) for s in participant_speeches)

        scores = (
            db.execute(select(Score).where(Score.participation_id == participation_uuid))
            .scalars()
            .all()
        )
        
        if not scores:
            return {
                "logic_score": 0.0,
                "argument_score": 0.0,
                "response_score": 0.0,
                "persuasion_score": 0.0,
                "teamwork_score": 0.0,
                "overall_score": 0.0,
                "speech_count": speech_count,
                "total_duration": total_duration,
            }
        
        # 计算各维度平均分
        logic_avg = sum(s.logic_score for s in scores) / len(scores)
        argument_avg = sum(s.argument_score for s in scores) / len(scores)
        response_avg = sum(s.response_score for s in scores) / len(scores)
        persuasion_avg = sum(s.persuasion_score for s in scores) / len(scores)
        teamwork_avg = sum(s.teamwork_score for s in scores) / len(scores)
        overall_avg = sum(s.overall_score for s in scores) / len(scores)
        
        return {
            "logic_score": round(logic_avg, 2),
            "argument_score": round(argument_avg, 2),
            "response_score": round(response_avg, 2),
            "persuasion_score": round(persuasion_avg, 2),
            "teamwork_score": round(teamwork_avg, 2),
            "overall_score": round(overall_avg, 2),
            "speech_count": speech_count,
            "total_duration": total_duration,
        }

    @staticmethod
    def get_debate_human_or_ai_score(
            db:Session,
            debate_id: str,
            type:str="human"
    )-> Dict[str, float]:
        '''计算该辩论人类发言的总分
        type:human or ai
        '''
        query = (
            db.query(
                Score,  # 相当于 scores.*
                Speech.speaker_type,
                Speech.speaker_role,
                Speech.content
            )
            .join(Speech, Score.speech_id == Speech.id)  # 显式连接条件
            .filter(Speech.debate_id == ScoringService._uuid_value(debate_id))
            .filter(Speech.is_valid_for_scoring.is_(True))
            .filter(Speech.speaker_type == type)
        )

        # 分页查询
        scores = query.all()
        if  not scores or len(scores)<=0:
            return {
                "logic_score": 0.0,
                "argument_score": 0.0,
                "response_score": 0.0,
                "persuasion_score": 0.0,
                "teamwork_score": 0.0,
                "overall_score": 0.0,
            }

        return {
            "logic_score": round(sum(s[0].logic_score for s in scores)/ len(scores),2),
            "argument_score": round(sum(s[0].argument_score for s in scores)/ len(scores),2),
            "response_score": round(sum(s[0].response_score for s in scores)/ len(scores),2),
            "persuasion_score": round(sum(s[0].persuasion_score for s in scores)/ len(scores),2),
            "teamwork_score": round(sum(s[0].teamwork_score for s in scores)/ len(scores),2),
            "overall_score": round(sum(s[0].overall_score for s in scores)/ len(scores),2),
        }


    @staticmethod
    def get_debate_statistics(
        db: Session,
        debate_id: str
    ) -> Dict:
        """
        获取辩论统计数据
        
        Args:
            db: 数据库会话
            debate_id: 辩论ID
            
        Returns:
            统计数据
        """
        def _map_speech_role_to_participation_role(speaker_type: str, speaker_role: Optional[str]) -> Optional[str]:
            if not speaker_role:
                return None
            role = str(speaker_role)
            if speaker_type == "ai" and role.startswith("ai_"):
                parts = role.split("_", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    return f"debater_{parts[1]}"
                return None
            if role.startswith("debater_"):
                return role
            return None

        debate_uuid = ScoringService._uuid_value(debate_id)
        participations = (
            db.execute(
                select(DebateParticipation).where(
                    DebateParticipation.debate_id == debate_uuid
                )
            )
            .scalars()
            .all()
        )

        role_to_stance: Dict[str, str] = {
            str(p.role): str(p.stance) for p in participations if p.role and p.stance
        }

        speeches = (
            db.execute(
                select(Speech)
                .where(Speech.debate_id == debate_uuid)
                .where(Speech.is_valid_for_scoring.is_(True))
            )
            .scalars()
            .all()
        )

        speech_ids = [s.id for s in speeches]
        scores: List[Score] = []
        if speech_ids:
            scores = (
                db.execute(select(Score).where(Score.speech_id.in_(speech_ids)))
                .scalars()
                .all()
            )
        score_by_speech_id: Dict[str, Score] = {
            str(s.speech_id): s for s in scores if s.speech_id is not None
        }
        
        # 统计各方数据
        positive_stats = {
            "speech_count": 0,
            "total_duration": 0,
            "avg_score": 0.0,
            "participants": []
        }
        
        negative_stats = {
            "speech_count": 0,
            "total_duration": 0,
            "avg_score": 0.0,
            "participants": []
        }
        
        for participation in participations:
            final_score = ScoringService.calculate_final_score(db, str(participation.id))
            participant_data = {
                "user_id": str(participation.user_id),
                "role": str(participation.role),
                "final_score": final_score,
                "speech_count": int(final_score.get("speech_count", 0)),
                "total_duration": int(final_score.get("total_duration", 0)),
            }
            if str(participation.stance) == "positive":
                positive_stats["participants"].append(participant_data)
            else:
                negative_stats["participants"].append(participant_data)

        side_score_values: Dict[str, List[float]] = {"positive": [], "negative": []}
        team_score_values: Dict[str, List[float]] = {"human": [], "ai": []}
        team_duration: Dict[str, int] = {"human": 0, "ai": 0}
        team_speech_count: Dict[str, int] = {"human": 0, "ai": 0}
        team_dim_sums: Dict[str, Dict[str, float]] = {
            "human": {
                "logic_score": 0.0,
                "argument_score": 0.0,
                "response_score": 0.0,
                "persuasion_score": 0.0,
                "teamwork_score": 0.0,
            },
            "ai": {
                "logic_score": 0.0,
                "argument_score": 0.0,
                "response_score": 0.0,
                "persuasion_score": 0.0,
                "teamwork_score": 0.0,
            },
        }
        team_scored_count: Dict[str, int] = {"human": 0, "ai": 0}

        for speech in speeches:
            duration = max(0, int(speech.duration or 0))
            speaker_type = str(speech.speaker_type)
            if speaker_type in team_duration:
                team_duration[speaker_type] += duration
                team_speech_count[speaker_type] += 1

            score = score_by_speech_id.get(str(speech.id))
            if score and speaker_type in team_score_values:
                team_score_values[speaker_type].append(float(score.overall_score))
                team_dim_sums[speaker_type]["logic_score"] += float(score.logic_score)
                team_dim_sums[speaker_type]["argument_score"] += float(score.argument_score)
                team_dim_sums[speaker_type]["response_score"] += float(score.response_score)
                team_dim_sums[speaker_type]["persuasion_score"] += float(score.persuasion_score)
                team_dim_sums[speaker_type]["teamwork_score"] += float(score.teamwork_score)
                team_scored_count[speaker_type] += 1
            #
            # mapped_role = _map_speech_role_to_participation_role(
            #     str(speech.speaker_type), str(speech.speaker_role)
            # )
            # stance = role_to_stance.get(mapped_role or "")
            stance="positive" if 'human' in speaker_type else 'negative'
            if stance not in ("positive", "negative"):
                continue

            if stance == "positive":
                positive_stats["speech_count"] += 1
                positive_stats["total_duration"] += duration
            else:
                negative_stats["speech_count"] += 1
                negative_stats["total_duration"] += duration

            if score:
                side_score_values[stance].append(float(score.overall_score))
        
        if side_score_values["positive"]:
            positive_stats["avg_score"] = round(
                sum(side_score_values["positive"]) / len(side_score_values["positive"]), 2
            )

        if side_score_values["negative"]:
            negative_stats["avg_score"] = round(
                sum(side_score_values["negative"]) / len(side_score_values["negative"]), 2
            )
        
        # 判断胜负
        winner = None
        if positive_stats["avg_score"] > negative_stats["avg_score"]:
            winner = "positive"
        elif negative_stats["avg_score"] > positive_stats["avg_score"]:
            winner = "negative"
        else:
            winner = "tie"
        
        def _avg(values: List[float]) -> float:
            if not values:
                return 0.0
            return round(sum(values) / len(values), 2)

        human_stats = {
            "speech_count": team_speech_count["human"],
            "total_duration": team_duration["human"],
            "avg_score": _avg(team_score_values["human"]),
            "avg_logic_score": round(team_dim_sums["human"]["logic_score"] / team_scored_count["human"], 2)
            if team_scored_count["human"]
            else 0.0,
            "avg_argument_score": round(team_dim_sums["human"]["argument_score"] / team_scored_count["human"], 2)
            if team_scored_count["human"]
            else 0.0,
            "avg_response_score": round(team_dim_sums["human"]["response_score"] / team_scored_count["human"], 2)
            if team_scored_count["human"]
            else 0.0,
            "avg_persuasion_score": round(team_dim_sums["human"]["persuasion_score"] / team_scored_count["human"], 2)
            if team_scored_count["human"]
            else 0.0,
            "avg_teamwork_score": round(team_dim_sums["human"]["teamwork_score"] / team_scored_count["human"], 2)
            if team_scored_count["human"]
            else 0.0,
        }

        ai_stats = {
            "speech_count": team_speech_count["ai"],
            "total_duration": team_duration["ai"],
            "avg_score": _avg(team_score_values["ai"]),
            "avg_logic_score": round(team_dim_sums["ai"]["logic_score"] / team_scored_count["ai"], 2)
            if team_scored_count["ai"]
            else 0.0,
            "avg_argument_score": round(team_dim_sums["ai"]["argument_score"] / team_scored_count["ai"], 2)
            if team_scored_count["ai"]
            else 0.0,
            "avg_response_score": round(team_dim_sums["ai"]["response_score"] / team_scored_count["ai"], 2)
            if team_scored_count["ai"]
            else 0.0,
            "avg_persuasion_score": round(team_dim_sums["ai"]["persuasion_score"] / team_scored_count["ai"], 2)
            if team_scored_count["ai"]
            else 0.0,
            "avg_teamwork_score": round(team_dim_sums["ai"]["teamwork_score"] / team_scored_count["ai"], 2)
            if team_scored_count["ai"]
            else 0.0,
        }

        human_ai_winner: str
        if human_stats["avg_score"] > ai_stats["avg_score"]:
            human_ai_winner = "human"
        elif ai_stats["avg_score"] > human_stats["avg_score"]:
            human_ai_winner = "ai"
        else:
            human_ai_winner = "tie"

        return {
            "positive": positive_stats,
            "negative": negative_stats,
            "winner": winner,
            "human": human_stats,
            "ai": ai_stats,
            "human_ai_winner": human_ai_winner,
            "total_speeches": len(speeches),
            "total_duration": sum(max(0, int(s.duration or 0)) for s in speeches),
        }
