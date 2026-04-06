"""
数据库会话管理
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import redis
from config import settings

# PostgreSQL数据库引擎（延迟初始化）
engine = None
SessionLocal = None

def init_engine():
    """初始化数据库引擎"""
    global engine, SessionLocal
    if engine is None:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基础模型类
Base = declarative_base()

# Redis连接（延迟初始化）
redis_client = None

def init_redis():
    """初始化Redis连接"""
    global redis_client
    if redis_client is None:
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )

def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话
    用于FastAPI依赖注入
    """
    if SessionLocal is None:
        init_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_redis():
    """
    获取Redis客户端
    用于FastAPI依赖注入
    """
    if redis_client is None:
        init_redis()
    return redis_client

def init_db():
    """
    初始化数据库
    创建所有表
    """
    if engine is None:
        init_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_ability_assessment_columns()
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
        conn.execute(text("UPDATE ability_assessments SET stablecoin_knowledge_score = 50 WHERE stablecoin_knowledge_score IS NULL"))
        conn.execute(text("UPDATE ability_assessments SET financial_knowledge_score = 50 WHERE financial_knowledge_score IS NULL"))
        conn.execute(text("UPDATE ability_assessments SET critical_thinking_score = 50 WHERE critical_thinking_score IS NULL"))
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
