from pathlib import Path


def test_migration_023_is_chained_and_defaults_legacy_rows_to_untrusted():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "023_add_score_provenance.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "023"' in migration
    assert 'down_revision = "022"' in migration
    for field in (
        "status", "scoring_source", "scoring_quality", "retry_count", "provider",
        "model", "rubric_version", "failure_code", "metadata", "eligible_for_analytics",
    ):
        assert f'"{field}"' in migration
    assert "legacy_unknown" in migration
    assert "评分系统暂时不可用" in migration
    assert "eligible_for_analytics = false" in migration
