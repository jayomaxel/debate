from pathlib import Path


def test_migration_022_is_chained_and_creates_authoritative_runtime_state():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "022_add_debate_runtime_states.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "022"' in migration
    assert 'down_revision = "021"' in migration
    for field in ("room_id", "debate_id", "state", "version", "lease_owner", "lease_expires_at"):
        assert f'"{field}"' in migration
