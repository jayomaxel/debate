from services.domain_pack_service import DomainPackService
from services.prompt_pack_service import (
    PROMPT_LAYER_ORDER,
    DebateReportSchema,
    PromptBuildContext,
    PromptPackService,
)


def test_prompt_build_context_defaults_to_competition():
    context = PromptBuildContext(topic="AI should enter the classroom")

    assert context.mode == "competition"
    assert context.agent == "debater"
    assert context.phase == "opening"
    assert context.history == []
    assert context.knowledge_snippets == []


def test_prompt_pack_has_stable_seven_layer_order():
    pack = PromptPackService.build_prompt(
        PromptBuildContext(
            agent="judge",
            mode="competition",
            phase="questioning",
            topic="AI should enter the classroom",
        )
    )

    assert list(pack.layers.keys()) == list(PROMPT_LAYER_ORDER)
    assert pack.layers["task_contract"]["constraints"] == [
        "json_only",
        "score_0_100",
        "no_hidden_fallback",
    ]
    assert "overall_score" in pack.layers["output_contract"]


def test_competition_and_teaching_prompts_differ_without_changing_shape():
    competition = PromptPackService.build_prompt(
        PromptBuildContext(agent="mentor", mode="competition", phase="free_debate")
    )
    teaching = PromptPackService.build_prompt(
        PromptBuildContext(agent="mentor", mode="teaching", phase="free_debate")
    )

    assert list(competition.layers.keys()) == list(teaching.layers.keys())
    assert competition.layers["mode_policy"]["mentor_length"]["max_chars"] == 120
    assert teaching.layers["mode_policy"]["mentor_length"]["max_chars"] == 180
    assert competition.render() != teaching.render()


def test_render_agent_prompt_keeps_pack_and_task_detail():
    prompt = PromptPackService.render_agent_prompt(
        PromptBuildContext(agent="debater", phase="questioning", topic="AI in class"),
        task_prompt="legacy task body",
        extra_sections={"debug_contract": {"field": "value"}},
    )

    assert prompt.startswith("prompt_pack_version: a.prompt_pack.v1")
    assert "## global_rules" in prompt
    assert "task_detail:" in prompt
    assert "legacy task body" in prompt
    assert "debug_contract:" in prompt
    assert '"field": "value"' in prompt


def test_resolve_mode_from_context_reads_frozen_meta_without_agent_logic():
    history = [{"content": "hello"}, {"config_meta": {"mode": "teaching"}}]

    assert PromptPackService.resolve_mode_from_context(history) == "teaching"
    assert PromptPackService.resolve_mode_from_context(history, mode="competition") == "competition"


def test_default_domain_pack_does_not_inject_stablecoin_content():
    pack = DomainPackService.build_domain_pack()

    assert pack.domain_pack_id == "default"
    assert pack.knowledge_snippets == []
    assert "stablecoin" in pack.blocked_defaults


def test_mock_report_schema_has_frontend_ready_quality_fields():
    report = DebateReportSchema.mock(mode="teaching", scoring_quality="fallback").to_dict()

    assert report["mode"] == "teaching"
    assert report["report_meta"]["scoring_quality"] == "fallback"
    assert report["report_meta"]["scoring_source"] == "fallback"
    assert report["evidence_anchors"][0]["turn_id"] == "turn_1"
    assert "improvement_actions" in report
