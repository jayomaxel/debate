"""add durable background jobs

Revision ID: 020
Revises: 019
Create Date: 2026-07-18

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def _uuid_type():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "background_jobs" not in inspector.get_table_names():
        op.create_table(
            "background_jobs",
            sa.Column("id", _uuid_type(), primary_key=True),
            sa.Column("job_type", sa.String(length=64), nullable=False),
            sa.Column("dedupe_key", sa.String(length=255), nullable=False),
            sa.Column("target_type", sa.String(length=64), nullable=True),
            sa.Column("target_id", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "available_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("claimed_by", sa.String(length=128), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "status IN ('queued', 'running', 'succeeded', 'failed', "
                "'cancelled', 'dead_letter')",
                name="ck_background_jobs_status",
            ),
            sa.CheckConstraint(
                "attempt_count >= 0 AND max_attempts > 0",
                name="ck_background_jobs_attempts",
            ),
            sa.UniqueConstraint(
                "job_type",
                "dedupe_key",
                name="uq_background_jobs_type_dedupe",
            ),
        )

    inspector = sa.inspect(op.get_bind())
    existing_indexes = {
        item["name"]
        for item in inspector.get_indexes("background_jobs")
        if item.get("name")
    }
    if "idx_background_jobs_claim" not in existing_indexes:
        op.create_index(
            "idx_background_jobs_claim",
            "background_jobs",
            ["status", "priority", "available_at", "created_at"],
            postgresql_where=sa.text("status = 'queued'"),
            sqlite_where=sa.text("status = 'queued'"),
        )
    if "idx_background_jobs_expired_lease" not in existing_indexes:
        op.create_index(
            "idx_background_jobs_expired_lease",
            "background_jobs",
            ["lease_expires_at"],
            postgresql_where=sa.text("status = 'running'"),
            sqlite_where=sa.text("status = 'running'"),
        )
    if "idx_background_jobs_target_created" not in existing_indexes:
        op.create_index(
            "idx_background_jobs_target_created",
            "background_jobs",
            ["target_type", "target_id", "created_at"],
        )


def downgrade() -> None:
    if "background_jobs" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("background_jobs")

