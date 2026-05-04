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
    _ensure_user_avatar_columns()
    _ensure_speech_columns()
    _ensure_ability_assessment_columns()
    _ensure_debate_report_columns()
    _ensure_debate_participation_columns()
    _ensure_lobby_reservation_columns()


def _ensure_user_avatar_columns():
    if engine is None:
        return

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    required_columns = [
        ("avatar_blob", "BYTEA"),
        ("avatar_mime_type", "VARCHAR(100)"),
        ("avatar_filename", "VARCHAR(255)"),
        ("avatar_default_key", "VARCHAR(64)"),
    ]

    if engine.dialect.name == "sqlite":
        required_columns = [
            ("avatar_blob", "BLOB"),
            ("avatar_mime_type", "VARCHAR(100)"),
            ("avatar_filename", "VARCHAR(255)"),
            ("avatar_default_key", "VARCHAR(64)"),
        ]

    with engine.begin() as conn:
        for column_name, column_type in required_columns:
            if column_name in existing_columns:
                continue
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))


def _ensure_speech_columns():
    if engine is None:
        return

    inspector = inspect(engine)
    if "speeches" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("speeches")}
    required_columns = [
        ("transcription_status", "VARCHAR(20)"),
        ("transcription_error", "TEXT"),
        ("is_valid_for_scoring", "BOOLEAN NOT NULL DEFAULT true"),
    ]

    with engine.begin() as conn:
        for column_name, column_type in required_columns:
            if column_name in existing_columns:
                continue
            conn.execute(text(f"ALTER TABLE speeches ADD COLUMN {column_name} {column_type}"))

        conn.execute(
            text(
                "UPDATE speeches "
                "SET transcription_status = 'failed', is_valid_for_scoring = false "
                "WHERE (content IS NULL OR trim(content) = '') AND audio_url IS NOT NULL"
            )
        )


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


def _ensure_lobby_reservation_columns():
    if engine is None:
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if engine.dialect.name == "postgresql":
        _ensure_lobby_reservation_enum_types()

    if "debates" in table_names:
        _ensure_debate_lobby_reservation_columns(inspector)

    if "debate_participations" in table_names:
        _ensure_debate_participation_lobby_reservation_columns(inspector)

    table_names = _ensure_reservation_invitation_table(table_names)
    inspector = inspect(engine)
    if "debate_reservation_invitations" in table_names:
        _ensure_reservation_invitation_columns(inspector)
    _ensure_lobby_reservation_indexes(table_names)


def _ensure_lobby_reservation_enum_types():
    enum_definitions = {
        "debate_mode_enum": ("teacher_assigned", "student_lobby", "teacher_reserved"),
        "debate_visibility_enum": ("public", "private"),
        "debate_reservation_status_enum": (
            "draft",
            "scheduled",
            "checkin_open",
            "waiting",
            "in_progress",
            "completed",
            "cancelled",
        ),
        "debate_attendance_status_enum": ("not_checked_in", "checked_in", "absent"),
        "reservation_invitation_read_status_enum": ("unread", "read"),
        "reservation_invitation_response_status_enum": (
            "pending",
            "accepted",
            "rejected",
            "expired",
        ),
    }

    with engine.begin() as conn:
        for enum_name, values in enum_definitions.items():
            escaped_values = ", ".join(f"'{value}'" for value in values)
            conn.execute(
                text(
                    f"""
                    DO $$ BEGIN
                        CREATE TYPE {enum_name} AS ENUM ({escaped_values});
                    EXCEPTION
                        WHEN duplicate_object THEN null;
                    END $$;
                    """
                )
            )


def _ensure_debate_lobby_reservation_columns(inspector):
    existing_columns = {col["name"] for col in inspector.get_columns("debates")}
    required_columns = [
        ("mode", _column_type("debate_mode_enum", "VARCHAR(32)") + " NOT NULL DEFAULT 'teacher_assigned'"),
        ("room_name", "VARCHAR(100)"),
        ("visibility", _column_type("debate_visibility_enum", "VARCHAR(16)") + " NOT NULL DEFAULT 'private'"),
        ("join_password_hash", "VARCHAR(255)"),
        ("password_updated_at", "TIMESTAMP"),
        ("capacity", "INTEGER NOT NULL DEFAULT 4"),
        ("creator_user_id", _uuid_type()),
        ("owner_user_id", _uuid_type()),
        ("host_user_id", _uuid_type()),
        ("scheduled_start_time", "TIMESTAMP"),
        ("checkin_open_time", "TIMESTAMP"),
        ("checkin_close_time", "TIMESTAMP"),
        ("allow_spectators", "BOOLEAN NOT NULL DEFAULT false"),
        ("reservation_status", _column_type("debate_reservation_status_enum", "VARCHAR(32)")),
        ("reservation_published_at", "TIMESTAMP"),
        ("cancelled_at", "TIMESTAMP"),
        ("cancel_reason", "TEXT"),
    ]

    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("ALTER TABLE debates ALTER COLUMN class_id DROP NOT NULL"))
            conn.execute(text("ALTER TABLE debates ALTER COLUMN teacher_id DROP NOT NULL"))

        for column_name, column_type in required_columns:
            if column_name in existing_columns:
                continue
            conn.execute(text(f"ALTER TABLE debates ADD COLUMN {column_name} {column_type}"))

        conn.execute(
            text(
                "UPDATE debates "
                "SET mode = COALESCE(mode, 'teacher_assigned'), "
                "visibility = COALESCE(visibility, 'private'), "
                "capacity = COALESCE(capacity, 4), "
                "creator_user_id = COALESCE(creator_user_id, teacher_id), "
                "owner_user_id = COALESCE(owner_user_id, teacher_id), "
                "host_user_id = COALESCE(host_user_id, teacher_id), "
                "allow_spectators = COALESCE(allow_spectators, false)"
            )
        )


