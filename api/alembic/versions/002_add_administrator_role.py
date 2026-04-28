"""Add administrator role to user_type enum

Revision ID: 002
Revises: 001
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 'administrator' value to user_type_enum
    # PostgreSQL requires a specific approach to alter enum types
    op.execute("""
        ALTER TYPE user_type_enum ADD VALUE IF NOT EXISTS 'administrator';
    """)


def downgrade() -> None:
    # Note: PostgreSQL does not support removing enum values directly
    # This would require recreating the enum type and all dependent columns
    # For safety, we'll leave the enum value in place but document the limitation
    # In a production scenario, you would need to:
    # 1. Create a new enum without 'administrator'
    # 2. Alter the column to use the new enum
    # 3. Drop the old enum
    # 4. Rename the new enum
    
    # For now, we'll just ensure no administrator users exist
    op.execute("""
        DELETE FROM users WHERE user_type = 'administrator';
    """)
    
    # Note: The enum value 'administrator' will remain in the type definition
    # This is a PostgreSQL limitation - enum values cannot be removed easily
    pass
