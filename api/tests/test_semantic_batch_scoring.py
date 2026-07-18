import uuid
from datetime import datetime

import pytest

from agents.judge_agent import JudgeAgent
from models.debate import Debate, DebateParticipation
from models.score import Score
from models.speech import Speech
from models.user import User
from services.scoring_service import ScoringService


@pytest.mark.asyncio
async def test_batch_scoring_uses_judge_semantics_without_keyword_bonus(db_session, monkeypatch):
    student = User(
        id=uuid.uuid4(),
        account="semantic_score_student",
        name="Semantic Score Student",
        email="semantic_score_student@test.com",
        password_hash="hashed_password",
        user_type="student",
        created_at=datetime.utcnow(),
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="人工智能是否应进入课堂",
        description="",
        duration=5,
        invitation_code="SEM001",
        status="completed",
    )
    participation = DebateParticipation(
        id=uuid.uuid4(),
        debate_id=debate.id,
        user_id=student.id,
        role="debater_1",
        stance="positive",
    )
    speech = Speech(
        id=uuid.uuid4(),
        debate_id=debate.id,
        speaker_id=student.id,
        speaker_type="human",
        speaker_role="debater_1",
        phase="opening",
        content="数据显示，人工智能和大模型可以辅助个性化学习。",
        duration=12,
        is_valid_for_scoring=True,
        timestamp=datetime.utcnow(),
    )
    db_session.add_all([student, debate, participation, speech])
    db_session.commit()

    captured_context = []

    async def fake_batch_evaluate(self, context):
        captured_context.extend(context)
        return {
            "speech_scores": [
                {
                    "speech_id": str(speech.id),
                    "scores": {
                        "logic_score": 81,
                        "argument_score": 79,
                        "response_score": 75,
                        "persuasion_score": 78,
                        "teamwork_score": 80,
                        "overall_score": 77,
                        "feedback": "模型根据论点与证据关系完成评分。",
                        "report_meta": {
                            "scoring_source": "judge_model",
                            "scoring_quality": "validated",
                            "provider": "llm",
                            "mode": "competition",
                        },
                    },
                    "violations": [],
                }
            ],
            "global_report": {
                "winner": "positive",
                "winning_reason": "正方论证更完整。",
                "scores": {"positive": {"total_score": 77}, "negative": {"total_score": 70}},
                "overall_comment": "模型基于完整转写给出结论。",
                "suggestions": [],
            },
            "report_meta": {
                "scoring_source": "judge_model",
                "scoring_quality": "validated",
                "provider": "llm",
                "mode": "competition",
            },
            "anomaly_samples": [],
            "calibration_summary": {"calibration_version": "a.calibration.v1", "sample_count": 0},
        }

    monkeypatch.setattr(JudgeAgent, "batch_evaluate_debate", fake_batch_evaluate)

    status = await ScoringService.ensure_debate_scored(db_session, str(debate.id))
    saved_score = db_session.query(Score).filter(Score.speech_id == speech.id).one()
    db_session.refresh(debate)

    assert status["ready"] is True
    assert captured_context[0]["topic"] == debate.topic
    assert saved_score.overall_score == 77
    assert "关键词加分" not in saved_score.feedback
    assert debate.report["report_meta"]["scoring_source"] == "judge_model"
    assert debate.report["report_meta"]["provider"] == "llm"
    assert debate.report["score_generation_mode"] == "semantic_judge"
    assert not hasattr(ScoringService, "calculate_keyword_bonus")

