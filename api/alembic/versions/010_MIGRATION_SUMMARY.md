# Migration 010: Knowledge Base Tables

## Overview
This migration creates the database schema for the Preparation Assistant feature, which enables administrators to manage a knowledge base of learning materials and allows students to query this knowledge base through natural language questions.

## Changes

### 1. PostgreSQL Extension
- **Enables pgvector extension**: Required for storing and querying vector embeddings for semantic search

### 2. Enum Type
- **upload_status_enum**: Defines the status of document processing
  - `pending`: Document uploaded, waiting for processing
  - `processing`: Document is being parsed, chunked, and vectorized
  - `completed`: Document successfully processed and ready for queries
  - `failed`: Document processing failed (error stored in error_message)

### 3. Tables Created

#### kb_documents
Stores metadata about uploaded knowledge base documents.

**Columns:**
- `id` (UUID): Primary key
- `filename` (VARCHAR(255)): Original filename
- `file_path` (VARCHAR(512)): Path to stored file on disk
- `file_type` (VARCHAR(100)): MIME type (PDF or DOCX only)
- `file_size` (INTEGER): File size in bytes
- `upload_status` (upload_status_enum): Processing status
- `error_message` (TEXT): Error details if processing failed
- `uploaded_by` (UUID): Foreign key to users table
- `uploaded_at` (TIMESTAMP): Upload timestamp
- `processed_at` (TIMESTAMP): Processing completion timestamp

**Constraints:**
- Foreign key: `uploaded_by` → `users.id`
- Check constraint: `file_type` must be PDF or DOCX MIME type

**Indexes:**
- `idx_kb_documents_uploaded_by`: For filtering by uploader
- `idx_kb_documents_upload_status`: For filtering by status

#### kb_document_chunks
Stores text chunks from parsed documents with their vector embeddings.

**Columns:**
- `id` (UUID): Primary key
- `document_id` (UUID): Foreign key to kb_documents
- `chunk_index` (INTEGER): Sequential index within document
- `content` (TEXT): Text content of the chunk
- `token_count` (INTEGER): Number of tokens in the chunk
- `embedding` (vector(1536)): Vector embedding for semantic search (OpenAI ada-002 dimension)
- `created_at` (TIMESTAMP): Creation timestamp

**Constraints:**
- Foreign key: `document_id` → `kb_documents.id` (CASCADE on delete)
- Unique constraint: `(document_id, chunk_index)` - ensures no duplicate chunks

**Indexes:**
- `idx_kb_chunks_document_id`: For filtering by document
- `idx_kb_chunks_embedding`: IVFFlat index for fast vector similarity search using cosine distance

#### kb_conversations
Stores student Q&A conversations with the knowledge base.

**Columns:**
- `id` (UUID): Primary key
- `user_id` (UUID): Foreign key to users table
- `session_id` (VARCHAR(100)): Frontend-generated session identifier
- `question` (TEXT): Student's question
- `answer` (TEXT): Generated answer
- `sources` (JSONB): Array of source documents and chunks used
- `created_at` (TIMESTAMP): Conversation timestamp

**Constraints:**
- Foreign key: `user_id` → `users.id`

**Indexes:**
- `idx_kb_conversations_user_session`: For retrieving conversation history
- `idx_kb_conversations_created_at`: For ordering by time (DESC)

## Vector Search Configuration

The migration creates an IVFFlat index for efficient vector similarity search:
- **Index type**: IVFFlat (Inverted File with Flat compression)
- **Distance metric**: Cosine distance (`vector_cosine_ops`)
- **Lists parameter**: 100 (number of clusters for IVF)

**Note**: The IVFFlat index performs best with data already present. Consider rebuilding the index after loading initial documents for optimal performance.

## Requirements Satisfied

This migration satisfies the following requirements from the design document:
- **Requirement 1.1**: Database structure for document management
- **Requirement 4.4**: Vector storage for embeddings with pgvector
- **Requirement 8.1**: Conversation history storage

## Running the Migration

To apply this migration:
```bash
cd api
alembic upgrade head
```

To rollback this migration:
```bash
cd api
alembic downgrade -1
```

## Dependencies

- PostgreSQL with pgvector extension installed
- Alembic migration 009 must be applied first
- Users table must exist (from initial migration)

## Next Steps

After running this migration:
1. Create SQLAlchemy models for the new tables (Task 1.2)
2. Implement DocumentService for document processing (Task 2.1)
3. Implement RAGService for question answering (Task 10.1)
