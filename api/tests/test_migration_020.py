"""Regression tests for the durable background job migration."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "020_add_background_jobs.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_020", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_and_downgrade_background_jobs_schema():
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        migration = _load_migration_module()
        migration.op = Operations(MigrationContext.configure(connection))

        migration.upgrade()
        inspector = sa.inspect(connection)
        assert "background_jobs" in inspector.get_table_names()
        columns = {item["name"] for item in inspector.get_columns("background_jobs")}
        assert {
            "id",
            "job_type",
            "dedupe_key",
            "status",
            "attempt_count",
            "max_attempts",
            "payload",
            "available_at",
            "lease_expires_at",
            "claimed_by",
        } <= columns
        indexes = {item["name"] for item in inspector.get_indexes("background_jobs")}
        assert {
            "idx_background_jobs_claim",
            "idx_background_jobs_expired_lease",
            "idx_background_jobs_target_created",
        } <= indexes
        unique_constraints = {
            item["name"] for item in inspector.get_unique_constraints("background_jobs")
        }
        assert "uq_background_jobs_type_dedupe" in unique_constraints

        migration.downgrade()
        assert "background_jobs" not in sa.inspect(connection).get_table_names()


def test_upgrade_is_idempotent_when_table_already_exists():
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        migration = _load_migration_module()
        migration.op = Operations(MigrationContext.configure(connection))

        migration.upgrade()
        migration.upgrade()

        assert "background_jobs" in sa.inspect(connection).get_table_names()