def _ensure_debate_participation_lobby_reservation_columns(inspector):
    existing_columns = {col["name"] for col in inspector.get_columns("debate_participations")}
    required_columns = [
        ("is_moderator", "BOOLEAN NOT NULL DEFAULT false"),
        ("is_room_owner", "BOOLEAN NOT NULL DEFAULT false"),
        ("invitation_id", _uuid_type()),
        ("invited_by", _uuid_type()),
        ("attendance_status", _column_type("debate_attendance_status_enum", "VARCHAR(32)")),
        ("checked_in_at", "TIMESTAMP"),
        ("seat_order", "INTEGER"),
        ("left_at", "TIMESTAMP"),
        ("last_seen_at", "TIMESTAMP"),
    ]

    with engine.begin() as conn:
        for column_name, column_type in required_columns:
            if column_name in existing_columns:
                continue
            conn.execute(text(f"ALTER TABLE debate_participations ADD COLUMN {column_name} {column_type}"))

        conn.execute(
            text(
                "UPDATE debate_participations "
                "SET is_moderator = COALESCE(is_moderator, false), "
                "is_room_owner = COALESCE(is_room_owner, false)"
            )
        )


def _ensure_reservation_invitation_table(table_names: set[str]) -> set[str]:
    if "debate_reservation_invitations" in table_names:
        return table_names

    try:
        from models.debate import DebateReservationInvitation

        DebateReservationInvitation.__table__.create(bind=engine, checkfirst=True)
    except Exception as exc:  # pragma: no cover - defensive startup compatibility
        logger.warning("Failed to ensure debate_reservation_invitations table: %s", exc)
        return table_names

    return set(inspect(engine).get_table_names())


def _ensure_reservation_invitation_columns(inspector):
    existing_columns = {
        col["name"] for col in inspector.get_columns("debate_reservation_invitations")
    }
    required_columns = [
        ("revoked_at", "TIMESTAMP"),
        ("revoked_by_teacher_id", _uuid_type()),
        ("revoke_reason", "TEXT"),
    ]

    with engine.begin() as conn:
        for column_name, column_type in required_columns:
            if column_name in existing_columns:
                continue
            conn.execute(
                text(
                    "ALTER TABLE debate_reservation_invitations "
                    f"ADD COLUMN {column_name} {column_type}"
                )
            )


def _ensure_lobby_reservation_indexes(table_names: set[str]):
    index_definitions = []

    if "debates" in table_names:
        index_definitions.extend(
            [
                (
                    "idx_debates_mode_status_created_at",
                    "debates",
                    "mode, status, created_at",
                ),
                ("idx_debates_lobby_visibility", "debates", "mode, visibility, status"),
                (
                    "idx_debates_reservation_time",
                    "debates",
                    "mode, reservation_status, scheduled_start_time",
                ),
                (
                    "idx_debates_teacher_reserved",
                    "debates",
                    "teacher_id, mode, scheduled_start_time",
                ),
                ("idx_debates_creator", "debates", "creator_user_id, created_at"),
                ("idx_debates_host", "debates", "host_user_id"),
            ]
        )

    if "debate_participations" in table_names:
        index_definitions.extend(
            [
                (
                    "idx_participations_debate_active",
                    "debate_participations",
                    "debate_id, left_at",
                ),
                ("idx_participations_user", "debate_participations", "user_id, joined_at"),
                (
                    "idx_participations_moderator",
                    "debate_participations",
                    "debate_id, is_moderator",
                ),
                ("idx_participations_seat", "debate_participations", "debate_id, seat_order"),
            ]
        )

    if "debate_reservation_invitations" in table_names:
        index_definitions.extend(
            [
                (
                    "idx_invitation_student_status",
                    "debate_reservation_invitations",
                    "student_id, response_status, attendance_status",
                ),
                (
                    "idx_invitation_debate_attendance",
                    "debate_reservation_invitations",
                    "debate_id, attendance_status",
                ),
                (
                    "idx_invitation_teacher_created",
                    "debate_reservation_invitations",
                    "invited_by_teacher_id, created_at",
                ),
                (
                    "idx_invitation_expires",
                    "debate_reservation_invitations",
                    "expires_at, response_status",
                ),
                (
                    "idx_invitation_debate_revoked",
                    "debate_reservation_invitations",
                    "debate_id, revoked_at",
                ),
            ]
        )

    with engine.begin() as conn:
        for index_name, table_name, columns in index_definitions:
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})")
            )

        if "debate_participations" in table_names:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_participation_active_user "
                    "ON debate_participations (debate_id, user_id) "
                    "WHERE left_at IS NULL"
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_participation_active_seat "
                    "ON debate_participations (debate_id, seat_order) "
                    "WHERE left_at IS NULL AND seat_order IS NOT NULL"
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_participation_active_role "
                    "ON debate_participations (debate_id, stance, role) "
                    "WHERE left_at IS NULL"
                )
            )

        if "debate_reservation_invitations" in table_names:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uniq_active_invitation_debate_student "
                    "ON debate_reservation_invitations (debate_id, student_id) "
                    "WHERE revoked_at IS NULL"
                )
            )


def _column_type(postgresql_type: str, fallback_type: str) -> str:
    if engine is not None and engine.dialect.name == "postgresql":
        return postgresql_type
    return fallback_type


def _uuid_type() -> str:
    if engine is not None and engine.dialect.name == "sqlite":
        return "CHAR(32)"
    return "UUID"
