"""add user avatar columns

Revision ID: 018
Revises: 017
Create Date: 2026-07-17

"""

from alembic import op
import sqlalchemy as sa


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


AVATAR_COLUMNS = (
    sa.Column("avatar_blob", sa.LargeBinary(), nullable=True),
    sa.Column("avatar_mime_type", sa.String(length=100), nullable=True),
    sa.Column("avatar_filename", sa.String(length=255), nullable=True),
    sa.Column("avatar_default_key", sa.String(length=64), nullable=True),
)


def _existing_user_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("users")}


def upgrade() -> None:
    existing_columns = _existing_user_columns()
    for column in AVATAR_COLUMNS:
        if column.name not in existing_columns:
            op.add_column("users", column)


def downgrade() -> None:
    existing_columns = _existing_user_columns()
    for column in reversed(AVATAR_COLUMNS):
        if column.name in existing_columns:
            op.drop_column("users", column.name)
