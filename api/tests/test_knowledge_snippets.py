import asyncio
from types import SimpleNamespace
import uuid

from agents.debater_agent import AIDebaterAgent
from services.knowledge_base import KnowledgeBase


class _DocumentQuery:
    def __init__(self, documents):
        self.documents = documents

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.documents


class _DocumentSession:
    def __init__(self, documents):
        self.documents = documents

    def query(self, *args, **kwargs):
        return _DocumentQuery(self.documents)


def test_knowledge_snippets_filter_by_phase_and_use_frozen_shape():
    document = SimpleNamespace(
        id=uuid.uuid4(),
        purpose_tag="evidence",
        filename="survey.pdf",
        content="unused",
        summary_payload={
            "label": "evidence",
            "summary": "A survey reached 82 percent of the target group.",
            "key_points": ["The sample was representative."],
            "evidence_candidates": ["82 percent response rate."],
            "case_candidates": [],
            "usable_phases": ["questioning", "free_debate"],
            "summary_quality": "validated",
        },
    )
    knowledge_base = KnowledgeBase.__new__(KnowledgeBase)
    knowledge_base.db = _DocumentSession([document])

    questioning = knowledge_base.get_knowledge_snippets(
        "debate-demo",
        "questioning",
        purpose_tags=["evidence"],
    )
    opening = knowledge_base.get_knowledge_snippets("debate-demo", "opening")

    assert len(questioning) == 2
    assert opening == []
    assert set(questioning[0]) == {
        "snippet_id",
        "document_id",
        "source_type",
        "content",
        "usage_goal",
        "source_location",
    }
    assert questioning[0]["source_type"] == "evidence"
    assert questioning[0]["source_location"] == "survey.pdf"


def test_ai_debater_injects_retrieved_knowledge_snippets(monkeypatch):
    agent = AIDebaterAgent(position=1, db=SimpleNamespace())
    captured = {}

    def fake_load(debate_id, speech_type):
        assert debate_id == "debate-demo"
        assert speech_type == "opening"
        return [{
            "snippet_id": "source:opening:0",
            "document_id": "source",
            "source_type": "evidence",
            "content": "The verified response rate was 82 percent.",
            "usage_goal": "Establish the main claim.",
            "source_location": "survey.pdf",
        }]

    async def fake_call(prompt, context=None, stream_callback=None):
        captured["prompt"] = prompt
        return "Opening statement"

    monkeypatch.setattr(agent, "_load_knowledge_snippets", fake_load)
    monkeypatch.setattr(agent, "_call_agent", fake_call)

    result = asyncio.run(agent.generate_speech_with_audio(
        speech_type="opening",
        topic="Should evidence rules be stricter?",
        stance="positive",
        context=[],
        include_audio=False,
        debate_id="debate-demo",
    ))

    assert result["text"] == "Opening statement"
    assert "The verified response rate was 82 percent." in captured["prompt"]
