from pathlib import Path
from types import SimpleNamespace

from agents.mentor_agent import MentorAgent


AGENT_FILES = (
    Path("api/agents/debater_agent.py"),
    Path("api/agents/judge_agent.py"),
    Path("api/agents/mentor_agent.py"),
)


def test_agents_do_not_reintroduce_inline_business_prompt_blocks():
    offenders = []
    for path in AGENT_FILES:
        source = path.read_text(encoding="utf-8")
        if 'prompt = f"""' in source or "prompt = f'''" in source:
            offenders.append(str(path))

    assert offenders == []


def test_mentor_tip_length_follows_teaching_mode_policy():
    agent = MentorAgent(db=SimpleNamespace())

    prompt = agent._build_prompt_pack_prompt(
        "测试辩题",
        "positive",
        "debater_2",
        "free_debate",
        context=[{"config_meta": {"mode": "teaching"}}],
        task_type="real_time_suggestion",
        task_data={"max_chars": 80},
    )

    assert '"max_chars": 180' in prompt
    assert '"min_chars": 120' in prompt
