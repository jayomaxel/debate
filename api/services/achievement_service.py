"""
成就管理服务
提供成就解锁、查询和管理功能
"""
from logging_config import get_logger
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from models.user import User
from models.achievement import Achievement
from models.debate import Debate, DebateParticipation
from models.score import Score

logger = get_logger(__name__)


# 成就类型定义
ACHIEVEMENT_TYPES = {
    "first_debate": {
        "title": "初出茅庐",
        "description": "完成首场辩论",
        "icon": "🎯",
        "category": "milestone"
    },
    "win_streak_3": {
        "title": "连胜之星",
        "description": "连续获胜3场辩论",
        "icon": "🌟",
        "category": "performance"
    },
    "win_streak_5": {
        "title": "连胜大师",
        "description": "连续获胜5场辩论",
        "icon": "👑",
        "category": "performance"
    },
    "mvp": {
        "title": "全场最佳",
        "description": "获得MVP称号",
        "icon": "🏆",
        "category": "performance"
    },
    "logic_master": {
        "title": "逻辑大师",
        "description": "逻辑建构力评分达到90分",
        "icon": "🧠",
        "category": "ability"
    },
    "argument_master": {
        "title": "知识达人",
        "description": "AI核心知识运用评分达到90分",
        "icon": "📚",
        "category": "ability"
    },
    "response_master": {
        "title": "思辨先锋",
        "description": "批判性思维评分达到90分",
        "icon": "⚡",
        "category": "ability"
    },
    "persuasion_master": {
        "title": "表达大师",
        "description": "语言表达力评分达到90分",
        "icon": "💬",
        "category": "ability"
    },
    "teamwork_master": {
        "title": "伦理之光",
        "description": "AI伦理与科技素养评分达到90分",
        "icon": "🤝",
        "category": "ability"
    },
    "debate_10": {
        "title": "辩论达人",
        "description": "完成10场辩论",
        "icon": "🎓",
        "category": "milestone"
    },
    "debate_50": {
        "title": "辩论专家",
        "description": "完成50场辩论",
        "icon": "🎖️",
        "category": "milestone"
    },
    "perfect_score": {
        "title": "完美表现",
        "description": "单场辩论获得满分100分",
        "icon": "💯",
        "category": "performance"
    },
    "high_scorer": {
        "title": "高分选手",
        "description": "平均分达到85分",
        "icon": "📈",
        "category": "performance"
    }
}


