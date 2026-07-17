from services.assessment_service import AssessmentService


def test_standard_profile_contract_maps_current_and_legacy_fields():
    profile = AssessmentService.build_standard_profile(
        {
            "expression_willingness": 72,
            "logical_thinking": 84,
            "critical_thinking": 91,
            "financial_knowledge": 66,
            "stablecoin_knowledge": 58,
        }
    )

    assert profile["standard_profile"] == {
        "expression": 72,
        "logic": 84,
        "critical": 91,
        "knowledge_primary": 66,
        "knowledge_secondary": 58,
    }
    assert profile["legacy_profile"]["expression_willingness"] == 72
    assert profile["legacy_profile"]["logical_thinking"] == 84
    assert profile["analysis_basis"] == "self_assessment_only"


def test_empty_assessment_profile_uses_neutral_contract_defaults():
    profile = AssessmentService.build_standard_profile(None)

    assert profile["standard_profile"] == {
        "expression": 50,
        "logic": 50,
        "critical": 50,
        "knowledge_primary": 50,
        "knowledge_secondary": 50,
    }
    assert profile["legacy_profile"]["financial_knowledge"] == 50
    assert profile["analysis_basis"] == "fallback_rule_only"


def test_role_fit_exposes_assignment_basis_for_profile():
    fit = AssessmentService.score_role_fit(
        {
            "expression_willingness": 60,
            "logical_thinking": 70,
            "critical_thinking": 95,
            "financial_knowledge": 65,
            "stablecoin_knowledge": 55,
        },
        "debater_3",
    )

    assert fit["role"] == "debater_3"
    assert fit["fit_score"] > 0
    assert fit["dimension_contribution"]["critical"] == 38.0
    assert fit["data_basis"] == "self_assessment_only"
    assert fit["standard_profile"]["critical"] == 95
