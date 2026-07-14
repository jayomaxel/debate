from services.score_validation_service import (
    CALIBRATION_VERSION,
    ScoreValidationService,
)


def test_valid_judge_json_is_marked_validated():
    raw = """
    Here is the JSON:
    {
      "logic_score": 82,
      "argument_score": 80,
      "response_score": 78,
      "persuasion_score": 81,
      "teamwork_score": 76,
      "overall_score": 79,
      "feedback": "结构清楚，回应直接。"
    }
    """

    result = ScoreValidationService.validate_or_fallback(raw, provider="llm")

    assert result.scoring_quality == "validated"
    assert result.report_meta.scoring_source == "judge_model"
    assert result.payload["overall_score"] == 79
    assert result.errors == []


def test_invalid_json_with_repaired_text_is_marked_repaired():
    repaired = """
    ```json
    {
      "logic_score": 70,
      "argument_score": 72,
      "response_score": 74,
      "persuasion_score": 76,
      "teamwork_score": 78,
      "overall_score": 74,
      "feedback": "修复后可解析。"
    }
    ```
    """

    result = ScoreValidationService.validate_or_fallback(
        "logic 70, argument 72",
        repaired_text=repaired,
        mode="teaching",
        provider="coze",
    )

    assert result.scoring_quality == "repaired"
    assert result.report_meta.retry_count == 1
    assert result.report_meta.provider == "coze"
    assert result.report_meta.mode == "teaching"
    assert "Repair the following judge response" in result.repair_prompt


def test_invalid_json_falls_back_with_explicit_meta():
    result = ScoreValidationService.validate_or_fallback(
        "not json",
        repaired_text="still not json",
        provider="unknown",
    )

    assert result.scoring_quality == "fallback"
    assert result.report_meta.scoring_source == "fallback"
    assert result.report_meta.provider == "llm"
    assert result.report_meta.retry_count == 1
    assert result.payload["overall_score"] == 60.0
    assert result.errors


def test_partial_payload_reports_partial_quality():
    payload = {
        "logic_score": 90,
        "argument_score": 88,
        "response_score": 86,
        "feedback": "缺少部分字段",
    }

    result = ScoreValidationService.validate_speech_score(payload)

    assert result.scoring_quality == "partial"
    assert "missing score field: persuasion_score" in result.errors
    assert "missing score field: teamwork_score" in result.errors


def test_calibration_summary_marks_mechanism_not_scientific_validation():
    samples = [
        {"type": "fallback_triggered", "speaker_role": "debater_2", "severity": "high"},
        {"type": "extreme_score", "speaker_role": "debater_4", "severity": "medium"},
    ]

    summary = ScoreValidationService.build_calibration_summary(samples)

    assert summary["calibration_version"] == CALIBRATION_VERSION
    assert summary["sample_count"] == 2
    assert summary["role_anomaly_distribution"]["debater_2"] == 1
    assert summary["fairness_check"]["status"] == "needs_review"
    assert "not a scientifically validated" in summary["fairness_check"]["claim"]
