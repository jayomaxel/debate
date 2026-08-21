from pathlib import Path


def test_migration_024_is_chained_after_msy_migrations_and_is_idempotent():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "024_align_teaching_design_contract.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "024"' in migration
    assert 'down_revision = "023"' in migration
    assert 'if name not in columns' in migration
    for column_name in (
        "extraction_result",
        "confidence",
        "missing_fields",
        "source_excerpt_map",
        "status",
    ):
        assert column_name in migration
