from logging_config import get_logger
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from models.user import User
from models.class_model import Class
from models.debate import Debate, DebateParticipation
from models.score import Score

logger = get_logger(__name__)


class ComparisonService:
    def __init__(self, db: Session):
        self.db = db

    def get_class_comparison(self, student_id: str, metric: str = "overall", top: int = 10) -> Dict[str, Any]:
        if top <= 0:
            top = 10
        top = min(top, 50)

        metric_field_map = {
            "overall": "avg_overall",
            "logic": "avg_logic",
            "argument": "avg_argument",
            "response": "avg_response",
            "persuasion": "avg_persuasion",
            "teamwork": "avg_teamwork",
        }

        if metric not in metric_field_map:
            raise ValueError("不支持的对比指标")

        try:
            student: Optional[User] = self.db.query(User).filter(
                and_(
                    User.id == student_id,
                    User.user_type == "student"
                )
            ).first()

            if not student:
                raise ValueError("学生不存在")

            if not student.class_id:
                raise ValueError("当前账号未加入班级，无法进行班级对比")

            class_obj: Optional[Class] = self.db.query(Class).filter(Class.id == student.class_id).first()

            student_scores = self.db.query(
                User.id.label("student_id"),
                User.name.label("student_name"),
                func.avg(Score.overall_score).label("avg_overall"),
                func.avg(Score.logic_score).label("avg_logic"),
                func.avg(Score.argument_score).label("avg_argument"),
                func.avg(Score.response_score).label("avg_response"),
                func.avg(Score.persuasion_score).label("avg_persuasion"),
                func.avg(Score.teamwork_score).label("avg_teamwork"),
            ).join(
                DebateParticipation, User.id == DebateParticipation.user_id
            ).join(
                Debate, DebateParticipation.debate_id == Debate.id
            ).join(
                Score, DebateParticipation.id == Score.participation_id
            ).filter(
                and_(
                    User.user_type == "student",
                    User.class_id == student.class_id,
                    Debate.status == "completed"
                )
            ).group_by(User.id, User.name).all()

            if not student_scores:
                return {
                    "class_id": str(student.class_id),
                    "class_name": class_obj.name if class_obj else "",
                    "metric": metric,
                    "my": None,
                    "class_avg": None,
                    "leaderboard": [],
                    "sample_size": 0
                }

            class_avg_row = self.db.query(
                func.avg(Score.overall_score).label("avg_overall"),
                func.avg(Score.logic_score).label("avg_logic"),
                func.avg(Score.argument_score).label("avg_argument"),
                func.avg(Score.response_score).label("avg_response"),
                func.avg(Score.persuasion_score).label("avg_persuasion"),
                func.avg(Score.teamwork_score).label("avg_teamwork"),
            ).join(
                DebateParticipation, Score.participation_id == DebateParticipation.id
            ).join(
                User, DebateParticipation.user_id == User.id
            ).join(
                Debate, DebateParticipation.debate_id == Debate.id
            ).filter(
                and_(
                    User.user_type == "student",
                    User.class_id == student.class_id,
                    Debate.status == "completed"
                )
            ).first()

            metric_field = metric_field_map[metric]
            sorted_scores = sorted(
                student_scores,
                key=lambda s: float(getattr(s, metric_field) or 0),
                reverse=True
            )

            sample_size = len(sorted_scores)
            my_rank = None
            my_row = None
            for idx, row in enumerate(sorted_scores):
                if str(row.student_id) == str(student.id):
                    my_rank = idx + 1
                    my_row = row
                    break

            def normalize_ability(row: Any) -> Dict[str, float]:
                return {
                    "logic": round(float(row.avg_logic or 0), 2),
                    "argument": round(float(row.avg_argument or 0), 2),
                    "response": round(float(row.avg_response or 0), 2),
                    "persuasion": round(float(row.avg_persuasion or 0), 2),
                    "teamwork": round(float(row.avg_teamwork or 0), 2),
                }

            leaderboard: List[Dict[str, Any]] = []
            for idx, row in enumerate(sorted_scores[:top]):
                leaderboard.append({
                    "rank": idx + 1,
                    "student_id": str(row.student_id),
                    "student_name": row.student_name,
                    "score": round(float(getattr(row, metric_field) or 0), 2),
                    "overall_score": round(float(row.avg_overall or 0), 2),
                    "ability_scores": normalize_ability(row),
                })

            percentile = None
            if my_rank is not None and sample_size > 0:
                percentile = round(((sample_size - my_rank + 1) / sample_size) * 100, 2)

            my_payload = None
            if my_row is not None:
                my_payload = {
                    "student_id": str(my_row.student_id),
                    "student_name": my_row.student_name,
                    "rank": my_rank,
                    "percentile": percentile,
                    "score": round(float(getattr(my_row, metric_field) or 0), 2),
                    "overall_score": round(float(my_row.avg_overall or 0), 2),
                    "ability_scores": normalize_ability(my_row),
                }

            class_avg = None
            if class_avg_row is not None:
                class_avg = {
                    "score": round(float(getattr(class_avg_row, metric_field) or 0), 2),
                    "overall_score": round(float(class_avg_row.avg_overall or 0), 2),
                    "ability_scores": {
                        "logic": round(float(class_avg_row.avg_logic or 0), 2),
                        "argument": round(float(class_avg_row.avg_argument or 0), 2),
                        "response": round(float(class_avg_row.avg_response or 0), 2),
                        "persuasion": round(float(class_avg_row.avg_persuasion or 0), 2),
                        "teamwork": round(float(class_avg_row.avg_teamwork or 0), 2),
                    }
                }

            return {
                "class_id": str(student.class_id),
                "class_name": class_obj.name if class_obj else "",
                "metric": metric,
                "my": my_payload,
                "class_avg": class_avg,
                "leaderboard": leaderboard,
                "sample_size": sample_size
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to get class comparison: {e}", exc_info=True)
            raise
