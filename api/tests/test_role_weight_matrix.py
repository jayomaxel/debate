from services.rubric_service import DEBATER_ROLES, RUBRIC_VERSION, RubricService


def test_scoring_policy_has_three_layers_and_valid_role_weights():
    policy = RubricService.get_scoring_policy("competition")
    validation = RubricService.validate_policy(policy)

    assert policy.version == RUBRIC_VERSION
    assert policy.score_layers.to_dict() == {
        "common_argument_weight": 0.55,
        "role_fulfillment_weight": 0.30,
        "team_process_weight": 0.15,
    }
    assert validation == {"valid": True, "errors": []}


def test_all_debater_roles_have_distinct_responsibilities():
    responsibilities = {}

    for role in DEBATER_ROLES:
        rubric = RubricService.get_role_rubric(role)
        responsibilities[role] = set(rubric.responsibilities.keys())
        assert round(sum(rubric.dimension_weights.values()), 6) == 1.0

    assert "definition" in responsibilities["debater_1"]
    assert "question_design" in responsibilities["debater_2"]
    assert "rebuttal_integration" in responsibilities["debater_3"]
    assert "weighing" in responsibilities["debater_4"]


def test_role_weighted_dimension_score_keeps_legacy_fields():
    scores = {
        "logic_score": 90,
        "argument_score": 80,
        "response_score": 70,
        "persuasion_score": 60,
        "teamwork_score": 50,
    }

    first_speaker_score = RubricService.weighted_dimension_score(scores, "debater_1")
    third_speaker_score = RubricService.weighted_dimension_score(scores, "debater_3")

    assert first_speaker_score != third_speaker_score
    assert first_speaker_score == 75.8
    assert third_speaker_score == 73.0


def test_participant_score_separates_personal_role_and_team_layers():
    participant_score = RubricService.build_participant_score(
        "debater_4",
        {
            "logic_score": 80,
            "argument_score": 82,
            "response_score": 70,
            "persuasion_score": 88,
            "teamwork_score": 76,
        },
        role_fulfillment_score=90,
        team_process_score=75,
    )

    assert participant_score["rubric_version"] == RUBRIC_VERSION
    assert participant_score["common_argument_score"] == 80.28
    assert participant_score["role_fulfillment_score"] == 90
    assert participant_score["team_process_score"] == 75
    assert participant_score["overall_score"] == 82.4
    assert participant_score["legacy_scores"]["logic_score"] == 80
