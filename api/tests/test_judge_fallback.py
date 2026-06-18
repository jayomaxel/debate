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
