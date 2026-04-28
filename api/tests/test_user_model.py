"""
Test User model - verify administrator role support
"""

import pytest
from sqlalchemy.orm import sessionmaker
from models.user import User
from database import Base
from testing_db import create_test_engine, create_test_schema, drop_test_schema
import uuid

# Create in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_test_engine(TEST_DATABASE_URL)

    # For SQLite, we need to handle the enum differently
    # SQLite doesn't have native enum support, so SQLAlchemy will use VARCHAR
    create_test_schema(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        drop_test_schema(engine)


def test_user_model_accepts_administrator_role(db_session):
    """Test that User model accepts 'administrator' as a valid role"""
    # Create a user with administrator role
    admin_user = User(
        id=uuid.uuid4(),
        account="admin",
        password_hash="hashed_password_here",
        user_type="administrator",
        name="Administrator",
        email="admin@system.local",
    )

    # Add to session and commit
    db_session.add(admin_user)
    db_session.commit()

    # Query back and verify
    retrieved_user = db_session.query(User).filter(User.account == "admin").first()

    assert retrieved_user is not None
    assert retrieved_user.user_type == "administrator"
    assert retrieved_user.account == "admin"
    assert retrieved_user.name == "Administrator"
    assert retrieved_user.email == "admin@system.local"


def test_user_model_accepts_teacher_role(db_session):
    """Test that User model still accepts 'teacher' role (backward compatibility)"""
    teacher_user = User(
        id=uuid.uuid4(),
        account="teacher1",
        password_hash="hashed_password_here",
        user_type="teacher",
        name="Teacher One",
        email="teacher1@test.com",
    )

    db_session.add(teacher_user)
    db_session.commit()

    retrieved_user = db_session.query(User).filter(User.account == "teacher1").first()

    assert retrieved_user is not None
    assert retrieved_user.user_type == "teacher"


def test_user_model_accepts_student_role(db_session):
    """Test that User model still accepts 'student' role (backward compatibility)"""
    student_user = User(
        id=uuid.uuid4(),
        account="student1",
        password_hash="hashed_password_here",
        user_type="student",
        name="Student One",
        email="student1@test.com",
    )

    db_session.add(student_user)
    db_session.commit()

    retrieved_user = db_session.query(User).filter(User.account == "student1").first()

    assert retrieved_user is not None
    assert retrieved_user.user_type == "student"


def test_user_model_rejects_invalid_role(db_session):
    """Test that User model rejects invalid role values"""
    # This test verifies that only valid roles are accepted
    # In SQLite, enum validation happens at the SQLAlchemy level
    # In PostgreSQL, it would be enforced at the database level

    with pytest.raises(Exception):  # Could be ValueError or StatementError
        invalid_user = User(
            id=uuid.uuid4(),
            account="invalid",
            password_hash="hashed_password_here",
            user_type="invalid_role",  # This should fail
            name="Invalid User",
            email="invalid@test.com",
        )
        db_session.add(invalid_user)
        db_session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
