"""
Database session and optional Redis helpers.
"""

import logging
from typing import Any, Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import settings

try:
    import redis
except ModuleNotFoundError:  # pragma: no cover - depends on local environment
    redis = None


logger = logging.getLogger(__name__)

# PostgreSQL engine (lazy initialization)
engine = None
SessionLocal = None


def init_engine():
    """Initialize the SQLAlchemy engine once."""
    global engine, SessionLocal
    if engine is None:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


Base = declarative_base()

# Redis connection (lazy initialization)
redis_client = None
_redis_missing_dependency_logged = False


def init_redis():
    """Initialize Redis if the dependency is available."""
    global redis_client, _redis_missing_dependency_logged

    if redis_client is not None:
        return redis_client

    if redis is None:
        if not _redis_missing_dependency_logged:
            logger.warning(
                "Redis Python package is not installed; Redis-backed features are disabled. "
                "Install backend dependencies from api/requirements.txt to enable them."
            )
            _redis_missing_dependency_logged = True
        return None

    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
        decode_responses=True,
    )
    return redis_client


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI dependency injection."""
    if SessionLocal is None:
        init_engine()

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> Any:
    """Return the Redis client when available, otherwise ``None``."""
    if redis_client is None:
        return init_redis()
    return redis_client


def init_db():
    """Create tables and apply lightweight compatibility fixes."""
    if engine is None:
        init_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_ability_assessment_columns()
    _ensure_debate_report_columns()
    _ensure_debate_participation_columns()


def _ensure_ability_assessment_columns():
    if engine is None:
        return

    inspector = inspect(engine)
    if "ability_assessments" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("ability_assessments")}
    required_columns = [
        ("expression_willingness_score", "INTEGER"),
        ("logical_thinking_score", "INTEGER"),
        ("stablecoin_knowledge_score", "INTEGER"),
        ("financial_knowledge_score", "INTEGER"),
        ("critical_thinking_score", "INTEGER"),
        ("is_default", "BOOLEAN NOT NULL DEFAULT false"),
    ]

    with engine.begin() as conn:
        for column_name, column_type in required_columns:
            if column_name in existing_columns:
                continue
            conn.execute(text(f"ALTER TABLE ability_assessments ADD COLUMN {column_name} {column_type}"))

        conn.execute(
            text(
                "UPDATE ability_assessments "
                "SET logical_thinking_score = logical_thinking * 10 "
                "WHERE logical_thinking_score IS NULL"
            )
        )
        conn.execute(
            text(
                "UPDATE ability_assessments "
                "SET expression_willingness_score = expression_willingness * 10 "
                "WHERE expression_willingness_score IS NULL"
            )
        )
        conn.execute(
            text(
                "UPDATE ability_assessments "
                "SET stablecoin_knowledge_score = 50 "
                "WHERE stablecoin_knowledge_score IS NULL"
            )
        )
        conn.execute(
            text(
                "UPDATE ability_assessments "
                "SET financial_knowledge_score = 50 "
                "WHERE financial_knowledge_score IS NULL"
            )
        )
        conn.execute(
            text(
                "UPDATE ability_assessments "
                "SET critical_thinking_score = 50 "
                "WHERE critical_thinking_score IS NULL"
            )
        )
        conn.execute(text("UPDATE ability_assessments SET is_default = false WHERE is_default IS NULL"))


def _ensure_debate_participation_columns():
    if engine is None:
        return

    inspector = inspect(engine)
    if "debate_participations" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("debate_participations")}
    required_columns = [
        ("role_reason", "VARCHAR(32)"),
    ]

    with engine.begin() as conn:
        for column_name, column_type in required_columns:
            if column_name in existing_columns:
                continue
            conn.execute(text(f"ALTER TABLE debate_participations ADD COLUMN {column_name} {column_type}"))


def _ensure_debate_report_columns():
    if engine is None:
        return

    inspector = inspect(engine)
    if "debates" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("debates")}
    required_columns = [
        ("report", "JSON"),
        ("report_pdf", "TEXT"),
    ]

    with engine.begin() as conn:
        for column_name, column_type in required_columns:
            if column_name in existing_columns:
                continue
            conn.execute(text(f"ALTER TABLE debates ADD COLUMN {column_name} {column_type}"))
