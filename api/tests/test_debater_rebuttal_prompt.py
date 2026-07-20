import asyncio
from types import SimpleNamespace

from agents.debater_agent import AIDebaterAgent


def test_rebuttal_prompt_marks_opponent_argument_as_attack_target(monkeypatch):
    captured = {}

    async def fake_call_agent(self, prompt, context=None, stream_callback=None):
        captured["prompt"] = prompt
        return "反方直接回应"

    monkeypatch.setattr(AIDebaterAgent, "_call_agent", fake_call_agent)

    agent = AIDebaterAgent(position=1, db=SimpleNamespace())
    result = asyncio.run(
        agent.generate_rebuttal(
            topic="人工智能是否应该进入课堂",
            stance="negative",
            opponent_argument="人工智能一定能提高所有学生的学习效果。",
            context=[{"role": "user", "content": "历史发言"}],
        )
    )

    assert result == "反方直接回应"
    prompt = captured["prompt"]
    assert "人工智能一定能提高所有学生的学习效果。" in prompt
    assert "task_execution_contract" in prompt
    assert "directly state one concrete defect" in prompt
    assert "never produce only a paraphrase" in prompt
    assert "This is a rebuttal task" in agent._build_runtime_system_prompt(
        rendered_prompt=prompt
    )


def test_free_debate_prompt_extracts_latest_non_ai_speech_as_target(monkeypatch):
    captured = {}

    async def fake_call_agent(self, prompt, context=None, stream_callback=None):
        captured["prompt"] = prompt
        return "反方完成反驳"

    monkeypatch.setattr(AIDebaterAgent, "_call_agent", fake_call_agent)

    agent = AIDebaterAgent(position=1, db=SimpleNamespace())
    recent_speeches = [
        {"speaker": "ai_1", "content": "我方之前的论点"},
        {"speaker": "debater_1", "content": "人工智能一定能提高所有学生的学习效果。"},
    ]
    result = asyncio.run(
        agent.generate_free_debate_speech(
            topic="人工智能是否应该进入课堂",
            stance="negative",
            context=[],
            recent_speeches=recent_speeches,
        )
    )

    assert result == "反方完成反驳"
    prompt = captured["prompt"]
    assert '"opponent_argument": "人工智能一定能提高所有学生的学习效果。"' in prompt
    assert "open with a direct challenge" in prompt
    assert "do not repeat the opponent speech" in prompt

