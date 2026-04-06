"""
数据分析服务
提供数据看板和统计分析功能
"""
from logging_config import get_logger
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from models.user import User
from models.class_model import Class
from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech

logger = get_logger(__name__)


class AnalyticsService:
    """数据分析服务类"""
    
    def __init__(self, db: Session):
        """
        初始化数据分析服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    def get_class_statistics(self, class_id: str, teacher_id: str) -> Dict[str, Any]:
        """
        获取班级统计数据
        
        Args:
            class_id: 班级ID
            teacher_id: 教师ID（用于权限验证）
            
        Returns:
            班级统计数据
        """
        try:
            # 验证班级归属
            class_obj = self.db.query(Class).filter(
                and_(
                    Class.id == class_id,
                    Class.teacher_id == teacher_id
                )
            ).first()
            
            if not class_obj:
                raise ValueError("班级不存在或无权访问")
            
            # 获取班级学生数量
            student_count = self.db.query(User).filter(
                and_(
                    User.class_id == class_id,
                    User.user_type == "student"
                )
            ).count()
            
            # 获取班级辩论数量
            debate_count = self.db.query(Debate).filter(
                Debate.class_id == class_id
            ).count()
            
            # 获取已完成的辩论数量
            completed_debates = self.db.query(Debate).filter(
                and_(
                    Debate.class_id == class_id,
                    Debate.status == "completed"
                )
            ).count()
            
            # 计算完成率
            completion_rate = (completed_debates / debate_count * 100) if debate_count > 0 else 0
            
            # 获取学生参与统计
            participations = self.db.query(
                User.id,
                User.name,
                func.count(DebateParticipation.id).label("participation_count")
            ).join(
                DebateParticipation, User.id == DebateParticipation.user_id
            ).filter(
                User.class_id == class_id
            ).group_by(User.id, User.name).all()
            
            # 计算平均参与次数
            avg_participation = sum(p.participation_count for p in participations) / student_count if student_count > 0 else 0
            
            # 获取班级平均分
            avg_score = self.db.query(
                func.avg(Score.overall_score)
            ).join(
                DebateParticipation, Score.participation_id == DebateParticipation.id
            ).join(
                User, DebateParticipation.user_id == User.id
            ).filter(
                User.class_id == class_id
            ).scalar() or 0
            
            # 获取最近7天的活跃度
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            recent_debates = self.db.query(Debate).filter(
                and_(
                    Debate.class_id == class_id,
                    Debate.start_time >= seven_days_ago
                )
            ).count()
            
            return {
                "class_id": str(class_id),
                "class_name": class_obj.name,
                "student_count": student_count,
                "debate_count": debate_count,
                "completed_debates": completed_debates,
                "completion_rate": round(completion_rate, 2),
                "avg_participation": round(avg_participation, 2),
                "avg_score": round(float(avg_score), 2),
                "recent_activity": recent_debates,
                "updated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get class statistics: {e}", exc_info=True)
            raise
    
    def get_student_statistics(self, student_id: str) -> Dict[str, Any]:
        """
        获取学生统计数据
        
        Args:
            student_id: 学生ID
            
        Returns:
            学生统计数据
        """
        try:
            # 获取学生信息
            student = self.db.query(User).filter(
                and_(
                    User.id == student_id,
                    User.user_type == "student"
                )
            ).first()
            
            if not student:
                raise ValueError("学生不存在")
            
            # 获取参与次数
            participation_count = self.db.query(DebateParticipation).filter(
                DebateParticipation.user_id == student_id
            ).count()
            
            # 获取完成的辩论次数
            completed_count = self.db.query(DebateParticipation).join(
                Debate, DebateParticipation.debate_id == Debate.id
            ).filter(
                and_(
                    DebateParticipation.user_id == student_id,
                    Debate.status == "completed"
                )
            ).count()
            
            # 获取平均分
            avg_score = self.db.query(
                func.avg(Score.overall_score)
            ).join(
                DebateParticipation, Score.participation_id == DebateParticipation.id
            ).filter(
                DebateParticipation.user_id == student_id
            ).scalar() or 0
            
            # 获取五维能力平均分
            ability_scores = self.db.query(
                func.avg(Score.logic_score).label("logic"),
                func.avg(Score.argument_score).label("argument"),
                func.avg(Score.response_score).label("response"),
                func.avg(Score.persuasion_score).label("persuasion"),
                func.avg(Score.teamwork_score).label("teamwork")
            ).join(
                DebateParticipation, Score.participation_id == DebateParticipation.id
            ).filter(
                DebateParticipation.user_id == student_id
            ).first()
            
            # 获取发言统计
            speech_stats = self.db.query(
                func.count(Speech.id).label("speech_count"),
                func.sum(Speech.duration).label("total_duration")
            ).join(
                Debate, Speech.debate_id == Debate.id
            ).filter(
                and_(
                    Speech.speaker_id == student_id,
                    Speech.speaker_type == "human"
                )
            ).first()
            
            # 获取角色分布
            role_distribution = self.db.query(
                DebateParticipation.role,
                func.count(DebateParticipation.id).label("count")
            ).filter(
                DebateParticipation.user_id == student_id
            ).group_by(DebateParticipation.role).all()
            
            # 获取立场分布
            stance_distribution = self.db.query(
                DebateParticipation.stance,
                func.count(DebateParticipation.id).label("count")
            ).filter(
                DebateParticipation.user_id == student_id
            ).group_by(DebateParticipation.stance).all()
            
            return {
                "total_debates": participation_count,
                "completed_debates": completed_count,
                "average_score": round(float(avg_score), 2),
                "ability_scores": {
                    "logic": round(float(ability_scores.logic or 0), 2),
                    "expression": round(float(ability_scores.argument or 0), 2),
                    "rebuttal": round(float(ability_scores.response or 0), 2),
                    "knowledge": round(float(ability_scores.persuasion or 0), 2),
                    "teamwork": round(float(ability_scores.teamwork or 0), 2)
                },
                "speech_stats": {
                    "total_speeches": speech_stats.speech_count or 0,
                    "average_duration": round((speech_stats.total_duration or 0) / (speech_stats.speech_count or 1), 2)
                },
                "role_distribution": {
                    role.role: role.count for role in role_distribution
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get student statistics: {e}", exc_info=True)
            raise
    
    def get_completion_rate(self, class_id: str) -> Dict[str, Any]:
        """
        获取班级完成率统计
        
        Args:
            class_id: 班级ID
            
        Returns:
            完成率统计
        """
        try:
            # 获取所有学生
            students = self.db.query(User).filter(
                and_(
                    User.class_id == class_id,
                    User.user_type == "student"
                )
            ).all()
            
            # 获取班级所有辩论
            total_debates = self.db.query(Debate).filter(
                Debate.class_id == class_id
            ).count()
            
            if total_debates == 0:
                return {
                    "class_id": str(class_id),
                    "total_debates": 0,
                    "student_completion": [],
                    "avg_completion_rate": 0
                }
            
            # 统计每个学生的完成情况
            student_completion = []
            for student in students:
                completed = self.db.query(DebateParticipation).join(
                    Debate, DebateParticipation.debate_id == Debate.id
                ).filter(
                    and_(
                        DebateParticipation.user_id == student.id,
                        Debate.status == "completed"
                    )
                ).count()
                
                completion_rate = (completed / total_debates * 100)
                
                student_completion.append({
                    "student_id": str(student.id),
                    "student_name": student.name,
                    "completed": completed,
                    "total": total_debates,
                    "completion_rate": round(completion_rate, 2)
                })
            
            # 计算平均完成率
            avg_completion_rate = sum(s["completion_rate"] for s in student_completion) / len(students) if students else 0
            
            return {
                "class_id": str(class_id),
                "total_debates": total_debates,
                "student_completion": student_completion,
                "avg_completion_rate": round(avg_completion_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get completion rate: {e}", exc_info=True)
            raise
    
    def get_average_score(self, class_id: str) -> Dict[str, Any]:
        """
        获取班级平均分统计
        
        Args:
            class_id: 班级ID
            
        Returns:
            平均分统计
        """
        try:
            # 获取班级所有学生的平均分
            student_scores = self.db.query(
                User.id,
                User.name,
                func.avg(Score.overall_score).label("avg_score"),
                func.avg(Score.logic_score).label("logic"),
                func.avg(Score.argument_score).label("argument"),
                func.avg(Score.response_score).label("response"),
                func.avg(Score.persuasion_score).label("persuasion"),
                func.avg(Score.teamwork_score).label("teamwork")
            ).join(
                DebateParticipation, User.id == DebateParticipation.user_id
            ).join(
                Score, DebateParticipation.id == Score.participation_id
            ).filter(
                User.class_id == class_id
            ).group_by(User.id, User.name).all()
            
            # 计算班级总平均分
            class_avg = sum(s.avg_score or 0 for s in student_scores) / len(student_scores) if student_scores else 0
            
            # 计算五维能力班级平均
            class_ability_avg = {
                "logic": sum(s.logic or 0 for s in student_scores) / len(student_scores) if student_scores else 0,
                "argument": sum(s.argument or 0 for s in student_scores) / len(student_scores) if student_scores else 0,
                "response": sum(s.response or 0 for s in student_scores) / len(student_scores) if student_scores else 0,
                "persuasion": sum(s.persuasion or 0 for s in student_scores) / len(student_scores) if student_scores else 0,
                "teamwork": sum(s.teamwork or 0 for s in student_scores) / len(student_scores) if student_scores else 0
            }
            
            return {
                "class_id": str(class_id),
                "class_avg_score": round(float(class_avg), 2),
                "class_ability_avg": {
                    k: round(float(v), 2) for k, v in class_ability_avg.items()
                },
                "student_scores": [
                    {
                        "student_id": str(s.id),
                        "student_name": s.name,
                        "avg_score": round(float(s.avg_score or 0), 2),
                        "ability_scores": {
                            "logic": round(float(s.logic or 0), 2),
                            "argument": round(float(s.argument or 0), 2),
                            "response": round(float(s.response or 0), 2),
                            "persuasion": round(float(s.persuasion or 0), 2),
                            "teamwork": round(float(s.teamwork or 0), 2)
                        }
                    }
                    for s in student_scores
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get average score: {e}", exc_info=True)
            raise
    
    def get_growth_trend(self, student_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        获取学生成长趋势
        
        Args:
            student_id: 学生ID
            limit: 返回最近N场辩论的数据
            
        Returns:
            成长趋势数据
        """
        try:
            # 获取学生最近的辩论记录和评分
            debates_with_scores = self.db.query(
                Debate.id,
                Debate.topic,
                Debate.start_time,
                Score.overall_score,
                Score.logic_score,
                Score.argument_score,
                Score.response_score,
                Score.persuasion_score,
                Score.teamwork_score
            ).join(
                DebateParticipation, Debate.id == DebateParticipation.debate_id
            ).join(
                Score, DebateParticipation.id == Score.participation_id
            ).filter(
                DebateParticipation.user_id == student_id
            ).order_by(Debate.start_time.desc()).limit(limit).all()
            
            # 反转顺序（从旧到新）
            debates_with_scores = list(reversed(debates_with_scores))
            
            return {
                "debates": [
                    {
                        "debate_id": str(d.id),
                        "topic": d.topic,
                        "date": d.start_time.isoformat() if d.start_time else None,
                        "score": round(float(d.overall_score), 2),
                        "ability_scores": {
                            "logic": round(float(d.logic_score), 2),
                            "expression": round(float(d.argument_score), 2),
                            "rebuttal": round(float(d.response_score), 2),
                            "knowledge": round(float(d.persuasion_score), 2),
                            "teamwork": round(float(d.teamwork_score), 2)
                        }
                    }
                    for d in debates_with_scores
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get growth trend: {e}", exc_info=True)
            raise
