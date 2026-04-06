"""Initial migration - create all tables

Revision ID: 001
Revises: 
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建枚举类型（如果不存在）
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_type_enum AS ENUM ('teacher', 'student');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE debate_status_enum AS ENUM ('draft', 'published', 'in_progress', 'completed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE debater_role_enum AS ENUM ('debater_1', 'debater_2', 'debater_3', 'debater_4');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE stance_enum AS ENUM ('positive', 'negative');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE speaker_type_enum AS ENUM ('human', 'ai');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE debate_phase_enum AS ENUM ('opening', 'questioning', 'free_debate', 'closing');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE embedding_status_enum AS ENUM ('pending', 'processing', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE recommended_role_enum AS ENUM ('debater_1', 'debater_2', 'debater_3', 'debater_4');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # 创建 users 表
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('account', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('user_type', sa.Enum('teacher', 'student', name='user_type_enum'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('student_id', sa.String(50), nullable=True),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )
    
    # 创建 classes 表
    op.create_table(
        'classes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(20), nullable=False, unique=True, index=True),
        sa.Column('teacher_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'])
    )
    
    # 添加 users.class_id 外键
    op.create_foreign_key('fk_users_class_id', 'users', 'classes', ['class_id'], ['id'])
    
    # 创建 debates 表
    op.create_table(
        'debates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('topic', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=False),
        sa.Column('invitation_code', sa.String(6), nullable=False, unique=True, index=True),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('teacher_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('draft', 'published', 'in_progress', 'completed', name='debate_status_enum'), server_default='draft'),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id']),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'])
    )
    
    # 创建 debate_participations 表
    op.create_table(
        'debate_participations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('debate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.Enum('debater_1', 'debater_2', 'debater_3', 'debater_4', name='debater_role_enum'), nullable=False),
        sa.Column('stance', sa.Enum('positive', 'negative', name='stance_enum'), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['debate_id'], ['debates.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'])
    )
    
    # 创建 speeches 表
    op.create_table(
        'speeches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('debate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('speaker_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('speaker_type', sa.Enum('human', 'ai', name='speaker_type_enum'), nullable=False),
        sa.Column('speaker_role', sa.String(20), nullable=False),
        sa.Column('phase', sa.Enum('opening', 'questioning', 'free_debate', 'closing', name='debate_phase_enum'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('audio_url', sa.String(500), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['debate_id'], ['debates.id']),
        sa.ForeignKeyConstraint(['speaker_id'], ['users.id'])
    )
    
    # 创建 scores 表
    op.create_table(
        'scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('participation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('speech_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('logic_score', sa.Float(), nullable=False),
        sa.Column('argument_score', sa.Float(), nullable=False),
        sa.Column('response_score', sa.Float(), nullable=False),
        sa.Column('persuasion_score', sa.Float(), nullable=False),
        sa.Column('teamwork_score', sa.Float(), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['participation_id'], ['debate_participations.id']),
        sa.ForeignKeyConstraint(['speech_id'], ['speeches.id'])
    )
    
    # 创建 documents 表
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('debate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('embedding_status', sa.Enum('pending', 'processing', 'completed', 'failed', name='embedding_status_enum'), server_default='pending'),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['debate_id'], ['debates.id'])
    )
    
    # 创建 achievements 表
    op.create_table(
        'achievements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('achievement_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('icon', sa.String(100), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'])
    )
    
    # 创建 ability_assessments 表
    op.create_table(
        'ability_assessments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('personality_type', sa.String(10), nullable=True),
        sa.Column('expression_willingness', sa.Integer(), nullable=False),
        sa.Column('logical_thinking', sa.Integer(), nullable=False),
        sa.Column('recommended_role', sa.Enum('debater_1', 'debater_2', 'debater_3', 'debater_4', name='recommended_role_enum'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'])
    )
    
    # 创建 configs 表
    op.create_table(
        'configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('key', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )


def downgrade() -> None:
    # 删除所有表
    op.drop_table('configs')
    op.drop_table('ability_assessments')
    op.drop_table('achievements')
    op.drop_table('documents')
    op.drop_table('scores')
    op.drop_table('speeches')
    op.drop_table('debate_participations')
    op.drop_table('debates')
    op.drop_table('classes')
    op.drop_table('users')
    
    # 删除枚举类型
    op.execute('DROP TYPE IF EXISTS recommended_role_enum')
    op.execute('DROP TYPE IF EXISTS embedding_status_enum')
    op.execute('DROP TYPE IF EXISTS debate_phase_enum')
    op.execute('DROP TYPE IF EXISTS speaker_type_enum')
    op.execute('DROP TYPE IF EXISTS stance_enum')
    op.execute('DROP TYPE IF EXISTS debater_role_enum')
    op.execute('DROP TYPE IF EXISTS debate_status_enum')
    op.execute('DROP TYPE IF EXISTS user_type_enum')
