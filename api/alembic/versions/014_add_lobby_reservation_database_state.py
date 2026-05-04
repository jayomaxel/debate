"""add lobby and reservation database state

Revision ID: 014
Revises: 013
Create Date: 2026-05-03

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


DEBATE_MODE_VALUES = ("teacher_assigned", "student_lobby", "teacher_reserved")
DEBATE_VISIBILITY_VALUES = ("public", "private")
DEBATE_RESERVATION_STATUS_VALUES = (
    "draft",
    "scheduled",
    "checkin_open",
    "waiting",
    "in_progress",
    "completed",
    "cancelled",
)
ATTENDANCE_STATUS_VALUES = ("not_checked_in", "checked_in", "absent")
INVITATION_READ_STATUS_VALUES = ("unread", "read")
INVITATION_RESPONSE_STATUS_VALUES = ("pending", "accepted", "rejected", "expired")


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    uuid_type = _uuid_type(is_postgresql)

    if is_postgresql:
        _create_postgresql_enum("debate_mode_enum", DEBATE_MODE_VALUES)
        _create_postgresql_enum("debate_visibility_enum", DEBATE_VISIBILITY_VALUES)
        _create_postgresql_enum("debate_reservation_status_enum", DEBATE_RESERVATION_STATUS_VALUES)
        _create_postgresql_enum("debate_attendance_status_enum", ATTENDANCE_STATUS_VALUES)
        _create_postgresql_enum("reservation_invitation_read_status_enum", INVITATION_READ_STATUS_VALUES)
        _create_postgresql_enum(
            "reservation_invitation_response_status_enum",
            INVITATION_RESPONSE_STATUS_VALUES,
        )

    debate_mode_enum = _enum_type("debate_mode_enum", DEBATE_MODE_VALUES, is_postgresql)
    debate_visibility_enum = _enum_type("debate_visibility_enum", DEBATE_VISIBILITY_VALUES, is_postgresql)
    debate_reservation_status_enum = _enum_type(
        "debate_reservation_status_enum",
        DEBATE_RESERVATION_STATUS_VALUES,
        is_postgresql,
    )
    attendance_status_enum = _enum_type(
        "debate_attendance_status_enum",
        ATTENDANCE_STATUS_VALUES,
        is_postgresql,
    )
    invitation_read_status_enum = _enum_type(
        "reservation_invitation_read_status_enum",
        INVITATION_READ_STATUS_VALUES,
        is_postgresql,
    )
    invitation_response_status_enum = _enum_type(
        "reservation_invitation_response_status_enum",
        INVITATION_RESPONSE_STATUS_VALUES,
        is_postgresql,
    )

    with op.batch_alter_table("debates") as batch_op:
        if is_postgresql:
            batch_op.alter_column("class_id", existing_type=uuid_type, nullable=True)
            batch_op.alter_column("teacher_id", existing_type=uuid_type, nullable=True)
        batch_op.add_column(
            sa.Column(
                "mode",
                debate_mode_enum,
                nullable=False,
                server_default="teacher_assigned",
            )
        )
        batch_op.add_column(sa.Column("room_name", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column(
                "visibility",
                debate_visibility_enum,
                nullable=False,
                server_default="private",
            )
        )
        batch_op.add_column(sa.Column("join_password_hash", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("password_updated_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("capacity", sa.Integer(), nullable=False, server_default="4"))
        batch_op.add_column(sa.Column("creator_user_id", uuid_type, nullable=True))
        batch_op.add_column(sa.Column("owner_user_id", uuid_type, nullable=True))
        batch_op.add_column(sa.Column("host_user_id", uuid_type, nullable=True))
        batch_op.add_column(sa.Column("scheduled_start_time", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("checkin_open_time", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("checkin_close_time", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("allow_spectators", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("reservation_status", debate_reservation_status_enum, nullable=True))
        batch_op.add_column(sa.Column("reservation_published_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("cancel_reason", sa.Text(), nullable=True))
        batch_op.create_foreign_key("fk_debates_creator_user_id", "users", ["creator_user_id"], ["id"])
        batch_op.create_foreign_key("fk_debates_owner_user_id", "users", ["owner_user_id"], ["id"])
        batch_op.create_foreign_key("fk_debates_host_user_id", "users", ["host_user_id"], ["id"])

    op.execute(
        "UPDATE debates "
        "SET mode = 'teacher_assigned', "
        "visibility = 'private', "
        "capacity = 4, "
        "creator_user_id = teacher_id, "
        "owner_user_id = teacher_id, "
        "host_user_id = teacher_id, "
        "allow_spectators = false "
        "WHERE mode IS NULL "
        "OR visibility IS NULL "
        "OR capacity IS NULL "
        "OR creator_user_id IS NULL "
        "OR owner_user_id IS NULL "
        "OR host_user_id IS NULL "
        "OR allow_spectators IS NULL"
    )

    op.create_table(
        "debate_reservation_invitations",
        sa.Column("id", uuid_type, primary_key=True, default=uuid.uuid4),
        sa.Column("debate_id", uuid_type, nullable=False),
        sa.Column("student_id", uuid_type, nullable=False),
        sa.Column("invited_by_teacher_id", uuid_type, nullable=False),
        sa.Column(
            "assigned_role",
            postgresql.ENUM(
                "debater_1",
                "debater_2",
                "debater_3",
                "debater_4",
                name="debater_role_enum",
                create_type=False,
            )
            if is_postgresql
            else sa.Enum(
                "debater_1",
                "debater_2",
                "debater_3",
                "debater_4",
                name="debater_role_enum",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "assigned_stance",
            postgresql.ENUM("positive", "negative", name="stance_enum", create_type=False)
            if is_postgresql
            else sa.Enum("positive", "negative", name="stance_enum", native_enum=False),
            nullable=True,
        ),
        sa.Column(
            "is_designated_moderator",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("is_backup_moderator", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "read_status",
            invitation_read_status_enum,
            nullable=False,
            server_default="unread",
        ),
        sa.Column(
            "response_status",
            invitation_response_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "attendance_status",
            attendance_status_enum,
            nullable=False,
            server_default="not_checked_in",
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by_teacher_id", uuid_type, nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("checked_in_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["debate_id"], ["debates.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["invited_by_teacher_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["revoked_by_teacher_id"], ["users.id"]),
    )

    with op.batch_alter_table("debate_participations") as batch_op:
        batch_op.add_column(
            sa.Column("is_moderator", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("is_room_owner", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("invitation_id", uuid_type, nullable=True))
        batch_op.add_column(sa.Column("invited_by", uuid_type, nullable=True))
        batch_op.add_column(sa.Column("attendance_status", attendance_status_enum, nullable=True))
        batch_op.add_column(sa.Column("checked_in_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("seat_order", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("left_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_seen_at", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            "fk_debate_participations_invitation_id",
            "debate_reservation_invitations",
            ["invitation_id"],
            ["id"],
        )
        batch_op.create_foreign_key("fk_debate_participations_invited_by", "users", ["invited_by"], ["id"])

    op.execute(
        "UPDATE debate_participations "
        "SET is_moderator = false, is_room_owner = false "
        "WHERE is_moderator IS NULL OR is_room_owner IS NULL"
    )

    op.create_index(
        "idx_debates_mode_status_created_at",
        "debates",
        ["mode", "status", "created_at"],
    )
    op.create_index("idx_debates_lobby_visibility", "debates", ["mode", "visibility", "status"])
    op.create_index(
        "idx_debates_reservation_time",
        "debates",
        ["mode", "reservation_status", "scheduled_start_time"],
    )
    op.create_index("idx_debates_teacher_reserved", "debates", ["teacher_id", "mode", "scheduled_start_time"])
    op.create_index("idx_debates_creator", "debates", ["creator_user_id", "created_at"])
    op.create_index("idx_debates_host", "debates", ["host_user_id"])
    op.create_index("idx_participations_debate_active", "debate_participations", ["debate_id", "left_at"])
    op.create_index("idx_participations_user", "debate_participations", ["user_id", "joined_at"])
    op.create_index("idx_participations_moderator", "debate_participations", ["debate_id", "is_moderator"])
    op.create_index("idx_participations_seat", "debate_participations", ["debate_id", "seat_order"])
    op.create_index(
        "uniq_participation_active_user",
        "debate_participations",
        ["debate_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
        sqlite_where=sa.text("left_at IS NULL"),
    )
    op.create_index(
        "uniq_participation_active_seat",
        "debate_participations",
        ["debate_id", "seat_order"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL AND seat_order IS NOT NULL"),
        sqlite_where=sa.text("left_at IS NULL AND seat_order IS NOT NULL"),
    )
    op.create_index(
        "uniq_participation_active_role",
        "debate_participations",
        ["debate_id", "stance", "role"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
        sqlite_where=sa.text("left_at IS NULL"),
    )
    op.create_index(
        "idx_invitation_student_status",
        "debate_reservation_invitations",
        ["student_id", "response_status", "attendance_status"],
    )
    op.create_index(
        "idx_invitation_debate_attendance",
        "debate_reservation_invitations",
        ["debate_id", "attendance_status"],
    )
    op.create_index(
        "idx_invitation_teacher_created",
        "debate_reservation_invitations",
        ["invited_by_teacher_id", "created_at"],
    )
    op.create_index(
        "idx_invitation_expires",
        "debate_reservation_invitations",
        ["expires_at", "response_status"],
    )
    op.create_index(
        "idx_invitation_debate_revoked",
        "debate_reservation_invitations",
        ["debate_id", "revoked_at"],
    )
    op.create_index(
        "uniq_active_invitation_debate_student",
        "debate_reservation_invitations",
        ["debate_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    uuid_type = _uuid_type(is_postgresql)

    op.drop_index("uniq_active_invitation_debate_student", table_name="debate_reservation_invitations")
    op.drop_index("idx_invitation_debate_revoked", table_name="debate_reservation_invitations")
    op.drop_index("idx_invitation_expires", table_name="debate_reservation_invitations")
    op.drop_index("idx_invitation_teacher_created", table_name="debate_reservation_invitations")
    op.drop_index("idx_invitation_debate_attendance", table_name="debate_reservation_invitations")
    op.drop_index("idx_invitation_student_status", table_name="debate_reservation_invitations")
    op.drop_index("uniq_participation_active_role", table_name="debate_participations")
    op.drop_index("uniq_participation_active_seat", table_name="debate_participations")
    op.drop_index("uniq_participation_active_user", table_name="debate_participations")
    op.drop_index("idx_participations_seat", table_name="debate_participations")
    op.drop_index("idx_participations_moderator", table_name="debate_participations")
    op.drop_index("idx_participations_user", table_name="debate_participations")
    op.drop_index("idx_participations_debate_active", table_name="debate_participations")
    op.drop_index("idx_debates_host", table_name="debates")
    op.drop_index("idx_debates_creator", table_name="debates")
    op.drop_index("idx_debates_teacher_reserved", table_name="debates")
    op.drop_index("idx_debates_reservation_time", table_name="debates")
    op.drop_index("idx_debates_lobby_visibility", table_name="debates")
    op.drop_index("idx_debates_mode_status_created_at", table_name="debates")

    with op.batch_alter_table("debate_participations") as batch_op:
        batch_op.drop_constraint("fk_debate_participations_invited_by", type_="foreignkey")
        batch_op.drop_constraint("fk_debate_participations_invitation_id", type_="foreignkey")
        batch_op.drop_column("last_seen_at")
        batch_op.drop_column("left_at")
        batch_op.drop_column("seat_order")
        batch_op.drop_column("checked_in_at")
        batch_op.drop_column("attendance_status")
        batch_op.drop_column("invited_by")
        batch_op.drop_column("invitation_id")
        batch_op.drop_column("is_room_owner")
        batch_op.drop_column("is_moderator")

    op.drop_table("debate_reservation_invitations")

    with op.batch_alter_table("debates") as batch_op:
        batch_op.drop_constraint("fk_debates_host_user_id", type_="foreignkey")
        batch_op.drop_constraint("fk_debates_owner_user_id", type_="foreignkey")
        batch_op.drop_constraint("fk_debates_creator_user_id", type_="foreignkey")
        batch_op.drop_column("cancel_reason")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("reservation_published_at")
        batch_op.drop_column("reservation_status")
        batch_op.drop_column("allow_spectators")
        batch_op.drop_column("checkin_close_time")
        batch_op.drop_column("checkin_open_time")
        batch_op.drop_column("scheduled_start_time")
        batch_op.drop_column("host_user_id")
        batch_op.drop_column("owner_user_id")
        batch_op.drop_column("creator_user_id")
        batch_op.drop_column("capacity")
        batch_op.drop_column("password_updated_at")
        batch_op.drop_column("join_password_hash")
        batch_op.drop_column("visibility")
        batch_op.drop_column("room_name")
        batch_op.drop_column("mode")
        if is_postgresql:
            batch_op.alter_column("teacher_id", existing_type=uuid_type, nullable=False)
            batch_op.alter_column("class_id", existing_type=uuid_type, nullable=False)

    if is_postgresql:
        _drop_postgresql_enum("reservation_invitation_response_status_enum")
        _drop_postgresql_enum("reservation_invitation_read_status_enum")
        _drop_postgresql_enum("debate_attendance_status_enum")
        _drop_postgresql_enum("debate_reservation_status_enum")
        _drop_postgresql_enum("debate_visibility_enum")
        _drop_postgresql_enum("debate_mode_enum")


def _enum_type(name: str, values: tuple[str, ...], is_postgresql: bool):
    if is_postgresql:
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name, native_enum=False)


def _uuid_type(is_postgresql: bool):
    if is_postgresql:
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def _create_postgresql_enum(name: str, values: tuple[str, ...]) -> None:
    escaped_values = ", ".join(f"'{value}'" for value in values)
    op.execute(
        f"""
        DO $$ BEGIN
            CREATE TYPE {name} AS ENUM ({escaped_values});
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )


def _drop_postgresql_enum(name: str) -> None:
    op.execute(f"DROP TYPE IF EXISTS {name}")
