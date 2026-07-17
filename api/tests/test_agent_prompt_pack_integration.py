from pathlib import Path


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
