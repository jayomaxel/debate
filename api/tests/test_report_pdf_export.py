import pytest

from services.report_service import Report, ReportGenerator
from config import settings


@pytest.mark.asyncio
async def test_export_to_pdf_async_generates_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    async def fake_generate_markdown_report_async(
        db,
        debate_topic,
        content_str="",
    ):
        return f"# 测试报告\n\n辩题：{debate_topic}\n\n{content_str}"

    monkeypatch.setattr(
        ReportGenerator,
        "generate_markdown_report_async",
        fake_generate_markdown_report_async,
        raising=True,
    )

    report = Report(
        debate_id="debate-1",
        topic="测试辩题",
        start_time=None,
        end_time=None,
        duration=0,
        participants=[
            {
                "user_id": "u1",
                "name": "张三",
                "role": "debater_1",
                "stance": "positive",
                "is_ai": False,
                "final_score": {
                    "logic_score": 80,
                    "argument_score": 80,
                    "response_score": 80,
                    "persuasion_score": 80,
                    "teamwork_score": 80,
                    "overall_score": 80,
                    "speech_count": 1,
                    "total_duration": 10,
                },
            }
        ],
        speeches=[
            {
                "id": "s1",
                "speaker_type": "human",
                "speaker_role": "debater_1",
                "speaker_name": "张三",
                "stance": "positive",
                "role": "debater_1",
                "phase": "opening",
                "content": "这是一次测试发言。",
                "duration": 10,
                "timestamp": "2026-02-04T00:00:00",
                "score": {
                    "logic_score": 80,
                    "argument_score": 80,
                    "response_score": 80,
                    "persuasion_score": 80,
                    "teamwork_score": 80,
                    "overall_score": 80,
                    "feedback": "测试评语",
                },
            }
        ],
        statistics={"winner": "positive"},
        winner="positive",
    )

    report_data = report.to_dict()
    assert report_data["mode"] == "competition"
    assert report_data["report_meta"]["scoring_quality"] == "validated"
    assert report_data["participant_scores"][0]["legacy_scores"]["overall_score"] == 80
    assert report_data["evidence_anchors"][0]["turn_id"] == "s1"
    assert report_data["team_summary"]["positive"]["speech_count"] == 1
    assert report_data["statistics"]["calibration_summary"]["sample_count"] == 0

    pdf_bytes = await ReportGenerator.export_to_pdf_async(object(), report)
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert bytes(pdf_bytes).startswith(b"%PDF")

    cache_path = ReportGenerator._get_report_pdf_cache_path(report.debate_id)
    assert cache_path.exists()
    assert cache_path.read_bytes().startswith(b"%PDF")
