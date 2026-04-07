import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

root = Path(__file__).resolve().parents[1]
root_str = str(root)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

from models.user import User
from testing_db import (
    PGVECTOR_TEST_DATABASE_ENV,
    create_test_engine,
    create_test_schema,
    drop_test_schema,
    has_pgvector_test_database,
    resolve_test_database_url,
)


TEST_DATABASE_URL = "sqlite:///:memory:"


def pytest_collection_modifyitems(config, items):
    if has_pgvector_test_database():
        return

    skip_pgvector = pytest.mark.skip(
        reason=(
            f"requires PostgreSQL + pgvector test database; "
            f"set {PGVECTOR_TEST_DATABASE_ENV} to enable these tests"
        )
    )

    for item in items:
        if "pgvector" in item.keywords:
            item.add_marker(skip_pgvector)


@pytest.fixture
def db_session(request):
    """Create a test database session."""
    database_url = resolve_test_database_url(
        TEST_DATABASE_URL,
        use_pgvector=bool(request.node.get_closest_marker("pgvector")),
    )
    engine = create_test_engine(database_url)
    create_test_schema(engine)

    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()

    test_user = User(
        id=uuid.uuid4(),
        account="test_admin",
        name="Test Admin",
        email="admin@test.com",
        password_hash="hashed_password",
        user_type="administrator",
        created_at=datetime.utcnow(),
    )
    session.add(test_user)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        drop_test_schema(engine)
