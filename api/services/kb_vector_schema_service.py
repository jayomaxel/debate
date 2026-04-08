"""Keep the KB embedding column aligned with the configured vector dimension."""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


class KBVectorSchemaService:
    @staticmethod
    async def ensure_schema_matches_vector_config(db: Session) -> bool:
        from services.config_service import ConfigService

        vector_config = await ConfigService(db).get_vector_config()
        target_dimension = int(vector_config.embedding_dimension or 1536)
        return KBVectorSchemaService.ensure_schema_matches_dimension(
            db=db,
            target_dimension=target_dimension,
        )

    @staticmethod
    def ensure_schema_matches_dimension(db: Session, target_dimension: int) -> bool:
        bind = db.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            return False

        table_exists = db.execute(
            text("SELECT to_regclass('public.kb_document_chunks')")
        ).scalar()
        if not table_exists:
            return False

        current_type = db.execute(
            text(
                """
                SELECT format_type(a.atttypid, a.atttypmod) AS format_type
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE n.nspname = 'public'
                    AND c.relname = 'kb_document_chunks'
                    AND a.attname = 'embedding'
                    AND a.attnum > 0
                    AND NOT a.attisdropped
                """
            )
        ).scalar()
        if not current_type:
            return False

        target_type = f"vector({target_dimension})"
        index_exists = db.execute(
            text("SELECT to_regclass('public.idx_kb_chunks_embedding')")
        ).scalar()

        if current_type == target_type and index_exists:
            return False

        non_null_embeddings = int(
            db.execute(
                text(
                    "SELECT count(*) FROM kb_document_chunks "
                    "WHERE embedding IS NOT NULL"
                )
            ).scalar()
            or 0
        )

        if current_type != target_type and non_null_embeddings > 0:
            if str(current_type).startswith("vector("):
                logger.warning(
                    "Skipping KB embedding column change from %s to %s because %s "
                    "stored embeddings would need to be regenerated.",
                    current_type,
                    target_type,
                    non_null_embeddings,
                )
                return False

            incompatible_rows = int(
                db.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM kb_document_chunks
                        WHERE embedding IS NOT NULL
                            AND cardinality(embedding) <> :target_dimension
                        """
                    ),
                    {"target_dimension": target_dimension},
                ).scalar()
                or 0
            )
            if incompatible_rows > 0:
                logger.warning(
                    "Skipping KB embedding column change to %s because %s stored "
                    "rows have incompatible dimensions.",
                    target_type,
                    incompatible_rows,
                )
                return False

        logger.info(
            "Aligning KB embedding schema: current_type=%s, target_type=%s",
            current_type,
            target_type,
        )

        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.execute(text("DROP INDEX IF EXISTS idx_kb_chunks_embedding"))

        if current_type != target_type:
            db.execute(
                text(
                    f"""
                    ALTER TABLE kb_document_chunks
                    ALTER COLUMN embedding
                    TYPE vector({target_dimension})
                    USING CASE
                        WHEN embedding IS NULL THEN NULL
                        ELSE embedding::vector({target_dimension})
                    END
                    """
                )
            )

        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding
                ON kb_document_chunks
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
                """
            )
        )
        db.commit()
        return True
