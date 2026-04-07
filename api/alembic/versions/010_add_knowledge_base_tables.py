"""add knowledge base tables

Revision ID: 010
Revises: 009
Create Date: 2026-02-01

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Create upload_status enum type
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE upload_status_enum AS ENUM ('pending', 'processing', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create kb_documents table
    op.create_table(
        "kb_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column(
            "upload_status",
            postgresql.ENUM('pending', 'processing', 'completed', 'failed', name='upload_status_enum', create_type=False),
            nullable=False,
            server_default='pending'
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.CheckConstraint(
            "file_type IN ('application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')",
            name="valid_file_type"
        ),
    )
    
    # Create indexes for kb_documents
    op.create_index("idx_kb_documents_uploaded_by", "kb_documents", ["uploaded_by"])
    op.create_index("idx_kb_documents_upload_status", "kb_documents", ["upload_status"])
    
    # Create kb_document_chunks table with vector embeddings
    op.create_table(
        "kb_document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),  # Will be converted to vector type
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], ["kb_documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "chunk_index", name="unique_document_chunk"),
    )
    
    # Convert embedding column to vector type (pgvector)
    op.execute("ALTER TABLE kb_document_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")
    
    # Create indexes for kb_document_chunks
    op.create_index("idx_kb_chunks_document_id", "kb_document_chunks", ["document_id"])
    
    # Create IVFFlat index for vector similarity search (cosine distance)
    # Note: This requires some data to be present for optimal performance
    # The index will be created but may need to be rebuilt after data is loaded
    op.execute("""
        CREATE INDEX idx_kb_chunks_embedding 
        ON kb_document_chunks 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    
    # Create kb_conversations table
    op.create_table(
        "kb_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sources", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    
    # Create indexes for kb_conversations
    op.create_index("idx_kb_conversations_user_session", "kb_conversations", ["user_id", "session_id"])
    op.create_index("idx_kb_conversations_created_at", "kb_conversations", ["created_at"], postgresql_using="btree", postgresql_ops={"created_at": "DESC"})


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("kb_conversations")
    op.drop_table("kb_document_chunks")
    op.drop_table("kb_documents")
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS upload_status_enum")
    
    # Note: We don't drop the vector extension as it might be used by other tables
    # If you need to drop it, uncomment the following line:
    # op.execute("DROP EXTENSION IF EXISTS vector")
