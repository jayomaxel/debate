# Backend Testing Guide

## Default test environment

- Default backend tests use SQLite.
- SQLite schema creation is now filtered through the shared test helper, so PostgreSQL-only `ARRAY` columns do not break unrelated suites.
- Run backend tests with the project virtual environment:

```powershell
cd api
.\venv\Scripts\python.exe -m pytest
```

## pgvector suites

- Tests marked with `@pytest.mark.pgvector` require PostgreSQL with the `pgvector` extension.
- Configure the database URL through `TEST_PGVECTOR_DATABASE_URL`.
- When this variable is not set, `pgvector` tests are skipped automatically.

Example:

```powershell
$env:TEST_PGVECTOR_DATABASE_URL = "postgresql://user:password@localhost:5432/aidebate_test"
cd api
.\venv\Scripts\python.exe -m pytest -m pgvector
```

## Current split

- SQLite is the default for fast unit and router tests.
- PostgreSQL + pgvector is reserved for vector storage, vector search, and document-processing workflows that depend on the `kb_document_chunks` table.
