"""Regression tests for the runtime debate schema migration."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "019_complete_runtime_debate_schema.py"
)
DEBATE_COLUMNS = {"report", "report_pdf"}
SPEECH_COLUMNS = {
    "match_state",
    "side",
    "speaker_position",
    "started_at",
    "ended_at",
    "official_duration_sec",
    "actual_duration_sec",
}


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_019", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_base_schema(connection) -> None:
    connection.execute(sa.text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)"))
    connection.execute(sa.text("CREATE TABLE debates (id VARCHAR(36) PRIMARY KEY)"))
    connection.execute(
        sa.text(
            "CREATE TABLE speeches ("
            "id VARCHAR(36) PRIMARY KEY, "
            "debate_id VARCHAR(36) REFERENCES debates(id)"
            ")"
        )
    )


def _columns(connection, table_name: str) -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(connection).get_columns(table_name)
    }


def test_upgrade_and_downgrade_runtime_debate_schema():
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        _create_base_schema(connection)
        migration = _load_migration_module()
        migration.op = Operations(MigrationContext.configure(connection))

        migration.upgrade()
        assert DEBATE_COLUMNS <= _columns(connection, "debates")
        assert SPEECH_COLUMNS <= _columns(connection, "speeches")
        assert "debate_event_logs" in sa.inspect(connection).get_table_names()

        event_log_indexes = {
            index["name"]
            for index in sa.inspect(connection).get_indexes("debate_event_logs")
        }
        assert {
            "idx_debate_event_logs_debate_created",
            "idx_debate_event_logs_room_created",
            "idx_debate_event_logs_type_state",
        } <= event_log_indexes

        migration.downgrade()
        assert DEBATE_COLUMNS.isdisjoint(_columns(connection, "debates"))
        assert SPEECH_COLUMNS.isdisjoint(_columns(connection, "speeches"))
        assert "debate_event_logs" not in sa.inspect(connection).get_table_names()


def test_upgrade_is_compatible_with_preexisting_runtime_schema():
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        _create_base_schema(connection)
        connection.execute(sa.text("ALTER TABLE debates ADD COLUMN report JSON"))
        connection.execute(sa.text("ALTER TABLE speeches ADD COLUMN match_state VARCHAR(32)"))
        migration = _load_migration_module()
        migration.op = Operations(MigrationContext.configure(connection))

        migration.upgrade()
        migration.upgrade()

        assert DEBATE_COLUMNS <= _columns(connection, "debates")
        assert SPEECH_COLUMNS <= _columns(connection, "speeches")
        assert "debate_event_logs" in sa.inspect(connection).get_table_names()
