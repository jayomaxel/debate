"""Regression tests for the user avatar schema migration."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "018_add_user_avatar_columns.py"
)
AVATAR_COLUMNS = {
    "avatar_blob",
    "avatar_mime_type",
    "avatar_filename",
    "avatar_default_key",
}


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_018", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_and_downgrade_user_avatar_columns():
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)"))
        migration = _load_migration_module()
        migration.op = Operations(MigrationContext.configure(connection))

        migration.upgrade()
        upgraded_columns = {
            column["name"] for column in sa.inspect(connection).get_columns("users")
        }
        assert AVATAR_COLUMNS <= upgraded_columns

        migration.downgrade()
        downgraded_columns = {
            column["name"] for column in sa.inspect(connection).get_columns("users")
        }
        assert AVATAR_COLUMNS.isdisjoint(downgraded_columns)


def test_upgrade_is_compatible_with_preexisting_avatar_columns():
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE users ("
                "id VARCHAR(36) PRIMARY KEY, "
                "avatar_blob BLOB, "
                "avatar_mime_type VARCHAR(100), "
                "avatar_filename VARCHAR(255), "
                "avatar_default_key VARCHAR(64)"
                ")"
            )
        )
        migration = _load_migration_module()
        migration.op = Operations(MigrationContext.configure(connection))

        migration.upgrade()
        columns = {
            column["name"] for column in sa.inspect(connection).get_columns("users")
        }
        assert AVATAR_COLUMNS <= columns
