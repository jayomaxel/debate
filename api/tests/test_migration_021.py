from pathlib import Path


def test_migration_021_is_chained_and_adds_publication_gate():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "021_add_kb_document_publication.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "021"' in migration
    assert 'down_revision = "020"' in migration
    assert '"is_published"' in migration
    assert 'server_default=sa.false()' in migration
