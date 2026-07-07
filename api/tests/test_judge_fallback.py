import asyncio
from types import SimpleNamespace

from agents.judge_agent import JudgeAgent
from services.score_validation_service import ScoreValidationService


def test_judge_fallback_chain_prefers_valid_output_before_repair():
    raw = {
        "logic_score": 81,
        "argument_score": 82,
        "response_score": 83,
        "persuasion_score": 84,
        "teamwork_score": 85,
        "overall_score": 83,
        "feedback": "有效输出应直接采用。",
    }

    result = ScoreValidationService.validate_or_fallback(str(raw).replace("'", '"'))

    assert result.scoring_quality == "validated"
    assert result.report_meta.retry_count == 0
    assert result.payload["feedback"] == "有效输出应直接采用。"


def test_judge_fallback_chain_uses_repair_before_fallback():
    repaired = """
    {
      "logic_score": 66,
      "argument_score": 67,
      "response_score": 68,
      "persuasion_score": 69,
      "teamwork_score": 70,
      "overall_score": 68,
      "feedback": "修复链路成功。"
    }
    """

    result = ScoreValidationService.validate_or_fallback(
        "bad judge output",
        repaired_text=repaired,
    )

    assert result.scoring_quality == "repaired"
    assert result.report_meta.scoring_source == "judge_model"
    assert result.payload["overall_score"] == 68


def test_judge_fallback_is_never_marked_as_validated():
    result = ScoreValidationService.validate_or_fallback(
        "bad judge output",
        repaired_text="bad repaired output",
    )

    assert result.scoring_quality == "fallback"
    assert result.report_meta.scoring_source == "fallback"
    assert result.payload["feedback"].startswith("Fallback score generated")


def test_judge_agent_score_speech_uses_prompt_pack_and_repair(monkeypatch):
    calls = []

    async def fake_call_agent(self, prompt):
        calls.append(prompt)
        if len(calls) == 1:
            assert "prompt_pack_version: a.prompt_pack.v1" in prompt
            assert "task_detail:" in prompt
            return "bad judge output"
        assert "Repair the following judge response" in prompt
        return """
        {
          "logic_score": 71,
          "argument_score": 72,
          "response_score": 73,
          "persuasion_score": 74,
          "teamwork_score": 75,
          "overall_score": 73,
          "feedback": "repaired ok"
        }
        """

    monkeypatch.setattr(JudgeAgent, "_call_agent", fake_call_agent)
    judge = JudgeAgent(SimpleNamespace())

    result = asyncio.run(
        judge.score_speech(
            speech_content="sample speech",
            speaker_role="debater_2",
            phase="questioning",
            context=[{"config_meta": {"mode": "teaching"}}],
        )
    )

    assert len(calls) == 2
    assert result.overall_score == 73
    assert result.report_meta["scoring_quality"] == "repaired"
    assert result.report_meta["retry_count"] == 1
    assert result.report_meta["mode"] == "teaching"


def test_judge_agent_batch_evaluate_uses_prompt_pack_repair_and_meta(monkeypatch):
    calls = []

    async def fake_call_agent(self, prompt):
        calls.append(prompt)
        if len(calls) == 1:
            assert "prompt_pack_version: a.prompt_pack.v1" in prompt
            assert "task_detail:" in prompt
            return "not json"
        assert "Repair the following judge response" in prompt
        return """
        {
          "speech_scores": [
            {
              "speech_id": "s1",
              "scores": {
                "logic_score": 80,
                "argument_score": 81,
                "response_score": 82,
                "persuasion_score": 83,
                "teamwork_score": 84,
                "overall_score": 82,
                "feedback": "batch repaired ok"
              },
              "violations": []
            }
          ],
          "global_report": {
            "winner": "positive",
            "winning_reason": "higher score",
            "scores": {
              "positive": {"total_score": 82},
              "negative": {"total_score": 70}
            },
            "overall_comment": "ok",
            "suggestions": "keep improving"
          }
        }
        """

    monkeypatch.setattr(JudgeAgent, "_call_agent", fake_call_agent)
    judge = JudgeAgent(SimpleNamespace())

    result = asyncio.run(
        judge.batch_evaluate_debate(
            [
                {
                    "speech_id": "s1",
                    "speaker_role": "debater_1",
                    "phase": "opening",
                    "content": "sample speech",
                    "config_meta": {"mode": "teaching"},
                }
            ]
        )
    )

    assert len(calls) == 2
    assert result["report_meta"]["scoring_quality"] == "repaired"
    assert result["report_meta"]["mode"] == "teaching"
    assert result["speech_scores"][0]["scores"]["report_meta"]["retry_count"] == 1
    assert result["global_report"]["report_meta"]["scoring_quality"] == "repaired"
    assert result["calibration_summary"]["calibration_version"] == "a.calibration.v1"
