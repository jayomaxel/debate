"""
历史记录服务
提供辩论历史记录查询和筛选功能
"""
from logging_config import get_logger
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from models.user import User
from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from services.scoring_service import ScoringService

logger = get_logger(__name__)


class HistoryService:
    """历史记录服务类"""
    
    def __init__(self, db: Session):
        """
        初始化历史记录服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    def get_debate_history(
        self,
        student_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        获取学生的辩论历史记录
        
        Args:
            student_id: 学生ID
            limit: 返回记录数量限制
            offset: 偏移量（用于分页）
            
        Returns:
            辩论历史记录列表
        """
        try:
            # 查询学生参与的所有辩论
            query = (self.db.query(
                Debate.id,
                Debate.topic,
                Debate.start_time,
                Debate.end_time,
                Debate.status,
                Debate.duration,
                DebateParticipation.id.label("participation_id"),
                DebateParticipation.role,
                DebateParticipation.stance
            ).join(
                DebateParticipation, Debate.id == DebateParticipation.debate_id
            ).filter(
                Debate.status == "completed"
            )
            .filter(
                DebateParticipation.user_id == student_id
            ).order_by(desc(Debate.start_time)))
            
            # 获取总数
            total = query.count()
            
            # 分页查询
            debates = query.limit(limit).offset(offset).all()

            debate_stats_cache: Dict[str, Dict[str, Any]] = {}

            def _get_stats(debate_id: str) -> Dict[str, Any]:
                if debate_id not in debate_stats_cache:
                    debate_stats_cache[debate_id] = ScoringService.get_debate_statistics(
                        self.db, debate_id
                    )
                return debate_stats_cache[debate_id]

            debate_results=[]
            for d in debates:
                human_score = round(
                    float(
                        ScoringService.get_debate_human_or_ai_score(
                            self.db, str(d.id),'human'
                        ).get("overall_score", 0.0)
                    ),
                    2,
                )

                ai_score=round(
                    float(
                        ScoringService.get_debate_human_or_ai_score(
                            self.db, str(d.id),'ai'
                        ).get("overall_score", 0.0)
                    ),
                    2,
                )
                status="draw"
                if human_score>=ai_score:
                    status="win"
                else:
                    status="lose"

                debate_result={
                        "debate_id": str(d.id),
                        "topic": d.topic,
                        "role": d.role,
                        "stance": d.stance,
                        "status": d.status,
                        "score": human_score,
                        "outcome":status,
                        "duration_seconds": int(d.duration),
                        "created_at": d.start_time.isoformat() if d.start_time else None
                    }
                debate_results.append(debate_result)


            return {
                "list": debate_results,
                "total": total,
                "page": offset // limit + 1 if limit > 0 else 1,
                "page_size": limit
            }
            
        except Exception as e:
            logger.error(f"Failed to get debate history: {e}", exc_info=True)
            raise

    
    def filter_history(
        self,
        student_id: str,
        status: Optional[str] = None,
        role: Optional[str] = None,
        stance: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        筛选学生的辩论历史记录
        
        Args:
            student_id: 学生ID
            status: 辩论状态筛选（可选）
            role: 角色筛选（可选）
            stance: 立场筛选（可选）
            start_date: 开始日期筛选（可选）
            end_date: 结束日期筛选（可选）
            limit: 返回记录数量限制
            offset: 偏移量（用于分页）
            
        Returns:
            筛选后的辩论历史记录
        """
        try:
            # 构建查询
            query = self.db.query(
                Debate.id,
                Debate.topic,
                Debate.start_time,
                Debate.end_time,
                Debate.status,
                DebateParticipation.id.label("participation_id"),
                DebateParticipation.role,
                DebateParticipation.stance
            ).join(
                DebateParticipation, Debate.id == DebateParticipation.debate_id
            ).filter(
                DebateParticipation.user_id == student_id
            )
            
            # 应用筛选条件
            if status:
                query = query.filter(Debate.status == status)
            
            if role:
                query = query.filter(DebateParticipation.role == role)
            
            if stance:
                query = query.filter(DebateParticipation.stance == stance)
            
            if start_date:
                query = query.filter(Debate.start_time >= start_date)
            
            if end_date:
                query = query.filter(Debate.start_time <= end_date)
            
            # 排序
            query = query.order_by(desc(Debate.start_time))
            
            # 获取总数
            total = query.count()
            
            # 分页查询
            debates = query.limit(limit).offset(offset).all()

            debate_stats_cache: Dict[str, Dict[str, Any]] = {}

            def _get_stats(debate_id: str) -> Dict[str, Any]:
                if debate_id not in debate_stats_cache:
                    debate_stats_cache[debate_id] = ScoringService.get_debate_statistics(
                        self.db, debate_id
                    )
                return debate_stats_cache[debate_id]
            
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "filters": {
                    "status": status,
                    "role": role,
                    "stance": stance,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "debates": [
                    {
                        "debate_id": str(d.id),
                        "topic": d.topic,
                        "start_time": d.start_time.isoformat() if d.start_time else None,
                        "end_time": d.end_time.isoformat() if d.end_time else None,
                        "status": d.status,
                        "role": d.role,
                        "stance": d.stance,
                        "outcome": (
                            "draw"
                            if _get_stats(str(d.id)).get("winner") == "tie"
                            else (
                                "win"
                                if _get_stats(str(d.id)).get("winner") == str(d.stance)
                                else "lose"
                            )
                            if _get_stats(str(d.id)).get("winner") in ("positive", "negative")
                            else "draw"
                        ),
                        "duration_seconds": int(_get_stats(str(d.id)).get("total_duration") or 0),
                        "overall_score": round(
                            float(
                                ScoringService.calculate_final_score(
                                    self.db, str(d.participation_id)
                                ).get("overall_score", 0.0)
                            ),
                            2,
                        ),
                    }
                    for d in debates
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to filter history: {e}", exc_info=True)
            raise
    
    def get_debate_details(self, debate_id: str, student_id: str) -> Optional[Dict[str, Any]]:
        """
        获取辩论详细信息
        
        Args:
            debate_id: 辩论ID
            student_id: 学生ID（用于权限验证）
            
        Returns:
            辩论详细信息，如果学生未参与该辩论则返回None
        """
        try:
            # 获取辩论基本信息
            debate = self.db.query(Debate).filter(Debate.id == debate_id).first()
            
            if not debate:
                return None

            viewer = self.db.query(User).filter(User.id == student_id).first()
            if not viewer:
                return None

            participation = None
            if viewer.user_type == "student":
                participation = self.db.query(DebateParticipation).filter(
                    and_(
                        DebateParticipation.debate_id == debate_id,
                        DebateParticipation.user_id == student_id
                    )
                ).first()
                if not participation:
                    return None
            
            # 获取整场辩论的发言记录（用于回放）
            speeches = (
                self.db.query(Speech)
                .filter(Speech.debate_id == debate_id)
                .order_by(Speech.timestamp)
                .all()
            )

            speech_items: List[Dict[str, Any]] = []
            for s in speeches:
                if s.speaker_id:
                    user_id = str(s.speaker_id)
                else:
                    user_id = f"ai:{s.speaker_role}"
                speech_items.append(
                    {
                        "id": str(s.id),
                        "debate_id": str(s.debate_id),
                        "user_id": user_id,
                        "content": s.content,
                        "audio_url": s.audio_url,
                        "duration": s.duration,
                        "phase": s.phase,
                        "created_at": s.timestamp.isoformat() if s.timestamp else None,
                    }
                )

            # 当前学生的总评分（若存在）
            my_score = None
            if participation:
                my_score = (
                    self.db.query(Score)
                    .filter(Score.participation_id == participation.id, Score.speech_id.is_(None))
                    .order_by(desc(Score.created_at))
                    .first()
                ) or (
                    self.db.query(Score)
                    .filter(Score.participation_id == participation.id)
                    .order_by(desc(Score.created_at))
                    .first()
                )

            # 参与者评分列表（尽量返回一条“总评”记录）
            score_rows = (
                self.db.query(Score, DebateParticipation)
                .join(DebateParticipation, DebateParticipation.id == Score.participation_id)
                .filter(DebateParticipation.debate_id == debate_id)
                .filter(Score.speech_id.is_(None))
                .order_by(desc(Score.created_at))
                .all()
            )

            scores: List[Dict[str, Any]] = []
            for sc, part in score_rows:
                if part.user_id:
                    user_id = str(part.user_id)
                else:
                    user_id = f"ai:{part.role}"
                scores.append(
                    {
                        "id": str(sc.id),
                        "debate_id": str(debate.id),
                        "user_id": user_id,
                        "logic": round(float(sc.logic_score), 2),
                        "expression": round(float(sc.persuasion_score), 2),
                        "rebuttal": round(float(sc.response_score), 2),
                        "teamwork": round(float(sc.teamwork_score), 2),
                        "knowledge": round(float(sc.argument_score), 2),
                        "total": round(float(sc.overall_score), 2),
                        "feedback": sc.feedback,
                        "created_at": sc.created_at.isoformat() if sc.created_at else None,
                    }
                )

            return {
                "debate": {
                    "id": str(debate.id),
                    "topic": debate.topic,
                    "description": debate.description,
                    "duration": debate.duration,
                    "status": debate.status,
                    "invitation_code": debate.invitation_code,
                    "created_at": debate.created_at.isoformat() if debate.created_at else None,
                },
                "participation": {
                    "role": participation.role if participation else None,
                    "stance": participation.stance if participation else None,
                    "score": round(float(my_score.overall_score), 2) if my_score else None,
                },
                "speeches": speech_items,
                "scores": scores,
            }
            
        except Exception as e:
            logger.error(f"Failed to get debate details: {e}", exc_info=True)
            raise
