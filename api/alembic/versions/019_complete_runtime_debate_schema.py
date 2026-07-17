"""complete runtime debate and speech schema

Revision ID: 019
Revises: 018
Create Date: 2026-07-17

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


DEBATE_COLUMNS = (
    sa.Column("report", sa.JSON(), nullable=True),
    sa.Column("report_pdf", sa.Text(), nullable=True),
)

SPEECH_COLUMNS = (
    sa.Column("match_state", sa.String(length=32), nullable=True),
    sa.Column("side", sa.String(length=16), nullable=True),
    sa.Column("speaker_position", sa.Integer(), nullable=True),
    sa.Column("started_at", sa.DateTime(), nullable=True),
    sa.Column("ended_at", sa.DateTime(), nullable=True),
    sa.Column("official_duration_sec", sa.Integer(), nullable=True),
    sa.Column("actual_duration_sec", sa.Integer(), nullable=True),
)

EVENT_LOG_INDEXES = (
    ("idx_debate_event_logs_debate_created", ("debate_id", "created_at")),
    ("idx_debate_event_logs_room_created", ("room_id", "created_at")),
    ("idx_debate_event_logs_type_state", ("event_type", "match_state")),
)


def _inspector():
    return sa.inspect(op.get_bind())


def _existing_columns(table_name: str) -> set[str]:
    inspector = _inspector()
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _uuid_type():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def _add_missing_columns(table_name: str, columns) -> None:
    existing_columns = _existing_columns(table_name)
    for column in columns:
        if column.name not in existing_columns:
            op.add_column(table_name, column)


def _create_event_log_table() -> None:
    inspector = _inspector()
    if "debate_event_logs" not in inspector.get_table_names():
        uuid_type = _uuid_type()
        op.create_table(
            "debate_event_logs",
            sa.Column("id", uuid_type, primary_key=True),
            sa.Column(
                "debate_id",
                uuid_type,
                sa.ForeignKey("debates.id"),
                nullable=False,
            ),
            sa.Column("room_id", sa.String(length=64), nullable=False),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("match_state", sa.String(length=32), nullable=True),
            sa.Column(
                "actor_user_id",
                uuid_type,
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
            sa.Column("actor_role", sa.String(length=32), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=True,
                server_default=sa.func.now(),
            ),
        )

    inspector = _inspector()
    existing_indexes = {
        index["name"]
        for index in inspector.get_indexes("debate_event_logs")
        if index.get("name")
    }
    for index_name, columns in EVENT_LOG_INDEXES:
        if index_name not in existing_indexes:
            op.create_index(index_name, "debate_event_logs", list(columns))


def upgrade() -> None:
    _add_missing_columns("debates", DEBATE_COLUMNS)
    _add_missing_columns("speeches", SPEECH_COLUMNS)
    _create_event_log_table()


def downgrade() -> None:
    inspector = _inspector()
    if "debate_event_logs" in inspector.get_table_names():
        op.drop_table("debate_event_logs")

    existing_speech_columns = _existing_columns("speeches")
    for column in reversed(SPEECH_COLUMNS):
        if column.name in existing_speech_columns:
            op.drop_column("speeches", column.name)

    existing_debate_columns = _existing_columns("debates")
    for column in reversed(DEBATE_COLUMNS):
        if column.name in existing_debate_columns:
            op.drop_column("debates", column.name)
