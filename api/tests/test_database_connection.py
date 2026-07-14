import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect, text


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def configured_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL or DATABASE_URL to run database connection diagnostics.")
    return database_url


def test_database_connection_diagnostics(configured_database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", configured_database_url)

    import database

    database.init_engine()
    assert database.SessionLocal is not None
    assert database.engine is not None

    db = database.SessionLocal()
    try:
        assert db.execute(text("SELECT 1")).scalar() == 1
    finally:
        db.close()


def test_database_required_tables_exist(configured_database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", configured_database_url)

    import database

    database.init_engine()
    assert database.engine is not None

    tables = set(inspect(database.engine).get_table_names())
    required_tables = {"debates", "speeches", "scores", "debate_participations", "users"}
    assert required_tables.issubset(tables)
