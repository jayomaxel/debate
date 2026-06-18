from services.prompt_pack_service import DebateReportSchema
from services.rubric_service import LEGACY_SCORE_FIELDS, RubricService
from services.score_validation_service import ScoreValidationService


def test_legacy_score_fields_remain_frozen_for_b_and_d_consumers():
    contract = ScoreValidationService.expected_speech_score_contract()

    for field_name in LEGACY_SCORE_FIELDS:
        assert field_name in contract
    assert "overall_score" in contract
    assert "feedback" in contract


def test_debate_report_v2_adds_fields_without_dropping_legacy_surface():
    report = DebateReportSchema.mock().to_dict()

    assert "report_meta" in report
    assert "turning_points" in report
    assert "evidence_anchors" in report
    assert "improvement_actions" in report
    assert "participant_scores" in report
    assert "participants" in report
    assert "speeches" in report
    assert "team_summary" in report
    assert "teaching_summary" in report


def test_scoring_quality_values_cover_required_states():
    states = ["validated", "repaired", "fallback", "partial"]

    for state in states:
        meta = ScoreValidationService.build_report_meta(
            scoring_source="fallback" if state == "fallback" else "judge_model",
            scoring_quality=state,
        )
        assert meta.scoring_quality == state


def test_rubric_score_layers_do_not_mix_team_and_personal_scores():
    participant_score = RubricService.build_participant_score(
        "debater_2",
        {
            "logic_score": 85,
            "argument_score": 80,
            "response_score": 90,
            "persuasion_score": 75,
            "teamwork_score": 70,
        },
        role_fulfillment_score=88,
        team_process_score=60,
    )

    assert participant_score["common_argument_score"] != participant_score["team_process_score"]
    assert participant_score["role_fulfillment_score"] == 88
    assert participant_score["team_process_score"] == 60
