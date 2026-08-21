import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from models.user import User


def _database_url() -> str:
    value = os.getenv("E2E_DATABASE_URL") or ""
    if not value or make_url(value).get_backend_name() != "postgresql":
        pytest.skip("E2E_DATABASE_URL must point to a migrated PostgreSQL database")
    return value


@pytest.fixture(scope="session")
def e2e_session_factory():
    engine = create_engine(_database_url(), pool_pre_ping=True)
    factory = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    setup = factory()
    try:
        if setup.query(User).filter(User.user_type == "administrator").first() is None:
            setup.add(
                User(
                    id=uuid.uuid4(),
                    account=f"e2e-admin-{uuid.uuid4().hex[:8]}",
                    password_hash="e2e-only",
                    user_type="administrator",
                    name="E2E Admin",
                    email=f"{uuid.uuid4().hex}@example.test",
                )
            )
            setup.commit()
    finally:
        setup.close()
    yield factory
    engine.dispose()


@pytest.fixture
def e2e_db(e2e_session_factory):
    db = e2e_session_factory()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