class AchievementService:
    """成就管理服务类"""
    
    def __init__(self, db: Session):
        """
        初始化成就管理服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    def check_achievements(self, user_id: str) -> List[str]:
        """
        检查学生是否满足成就解锁条件
        
        Args:
            user_id: 学生ID
            
        Returns:
            新解锁的成就类型列表
        """
        try:
            newly_unlocked = []
            
            # 获取已解锁的成就
            unlocked_achievements = self.db.query(Achievement.achievement_type).filter(
                Achievement.user_id == user_id
            ).all()
            unlocked_types = {a.achievement_type for a in unlocked_achievements}
            
            # 检查各种成就条件
            
            # 1. 首场辩论
            if "first_debate" not in unlocked_types:
                debate_count = self.db.query(DebateParticipation).join(
                    Debate, DebateParticipation.debate_id == Debate.id
                ).filter(
                    and_(
                        DebateParticipation.user_id == user_id,
                        Debate.status == "completed"
                    )
                ).count()
                
                if debate_count >= 1:
                    self.unlock_achievement(user_id, "first_debate")
                    newly_unlocked.append("first_debate")
            
            # 2. 完成10场辩论
            if "debate_10" not in unlocked_types:
                debate_count = self.db.query(DebateParticipation).join(
                    Debate, DebateParticipation.debate_id == Debate.id
                ).filter(
                    and_(
                        DebateParticipation.user_id == user_id,
                        Debate.status == "completed"
                    )
                ).count()
                
                if debate_count >= 10:
                    self.unlock_achievement(user_id, "debate_10")
                    newly_unlocked.append("debate_10")
            
            # 3. 完成50场辩论
            if "debate_50" not in unlocked_types:
                debate_count = self.db.query(DebateParticipation).join(
                    Debate, DebateParticipation.debate_id == Debate.id
                ).filter(
                    and_(
                        DebateParticipation.user_id == user_id,
                        Debate.status == "completed"
                    )
                ).count()
                
                if debate_count >= 50:
                    self.unlock_achievement(user_id, "debate_50")
                    newly_unlocked.append("debate_50")
            
            # 4. 检查五维能力成就（达到90分）
            ability_achievements = {
                "logic_master": "logic_score",
                "argument_master": "argument_score",
                "response_master": "response_score",
                "persuasion_master": "persuasion_score",
                "teamwork_master": "teamwork_score"
            }
            
            for achievement_type, score_field in ability_achievements.items():
                if achievement_type not in unlocked_types:
                    max_score = self.db.query(
                        func.max(getattr(Score, score_field))
                    ).join(
                        DebateParticipation, Score.participation_id == DebateParticipation.id
                    ).filter(
                        DebateParticipation.user_id == user_id
                    ).scalar()
                    
                    if max_score and max_score >= 90:
                        self.unlock_achievement(user_id, achievement_type)
                        newly_unlocked.append(achievement_type)
            
            # 5. 完美表现（单场100分）
            if "perfect_score" not in unlocked_types:
                perfect_score = self.db.query(Score).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    and_(
                        DebateParticipation.user_id == user_id,
                        Score.overall_score >= 100
                    )
                ).first()
                
                if perfect_score:
                    self.unlock_achievement(user_id, "perfect_score")
                    newly_unlocked.append("perfect_score")
            
            # 6. 高分选手（平均分85+）
            if "high_scorer" not in unlocked_types:
                avg_score = self.db.query(
                    func.avg(Score.overall_score)
                ).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    DebateParticipation.user_id == user_id
                ).scalar()
                
                if avg_score and avg_score >= 85:
                    self.unlock_achievement(user_id, "high_scorer")
                    newly_unlocked.append("high_scorer")
            
            # 7. 连胜成就（需要检查最近的辩论结果）
            if "win_streak_3" not in unlocked_types or "win_streak_5" not in unlocked_types:
                win_streak = self._check_win_streak(user_id)
                
                if win_streak >= 3 and "win_streak_3" not in unlocked_types:
                    self.unlock_achievement(user_id, "win_streak_3")
                    newly_unlocked.append("win_streak_3")
                
                if win_streak >= 5 and "win_streak_5" not in unlocked_types:
                    self.unlock_achievement(user_id, "win_streak_5")
                    newly_unlocked.append("win_streak_5")
            
            # 8. MVP成就（需要在辩论中获得最高分）
            if "mvp" not in unlocked_types:
                mvp_count = self._check_mvp_count(user_id)
                if mvp_count >= 1:
                    self.unlock_achievement(user_id, "mvp")
                    newly_unlocked.append("mvp")
            
            return newly_unlocked
            
        except Exception as e:
            logger.error(f"Failed to check achievements: {e}", exc_info=True)
            return []

    
    def _check_win_streak(self, user_id: str) -> int:
        """
        检查学生的连胜记录
        
        Args:
            user_id: 学生ID
            
        Returns:
            当前连胜场数
        """
        try:
            # 获取学生最近的辩论记录（按时间倒序）
            recent_debates = self.db.query(
                Debate.id,
                Score.overall_score,
                DebateParticipation.stance
            ).join(
                DebateParticipation, Debate.id == DebateParticipation.debate_id
            ).join(
                Score, DebateParticipation.id == Score.participation_id
            ).filter(
                and_(
                    DebateParticipation.user_id == user_id,
                    Debate.status == "completed"
                )
            ).order_by(Debate.end_time.desc()).limit(10).all()
            
            if not recent_debates:
                return 0
            
            # 计算连胜
            win_streak = 0
            for debate in recent_debates:
                # 获取该场辩论中同立场队伍的平均分
                team_avg = self.db.query(
                    func.avg(Score.overall_score)
                ).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    and_(
                        DebateParticipation.debate_id == debate.id,
                        DebateParticipation.stance == debate.stance
                    )
                ).scalar() or 0
                
                # 获取对方队伍的平均分
                opponent_avg = self.db.query(
                    func.avg(Score.overall_score)
                ).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    and_(
                        DebateParticipation.debate_id == debate.id,
                        DebateParticipation.stance != debate.stance
                    )
                ).scalar() or 0
                
                # 判断是否获胜
                if team_avg > opponent_avg:
                    win_streak += 1
                else:
                    break
            
            return win_streak
            
        except Exception as e:
            logger.error(f"Failed to check win streak: {e}", exc_info=True)
            return 0
    
    def _check_mvp_count(self, user_id: str) -> int:
        """
        检查学生获得MVP的次数
        
        Args:
            user_id: 学生ID
            
        Returns:
            MVP次数
        """
        try:
            # 获取学生参与的所有辩论
            participations = self.db.query(
                DebateParticipation.debate_id,
                Score.overall_score
            ).join(
                Score, DebateParticipation.id == Score.participation_id
            ).filter(
                DebateParticipation.user_id == user_id
            ).all()
            
            mvp_count = 0
            
            for participation in participations:
                # 获取该场辩论的最高分
                max_score = self.db.query(
                    func.max(Score.overall_score)
                ).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    DebateParticipation.debate_id == participation.debate_id
                ).scalar()
                
                # 如果学生得分等于最高分，则为MVP
                if participation.overall_score == max_score:
                    mvp_count += 1
            
            return mvp_count
            
        except Exception as e:
            logger.error(f"Failed to check MVP count: {e}", exc_info=True)
            return 0
    
    def unlock_achievement(self, user_id: str, achievement_type: str) -> bool:
        """
        解锁成就
        
        Args:
            user_id: 学生ID
            achievement_type: 成就类型
            
        Returns:
            是否成功解锁
        """
        try:
            # 检查成就类型是否有效
            if achievement_type not in ACHIEVEMENT_TYPES:
                logger.warning(f"Invalid achievement type: {achievement_type}")
                return False
            
            # 检查是否已解锁
            existing = self.db.query(Achievement).filter(
                and_(
                    Achievement.user_id == user_id,
                    Achievement.achievement_type == achievement_type
                )
            ).first()
            
            if existing:
                logger.info(f"Achievement {achievement_type} already unlocked for user {user_id}")
                return False
            
            # 创建成就记录
            achievement_info = ACHIEVEMENT_TYPES[achievement_type]
            achievement = Achievement(
                user_id=user_id,
                achievement_type=achievement_type,
                title=achievement_info["title"],
                description=achievement_info["description"],
                icon=achievement_info["icon"],
                unlocked_at=datetime.utcnow()
            )
            
            self.db.add(achievement)
            self.db.commit()
            
            logger.info(f"Achievement {achievement_type} unlocked for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unlock achievement: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    def get_achievements(self, user_id: str) -> Dict[str, Any]:
        """
        获取学生的成就列表
        
        Args:
            user_id: 学生ID
            
        Returns:
            成就列表（包含已解锁和未解锁）
        """
        try:
            # 获取已解锁的成就
            unlocked = self.db.query(Achievement).filter(
                Achievement.user_id == user_id
            ).order_by(Achievement.unlocked_at.desc()).all()
            
            unlocked_types = {a.achievement_type for a in unlocked}
            
            # 构建成就列表
            achievements = {
                "unlocked": [],
                "locked": [],
                "stats": {
                    "total": len(ACHIEVEMENT_TYPES),
                    "unlocked_count": len(unlocked),
                    "progress": round(len(unlocked) / len(ACHIEVEMENT_TYPES) * 100, 2)
                }
            }
            
            # 添加已解锁的成就
            for achievement in unlocked:
                achievements["unlocked"].append({
                    "id": str(achievement.id),
                    "type": achievement.achievement_type,
                    "title": achievement.title,
                    "description": achievement.description,
                    "icon": achievement.icon,
                    "category": ACHIEVEMENT_TYPES.get(achievement.achievement_type, {}).get("category", "other"),
                    "unlocked_at": achievement.unlocked_at.isoformat()
                })
            
            # 添加未解锁的成就
            for achievement_type, info in ACHIEVEMENT_TYPES.items():
                if achievement_type not in unlocked_types:
                    achievements["locked"].append({
                        "type": achievement_type,
                        "title": info["title"],
                        "description": info["description"],
                        "icon": "🔒",  # 未解锁显示锁图标
                        "category": info["category"],
                        "unlock_hint": self._get_unlock_hint(user_id, achievement_type)
                    })
            
            return achievements
            
        except Exception as e:
            logger.error(f"Failed to get achievements: {e}", exc_info=True)
            raise

    def get_achievements_v2(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            unlocked = self.db.query(Achievement).filter(
                Achievement.user_id == user_id
            ).order_by(Achievement.unlocked_at.desc()).all()

            unlocked_by_type = {a.achievement_type: a for a in unlocked}

            items: List[Dict[str, Any]] = []
            for achievement_type, info in ACHIEVEMENT_TYPES.items():
                unlocked_row = unlocked_by_type.get(achievement_type)
                unlocked_flag = unlocked_row is not None
                progress_target = self._get_unlock_progress(user_id, achievement_type) if not unlocked_flag else None

                item: Dict[str, Any] = {
                    "id": str(unlocked_row.id) if unlocked_flag else f"locked-{achievement_type}",
                    "type": achievement_type,
                    "name": info["title"],
                    "description": info["description"],
                    "category": info.get("category", "other"),
                    "icon": info.get("icon", "🏅"),
                    "unlocked": unlocked_flag,
                }

                if unlocked_flag:
                    item["unlocked_at"] = unlocked_row.unlocked_at.isoformat() if unlocked_row.unlocked_at else None
                else:
                    hint = self._get_unlock_hint(user_id, achievement_type)
                    if hint:
                        item["unlock_hint"] = hint
                    if progress_target is not None:
                        progress, target = progress_target
                        item["progress"] = progress
                        item["target"] = target

                items.append(item)

            return items
        except Exception as e:
            logger.error(f"Failed to get achievements v2: {e}", exc_info=True)
            raise

    def get_newly_unlocked_items_v2(self, user_id: str, types: List[str]) -> List[Dict[str, Any]]:
        if not types:
            return []

        try:
            rows = self.db.query(Achievement).filter(
                and_(
                    Achievement.user_id == user_id,
                    Achievement.achievement_type.in_(types)
                )
            ).order_by(Achievement.unlocked_at.desc()).all()

            result: List[Dict[str, Any]] = []
            for row in rows:
                info = ACHIEVEMENT_TYPES.get(row.achievement_type, {})
                result.append({
                    "id": str(row.id),
                    "type": row.achievement_type,
                    "name": row.title or info.get("title", row.achievement_type),
                    "description": row.description or info.get("description", ""),
                    "category": info.get("category", "other"),
                    "icon": info.get("icon", row.icon or "🏅"),
                    "unlocked": True,
                    "unlocked_at": row.unlocked_at.isoformat() if row.unlocked_at else None,
                })

            return result
        except Exception as e:
            logger.error(f"Failed to get newly unlocked items v2: {e}", exc_info=True)
            return []
    
    def _get_unlock_hint(self, user_id: str, achievement_type: str) -> str:
        """
        获取成就解锁提示
        
        Args:
            user_id: 学生ID
            achievement_type: 成就类型
            
        Returns:
            解锁提示文本
        """
        try:
            if achievement_type == "first_debate":
                return "完成你的第一场辩论"
            
            elif achievement_type == "debate_10":
                count = self.db.query(DebateParticipation).join(
                    Debate, DebateParticipation.debate_id == Debate.id
                ).filter(
                    and_(
                        DebateParticipation.user_id == user_id,
                        Debate.status == "completed"
                    )
                ).count()
                return f"已完成 {count}/10 场辩论"
            
            elif achievement_type == "debate_50":
                count = self.db.query(DebateParticipation).join(
                    Debate, DebateParticipation.debate_id == Debate.id
                ).filter(
                    and_(
                        DebateParticipation.user_id == user_id,
                        Debate.status == "completed"
                    )
                ).count()
                return f"已完成 {count}/50 场辩论"
            
            elif achievement_type in ["logic_master", "argument_master", "response_master", 
                                     "persuasion_master", "teamwork_master"]:
                score_field_map = {
                    "logic_master": "logic_score",
                    "argument_master": "argument_score",
                    "response_master": "response_score",
                    "persuasion_master": "persuasion_score",
                    "teamwork_master": "teamwork_score"
                }
                score_field = score_field_map[achievement_type]
                
                max_score = self.db.query(
                    func.max(getattr(Score, score_field))
                ).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    DebateParticipation.user_id == user_id
                ).scalar() or 0
                
                return f"最高分: {round(max_score, 1)}/90"
            
            elif achievement_type == "win_streak_3":
                streak = self._check_win_streak(user_id)
                return f"当前连胜: {streak}/3"
            
            elif achievement_type == "win_streak_5":
                streak = self._check_win_streak(user_id)
                return f"当前连胜: {streak}/5"
            
            elif achievement_type == "mvp":
                return "在任意一场辩论中获得最高分"
            
            elif achievement_type == "perfect_score":
                max_score = self.db.query(
                    func.max(Score.overall_score)
                ).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    DebateParticipation.user_id == user_id
                ).scalar() or 0
                return f"最高分: {round(max_score, 1)}/100"
            
            elif achievement_type == "high_scorer":
                avg_score = self.db.query(
                    func.avg(Score.overall_score)
                ).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    DebateParticipation.user_id == user_id
                ).scalar() or 0
                return f"平均分: {round(avg_score, 1)}/85"
            
            else:
                return "继续努力解锁此成就"
                
        except Exception as e:
            logger.error(f"Failed to get unlock hint: {e}", exc_info=True)
            return "继续努力解锁此成就"

    def _get_unlock_progress(self, user_id: str, achievement_type: str) -> Optional[tuple]:
        try:
            if achievement_type == "first_debate":
                count = self.db.query(DebateParticipation).join(
                    Debate, DebateParticipation.debate_id == Debate.id
                ).filter(
                    and_(
                        DebateParticipation.user_id == user_id,
                        Debate.status == "completed"
                    )
                ).count()
                return (min(count, 1), 1)

            if achievement_type == "debate_10":
                count = self.db.query(DebateParticipation).join(
                    Debate, DebateParticipation.debate_id == Debate.id
                ).filter(
                    and_(
                        DebateParticipation.user_id == user_id,
                        Debate.status == "completed"
                    )
                ).count()
                return (count, 10)

            if achievement_type == "debate_50":
                count = self.db.query(DebateParticipation).join(
                    Debate, DebateParticipation.debate_id == Debate.id
                ).filter(
                    and_(
                        DebateParticipation.user_id == user_id,
                        Debate.status == "completed"
                    )
                ).count()
                return (count, 50)

            if achievement_type in ["logic_master", "argument_master", "response_master",
                                    "persuasion_master", "teamwork_master"]:
                score_field_map = {
                    "logic_master": "logic_score",
                    "argument_master": "argument_score",
                    "response_master": "response_score",
                    "persuasion_master": "persuasion_score",
                    "teamwork_master": "teamwork_score"
                }
                score_field = score_field_map.get(achievement_type)
                if not score_field:
                    return None
                max_score = self.db.query(
                    func.max(getattr(Score, score_field))
                ).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    DebateParticipation.user_id == user_id
                ).scalar() or 0
                return (round(float(max_score), 1), 90)

            if achievement_type == "win_streak_3":
                streak = self._check_win_streak(user_id)
                return (streak, 3)

            if achievement_type == "win_streak_5":
                streak = self._check_win_streak(user_id)
                return (streak, 5)

            if achievement_type == "mvp":
                mvp_count = self._check_mvp_count(user_id)
                return (min(mvp_count, 1), 1)

            if achievement_type == "perfect_score":
                max_score = self.db.query(
                    func.max(Score.overall_score)
                ).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    DebateParticipation.user_id == user_id
                ).scalar() or 0
                return (round(float(max_score), 1), 100)

            if achievement_type == "high_scorer":
                avg_score = self.db.query(
                    func.avg(Score.overall_score)
                ).join(
                    DebateParticipation, Score.participation_id == DebateParticipation.id
                ).filter(
                    DebateParticipation.user_id == user_id
                ).scalar() or 0
                return (round(float(avg_score), 1), 85)

            return None
        except Exception as e:
            logger.error(f"Failed to get unlock progress: {e}", exc_info=True)
            return None
