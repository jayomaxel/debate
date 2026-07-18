from pathlib import Path
import uuid

import pytest

from config import settings
from models.debate import Debate
from services.report_file_storage_service import ReportFileStorageService
from services.report_service import Report, ReportGenerator


@pytest.mark.asyncio
async def test_export_to_pdf_async_generates_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        settings,
        "REPORT_FILE_STORAGE_DIR",
        str(tmp_path / "private-report-storage"),
        raising=False,
    )

    async def fake_generate_markdown_via_coze(db, report):
        return f"# Test Report\n\nTopic: {report.topic}\n\nThis is a test speech."

    monkeypatch.setattr(
        ReportGenerator,
        "_generate_markdown_via_coze",
        fake_generate_markdown_via_coze,
        raising=True,
    )

    async def fake_render_markdown_to_pdf_async(**kwargs):
        return b"%PDF-1.4\n%private-storage\n%%EOF"

    monkeypatch.setattr(
        ReportGenerator,
        "render_markdown_to_pdf_async",
        fake_render_markdown_to_pdf_async,
        raising=True,
    )

    report = Report(
        debate_id="debate-1",
        topic="Test debate topic",
        start_time=None,
        end_time=None,
        duration=0,
        participants=[
            {
                "user_id": "u1",
                "name": "Student One",
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
                "speaker_name": "Student One",
                "stance": "positive",
                "role": "debater_1",
                "phase": "opening",
                "content": "This is a test speech.",
                "duration": 10,
                "timestamp": "2026-02-04T00:00:00",
                "score": {
                    "logic_score": 80,
                    "argument_score": 80,
                    "response_score": 80,
                    "persuasion_score": 80,
                    "teamwork_score": 80,
                    "overall_score": 80,
                    "feedback": "Test feedback",
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

    storage_root = Path(str(getattr(settings, "REPORT_FILE_STORAGE_DIR"))).resolve()
    cached_files = list(storage_root.rglob("*.pdf"))
    assert cached_files
    assert cached_files[0].read_bytes().startswith(b"%PDF")


def test_private_report_pdf_rejects_tampered_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "REPORT_FILE_STORAGE_DIR",
        str(tmp_path / "private-report-storage"),
        raising=False,
    )
    debate = Debate(id=uuid.uuid4(), topic="Integrity check")

    storage_meta, stored_path = ReportFileStorageService.persist_pdf_bytes_for_debate(
        debate,
        b"%PDF-1.4\noriginal\n%%EOF",
    )
    assert storage_meta["sha256"]
    stored_path.write_bytes(b"%PDF-1.4\ntampered\n%%EOF")

    _, resolved_path, is_legacy = ReportFileStorageService.locate_pdf_artifact(
        debate,
        str(debate.id),
    )

    assert resolved_path is None
    assert is_legacy is False
