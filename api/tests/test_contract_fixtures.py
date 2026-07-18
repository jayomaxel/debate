import json
from pathlib import Path


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs" / "api_contract_examples"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_json(filename: str):
    with (DOCS_DIR / filename).open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _load_fixture(filename: str):
    with (FIXTURES_DIR / filename).open("r", encoding="utf-8") as fp:
        return json.load(fp)


def test_topic_recommendation_contract_example_files_exist_and_parse():
    expected = [
        "topic_recommendation_history.json",
        "topic_recommendation_detail.json",
        "topic_recommendation_analytics.json",
        "topic_recommendation_dashboard.json",
        "topic_recommendation_version_comparison.json",
    ]
    for filename in expected:
        assert (DOCS_DIR / filename).exists(), filename
        payload = _load_json(filename)
        assert payload["code"] == 200
        assert "data" in payload


def test_dashboard_contract_example_contains_expected_sections():
    payload = _load_json("topic_recommendation_dashboard.json")
    data = payload["data"]
    assert "summary" in data
    assert "quality" in data
    assert "timeline" in data
    assert "leaderboards" in data
    assert "observations" in data
    assert "recent_runs" in data


def test_work_package_e_contract_examples_exist_and_parse():
    expected = [
        'teaching_design_ready.json',
        'support_document_summary.json',
        'knowledge_snippet.json',
    ]
    for filename in expected:
        payload = _load_json(filename)
        assert payload['code'] == 200
        assert payload['data']


def test_teaching_design_contract_fixture_matches_the_published_example():
    fixture = _load_fixture("teaching_design_ready.json")
    example = _load_json("teaching_design_ready.json")["data"]

    assert fixture["contract"] == "TeachingDesignSchema"
    assert fixture["example"] == example
    assert set(example) == {"design_id", "class_id", "current_version_id", "versions"}
    assert example["versions"]

    version = example["versions"][0]
    assert set(version) == {
        "version_id",
        "uploaded_at",
        "source_file_type",
        "source_file_name",
        "extraction_result",
        "confidence",
        "missing_fields",
        "source_excerpt_map",
        "status",
    }
    assert version["source_file_type"] in {"pdf", "docx"}
    assert version["status"] in {"extracting", "ready", "needs_review", "failed"}
    assert set(version["extraction_result"]) == {
        "course_objectives",
        "knowledge_points",
        "chapter_topics",
        "key_and_difficult_points",
        "competency_goals",
        "applicable_grade",
        "class_hour_constraints",
        "teacher_notes",
    }


def test_version_comparison_contract_example_contains_expected_sections():
    payload = _load_json("topic_recommendation_version_comparison.json")
    data = payload["data"]
    assert "version_comparison_summary" in data
    assert "version_breakdown" in data
