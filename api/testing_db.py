"""
Shared helpers for test database setup.
"""

from __future__ import annotations

import os
from typing import Sequence

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.schema import Table

from database import Base


PGVECTOR_TEST_DATABASE_ENV = "TEST_PGVECTOR_DATABASE_URL"


def create_test_engine(database_url: str, **kwargs) -> Engine:
    """Create a test engine with SQLite-friendly defaults."""
    connect_args = kwargs.pop("connect_args", None)

    if database_url.startswith("sqlite"):
        merged_connect_args = {"check_same_thread": False}
        if connect_args:
            merged_connect_args.update(connect_args)
        kwargs["connect_args"] = merged_connect_args
    elif connect_args is not None:
        kwargs["connect_args"] = connect_args

    return create_engine(database_url, **kwargs)


def get_pgvector_test_database_url() -> str:
    """Return the configured PostgreSQL test URL for pgvector suites."""
    return os.getenv(PGVECTOR_TEST_DATABASE_ENV, "").strip()


def has_pgvector_test_database() -> bool:
    """Whether pgvector-marked tests have a PostgreSQL database available."""
    url = get_pgvector_test_database_url().lower()
    return url.startswith(("postgresql://", "postgresql+", "postgres://"))


def resolve_test_database_url(default_url: str, *, use_pgvector: bool = False) -> str:
    """Resolve the database URL for the current test."""
    if use_pgvector and has_pgvector_test_database():
        return get_pgvector_test_database_url()
    return default_url


def create_test_schema(engine: Engine, *, tables: Sequence[Table] | None = None) -> None:
    """Create the schema needed for a test run."""
    resolved_tables = _resolve_tables(engine, tables)
    if engine.dialect.name == "sqlite":
        for table in resolved_tables:
            table.create(bind=engine, checkfirst=True)
        return

    Base.metadata.create_all(bind=engine, tables=resolved_tables)


def drop_test_schema(engine: Engine, *, tables: Sequence[Table] | None = None) -> None:
    """Drop the schema created for a test run."""
    resolved_tables = _resolve_tables(engine, tables)
    if engine.dialect.name == "sqlite":
        for table in reversed(resolved_tables):
            table.drop(bind=engine, checkfirst=True)
        return

    Base.metadata.drop_all(bind=engine, tables=resolved_tables)


def _resolve_tables(engine: Engine, tables: Sequence[Table] | None) -> list[Table]:
    selected_tables = list(tables) if tables is not None else list(Base.metadata.tables.values())
    if engine.dialect.name != "sqlite":
        return selected_tables

    return [table for table in selected_tables if _table_supported_in_sqlite(table)]


def _table_supported_in_sqlite(table: Table) -> bool:
    for column in table.columns:
        visit_name = str(getattr(column.type, "__visit_name__", "")).upper()
        if visit_name == "ARRAY":
            return False
    return True
