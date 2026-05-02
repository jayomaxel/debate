"""
评分服务
负责实时评分、关键词加分、违规检测、最终得分计算
"""
from logging_config import get_logger
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime

from models.speech import Speech
from models.score import Score
from models.debate import Debate, DebateParticipation
from agents.judge_agent import JudgeAgent, ScoreBreakdown, Violation

logger = get_logger(__name__)


class ScoringService:
    """评分服务"""
    
    # 预定义关键词列表（可以从配置中读取）
    POSITIVE_KEYWORDS = [
        # 通用论证词
        "数据显示", "研究表明", "事实证明", "根据统计",
        "逻辑上", "显而易见", "不可否认", "众所周知",
        "合理", "科学", "客观", "公正",
        # AI 课程核心术语
        "情感计算", "自然语言处理", "NLP", "AIGC",
        "大模型", "大语言模型", "人机交互", "人机协作",
        "图灵测试", "机器学习", "深度学习", "神经网络",
        "AI伦理", "算法偏见", "数据隐私", "可解释性",
        "生成式AI", "强化学习", "知识图谱", "计算机视觉",
    ]
    
    # 关键词加分配置
    KEYWORD_BONUS_PER_WORD = 2.0  # 每个关键词加2分
    MAX_KEYWORD_BONUS = 10.0      # 最多加10分

    LOGIC_MARKERS = [
        "首先", "其次", "再次", "最后", "因为", "所以", "因此", "如果", "那么",
        "可见", "综上", "一方面", "另一方面", "前提", "结论", "逻辑",
    ]
    EVIDENCE_MARKERS = [
        "数据", "研究", "调查", "统计", "案例", "事实", "例如", "比如", "证明",
        "显示", "表明", "报告", "实验", "现实", "政策", "成本", "效率",
    ]
    RESPONSE_MARKERS = [
        "对方", "反方", "正方", "质疑", "反驳", "回应", "回答", "漏洞", "问题",
        "忽略", "不能说明", "并不等于", "为什么", "如何", "是否",
    ]
    ETHICS_MARKERS = [
        "伦理", "公平", "隐私", "安全", "责任", "透明", "偏见", "风险", "治理",
        "监管", "社会", "人文", "价值", "边界",
    ]
    AI_TERMS = [
        "AI", "人工智能", "算法", "模型", "大模型", "AIGC", "NLP", "自然语言",
        "机器学习", "深度学习", "数据", "算力", "人机协作", "智能体",
    ]

    @staticmethod
    def _clamp_score(value: float) -> float:
        return round(max(0.0, min(100.0, float(value))), 2)

    @staticmethod
    def _marker_count(content: str, markers: List[str]) -> int:
        return sum(1 for marker in markers if marker and marker in content)

    @staticmethod
    def _topic_relevance(content: str, topic: str) -> float:
        topic = (topic or "").strip()
        content = content or ""
        if not topic or not content:
            return 0.0

        terms = set()
        for raw in topic.replace("，", " ").replace("。", " ").replace("、", " ").split():
            raw = raw.strip()
            if len(raw) >= 2:
                terms.add(raw)
        for i in range(max(0, len(topic) - 1)):
            term = topic[i : i + 2]
            if term.strip():
                terms.add(term)

        hits = sum(1 for term in terms if term in content)
        return min(12.0, hits * 1.5)

    @staticmethod
    def _speech_stance(speaker_type: str) -> str:
        # Product rule: human is always affirmative, AI is always negative.
        return "positive" if str(speaker_type) == "human" else "negative"

    @staticmethod
    def _phase_label(phase: str) -> str:
        return {
            "opening": "立论",
            "questioning": "盘问",
            "free_debate": "自由辩论",
            "closing": "总结陈词",
        }.get(str(phase), str(phase or "发言"))

    @staticmethod
    def _local_score_speech(speech: Speech, topic: str) -> Dict:
        content = str(getattr(speech, "content", "") or "").strip()
        phase = str(getattr(speech, "phase", "") or "")
        length = len(content)

        if not content:
            base_scores = {
                "logic_score": 0.0,
                "argument_score": 0.0,
                "response_score": 0.0,
                "persuasion_score": 0.0,
                "teamwork_score": 0.0,
                "overall_score": 0.0,
                "feedback": "未检测到有效发言内容，无法形成评分。",
            }
            return {"speech_id": str(speech.id), "scores": base_scores, "violations": []}

        length_bonus = min(12.0, length / 45.0)
        topic_bonus = ScoringService._topic_relevance(content, topic)
        logic_hits = ScoringService._marker_count(content, ScoringService.LOGIC_MARKERS)
        evidence_hits = ScoringService._marker_count(content, ScoringService.EVIDENCE_MARKERS)
        response_hits = ScoringService._marker_count(content, ScoringService.RESPONSE_MARKERS)
        ethics_hits = ScoringService._marker_count(content, ScoringService.ETHICS_MARKERS)
        ai_hits = ScoringService._marker_count(content, ScoringService.AI_TERMS)

        logic_score = 58 + length_bonus + topic_bonus + min(16, logic_hits * 4)
        argument_score = 56 + length_bonus + topic_bonus + min(14, evidence_hits * 3) + min(10, ai_hits * 2)
        response_score = 56 + min(10, length_bonus) + min(22, response_hits * 4)
        persuasion_score = 58 + min(12, length_bonus) + min(10, logic_hits * 2) + min(8, content.count("！") + content.count("？") + content.count("?"))
        teamwork_score = 58 + min(10, length_bonus) + min(18, ethics_hits * 4) + min(8, ai_hits * 1.5)

        if phase == "questioning":
            response_score += 8
            logic_score += 3
        elif phase == "free_debate":
            response_score += 6
            persuasion_score += 3
        elif phase == "closing":
            logic_score += 6
            persuasion_score += 4
        elif phase == "opening":
            argument_score += 5
            logic_score += 4

        scores = {
            "logic_score": ScoringService._clamp_score(logic_score),
            "argument_score": ScoringService._clamp_score(argument_score),
            "response_score": ScoringService._clamp_score(response_score),
            "persuasion_score": ScoringService._clamp_score(persuasion_score),
            "teamwork_score": ScoringService._clamp_score(teamwork_score),
        }
        overall = (
            scores["logic_score"] * 0.24
            + scores["argument_score"] * 0.24
            + scores["response_score"] * 0.22
            + scores["persuasion_score"] * 0.18
            + scores["teamwork_score"] * 0.12
        )
        scores["overall_score"] = ScoringService._clamp_score(overall)

        stance_label = "正方" if ScoringService._speech_stance(str(speech.speaker_type)) == "positive" else "反方"
        phase_label = ScoringService._phase_label(phase)
        feedback_bits = []
        if topic_bonus:
            feedback_bits.append("能围绕辩题展开")
        if logic_hits:
            feedback_bits.append("论证结构较清楚")
        if evidence_hits:
            feedback_bits.append("有事实或案例支撑")
        if response_hits:
            feedback_bits.append("回应了对方观点")
        if not feedback_bits:
            feedback_bits.append("观点已形成，但论据和回应还可以更具体")
        scores["feedback"] = f"{stance_label}{phase_label}发言：" + "，".join(feedback_bits) + "。"

        return {"speech_id": str(speech.id), "scores": scores, "violations": []}

    @staticmethod
    def _build_global_report_from_scores(topic: str, speech_score_items: List[Dict], speech_map: Dict[str, Speech]) -> Dict:
        side_values: Dict[str, Dict[str, List[float]]] = {
            "positive": {"logic_score": [], "argument_score": [], "response_score": [], "persuasion_score": [], "teamwork_score": [], "overall_score": []},
            "negative": {"logic_score": [], "argument_score": [], "response_score": [], "persuasion_score": [], "teamwork_score": [], "overall_score": []},
        }

        for item in speech_score_items:
            if not isinstance(item, dict):
                continue
            speech = speech_map.get(str(item.get("speech_id") or ""))
            scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}
            if not speech or not scores:
                continue
            side = ScoringService._speech_stance(str(speech.speaker_type))
            for key in side_values[side]:
                side_values[side][key].append(float(scores.get(key, 0) or 0))

        def avg(side: str, key: str) -> float:
            values = [v for v in side_values[side][key] if v > 0]
            return round(sum(values) / len(values), 2) if values else 0.0

        def side_report(side: str) -> Dict[str, float]:
            return {
                "logical_thinking": avg(side, "logic_score"),
                "argument_quality": avg(side, "argument_score"),
                "reaction_speed": avg(side, "response_score"),
                "persuasion": avg(side, "persuasion_score"),
                "teamwork": avg(side, "teamwork_score"),
                "total_score": avg(side, "overall_score"),
            }

        positive = side_report("positive")
        negative = side_report("negative")
        if positive["total_score"] > negative["total_score"]:
            winner = "positive"
            reason = "正方整体得分更高，主要来自发言内容与辩题关联、论证结构和回应质量。"
        elif negative["total_score"] > positive["total_score"]:
            winner = "negative"
            reason = "反方整体得分更高，主要来自发言内容与辩题关联、论证结构和回应质量。"
        else:
            winner = "draw"
            reason = "双方综合得分接近，胜负不明显。"

        return {
            "winner": winner,
            "winning_reason": reason,
            "scores": {"positive": positive, "negative": negative},
            "overall_comment": f"本报告基于辩题“{topic}”及正反方完整发言，从逻辑、论据、回应、表达和科技伦理素养五个维度评分。",
            "suggestions": [
                "正方需要继续加强论据的事实支撑和对反方质疑的直接回应。",
                "反方需要保持反驳的针对性，并把论点和辩题核心概念绑定得更紧。",
                "双方在总结环节应明确回扣辩题，压缩重复表达，突出最强论据。",
            ],
        }
    
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
            
            # 计算关键词加分
            keyword_bonus = ScoringService.calculate_keyword_bonus(speech_content)
            
            # 计算违规扣分
            violation_penalty = sum(v.penalty for v in violations)
            
            # 计算最终得分
            base_score = score_breakdown.overall_score
            final_score = max(0, min(100, base_score + keyword_bonus - violation_penalty))
            
            # 生成反馈
            feedback = await judge.generate_feedback(
                speech_content=speech_content,
                score=score_breakdown,
                violations=violations
            )
            
            # 添加关键词和违规信息到反馈
            if keyword_bonus > 0:
                feedback += f"\n[关键词加分: +{keyword_bonus}分]"
            if violations:
                feedback += f"\n[违规扣分: -{violation_penalty}分]"
            
            # 创建评分记录
            score = Score(
                participation_id=participation_id,
                speech_id=speech_id,
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
                participation_id=participation_id,
                speech_id=speech_id,
                logic_score=70.0,
                argument_score=70.0,
                response_score=70.0,
                persuasion_score=70.0,
                teamwork_score=70.0,
                overall_score=70.0,
                feedback="评分系统暂时不可用"
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
            # 1. 使用本地确定性规则快速生成每条发言评分，避免外部模型慢或无响应导致报告为空。
            debate = db.execute(select(Debate).where(Debate.id == debate_id)).scalar_one_or_none()
            topic = str(debate.topic) if debate else ""
            speech_map = {str(s.id): s for s in speeches}
            speech_scores = [
                ScoringService._local_score_speech(speech, topic)
                for speech in speeches
                if str(getattr(speech, "content", "") or "").strip()
            ]

            # 2. 处理每条发言的评分
            for item in speech_scores:
                speech_id = item.get("speech_id")
                scores_data = item.get("scores", {})
                violations_data = item.get("violations", [])
                
                if not speech_id or speech_id not in speech_map:
                    continue
                    
                speech = speech_map[speech_id]
                
                # 获取参与ID (类似_auto_score_and_generate_report中的逻辑)
                participation_id = None
                if speech.speaker_type == "ai":
                    # AI处理逻辑... (简化版，假设已存在或不重要，或者需要重新查找)
                    # 为了简化，这里再次查找或创建
                    mapped_role = speech.speaker_role
                    if mapped_role.startswith("ai_"):
                        try:
                            num = mapped_role.split("_")[1]
                            mapped_role = f"debater_{num}"
                        except IndexError:
                            pass
                    
                    ai_participation = db.execute(
                        select(DebateParticipation).where(
                            DebateParticipation.debate_id == debate_id,
                            DebateParticipation.role == mapped_role,
                            DebateParticipation.user_id == None,
                        )
                    ).scalar_one_or_none()
                    
                    if not ai_participation:
                        ai_participation = db.execute(
                            select(DebateParticipation).where(
                                DebateParticipation.debate_id == debate_id,
                                DebateParticipation.role == mapped_role,
                                DebateParticipation.stance == "negative",
                            )
                        ).scalar_one_or_none()

                    if not ai_participation:
                        ai_participation = DebateParticipation(
                            debate_id=debate_id,
                            user_id=None,
                            role=mapped_role,
                            stance="negative" # 假设AI是反方
                        )
                        db.add(ai_participation)
                        db.flush()
                    participation_id = str(ai_participation.id)
                else:
                    participation = db.execute(
                        select(DebateParticipation).where(
                            DebateParticipation.debate_id == debate_id,
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
                        debate_id=debate_id,
                        user_id=speech.speaker_id,
                        role=role,
                        stance="positive",
                    )
                    db.add(participation)
                    db.flush()
                    participation_id = str(participation.id)
                
                # 检查是否已存在评分
                # 计算关键词加分
                keyword_bonus = ScoringService.calculate_keyword_bonus(speech.content)
                
                # 计算违规扣分
                violation_penalty = sum(float(v.get("penalty", 0)) for v in violations_data)
                
                # 基础分
                base_score = float(scores_data.get("overall_score", 70))
                
                # 最终分
                final_score = max(0, min(100, base_score + keyword_bonus - violation_penalty))
                scores_data["overall_score"] = final_score
                
                # 构造反馈
                feedback = scores_data.get("feedback", "")
                if keyword_bonus > 0:
                    feedback += f"\n[关键词加分: +{keyword_bonus}分]"
                if violations_data:
                    violation_text = "\n".join([f"- {v.get('violation_type')}: {v.get('description')}" for v in violations_data])
                    feedback += f"\n[违规扣分: -{violation_penalty}分]\n违规详情:\n{violation_text}"
                
                # 保存评分
                existing_score = db.execute(
                    select(Score).where(Score.speech_id == speech.id)
                ).scalar_one_or_none()

                if existing_score:
                    existing_score.participation_id = participation_id
                    existing_score.logic_score = float(scores_data.get("logic_score", 70))
                    existing_score.argument_score = float(scores_data.get("argument_score", 70))
                    existing_score.response_score = float(scores_data.get("response_score", 70))
                    existing_score.persuasion_score = float(scores_data.get("persuasion_score", 70))
                    existing_score.teamwork_score = float(scores_data.get("teamwork_score", 70))
                    existing_score.overall_score = final_score
                    existing_score.feedback = feedback
                    continue

                new_score = Score(
                    participation_id=participation_id,
                    speech_id=str(speech.id),
                    logic_score=float(scores_data.get("logic_score", 70)),
                    argument_score=float(scores_data.get("argument_score", 70)),
                    response_score=float(scores_data.get("response_score", 70)),
                    persuasion_score=float(scores_data.get("persuasion_score", 70)),
                    teamwork_score=float(scores_data.get("teamwork_score", 70)),
                    overall_score=final_score,
                    feedback=feedback
                )
                db.add(new_score)
            
            global_report = ScoringService._build_global_report_from_scores(
                topic=topic,
                speech_score_items=speech_scores,
                speech_map=speech_map,
            )

            db.commit()
            return global_report
            
        except Exception as e:
            logger.error(f"批量评分服务失败: {e}", exc_info=True)
            db.rollback()
            raise

    @staticmethod
    def calculate_keyword_bonus(speech_content: str) -> float:
        """
        计算关键词加分
        
        Args:
            speech_content: 发言内容
            
        Returns:
            加分值
        """
        keyword_count = 0
        
        keywords = (
            list(ScoringService.POSITIVE_KEYWORDS)
            + ScoringService.LOGIC_MARKERS
            + ScoringService.EVIDENCE_MARKERS
            + ScoringService.AI_TERMS
        )

        for keyword in keywords:
            if keyword in speech_content:
                keyword_count += 1
        
        bonus = min(
            keyword_count * ScoringService.KEYWORD_BONUS_PER_WORD,
            ScoringService.MAX_KEYWORD_BONUS
        )
        
        return bonus
    
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
        participation = db.execute(
            select(DebateParticipation).where(DebateParticipation.id == participation_id)
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
            db.execute(select(Score).where(Score.participation_id == participation_id))
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
            .filter(Speech.debate_id == debate_id)
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

        participations = (
            db.execute(
                select(DebateParticipation).where(
                    DebateParticipation.debate_id == debate_id
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
                .where(Speech.debate_id == debate_id)
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
