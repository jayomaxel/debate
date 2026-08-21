"""align teaching design storage with the frozen contract

Revision ID: 024
Revises: 023
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "class_teaching_design_versions" not in inspector.get_table_names():
        return
    columns = {
        column["name"]
        for column in inspector.get_columns("class_teaching_design_versions")
    }
    additions = (
        ("extraction_result", sa.Column("extraction_result", sa.JSON(), nullable=True)),
        ("confidence", sa.Column("confidence", sa.JSON(), nullable=True)),
        ("missing_fields", sa.Column("missing_fields", sa.JSON(), nullable=True)),
        ("source_excerpt_map", sa.Column("source_excerpt_map", sa.JSON(), nullable=True)),
        (
            "status",
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="needs_review",
            ),
        ),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("class_teaching_design_versions", column)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "class_teaching_design_versions" not in inspector.get_table_names():
        return
    columns = {
        column["name"]
        for column in inspector.get_columns("class_teaching_design_versions")
    }
    for column_name in (
        "status",
        "source_excerpt_map",
        "missing_fields",
        "confidence",
        "extraction_result",
    ):
        if column_name in columns:
            op.drop_column("class_teaching_design_versions", column_name)
