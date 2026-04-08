"""Seed repository-root DOCX files into the shared knowledge base."""

from pathlib import Path
import uuid
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.kb_document import KBDocument
from models.user import User
from services.document_service import DocumentService
from utils.security import hash_password


logger = logging.getLogger(__name__)

DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SEED_ACCOUNT = "kb_seed_admin"
SEED_EMAIL = "kb-seed-admin@system.local"


class KBSeedService:
    @staticmethod
    def _ensure_uploader(db: Session) -> User:
        uploader = db.execute(
            select(User)
            .where(User.user_type == "administrator")
            .order_by(User.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()

        if uploader is not None:
            return uploader

        uploader = db.execute(
            select(User)
            .order_by(User.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()

        if uploader is not None:
            return uploader

        uploader = User(
            id=uuid.uuid4(),
            account=SEED_ACCOUNT,
            password_hash=hash_password(uuid.uuid4().hex),
            user_type="administrator",
            name="知识库导入账号",
            email=SEED_EMAIL,
            phone=None,
        )
        db.add(uploader)
        db.commit()
        db.refresh(uploader)
        return uploader

    @staticmethod
    async def import_repo_root_docx_files(db: Session, repo_root: Path) -> list[str]:
        docx_paths = sorted(Path(repo_root).glob("*.docx"))
        if not docx_paths:
            return []

        uploader = KBSeedService._ensure_uploader(db)
        document_service = DocumentService(db)
        imported_document_ids: list[str] = []

        for docx_path in docx_paths:
            existing_document = db.execute(
                select(KBDocument)
                .where(KBDocument.filename == docx_path.name)
                .order_by(KBDocument.uploaded_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            if existing_document and existing_document.upload_status in {
                "pending",
                "processing",
                "completed",
            }:
                logger.info(
                    "Skipping repo-root KB seed document because it already exists: %s (%s)",
                    docx_path.name,
                    existing_document.upload_status,
                )
                continue

            if existing_document and existing_document.upload_status == "failed":
                try:
                    logger.info(
                        "Retrying failed repo-root KB seed document: %s (%s)",
                        docx_path.name,
                        existing_document.id,
                    )

                    target_path = Path(existing_document.file_path)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_bytes(docx_path.read_bytes())

                    existing_document.filename = docx_path.name
                    existing_document.file_type = DOCX_MIME_TYPE
                    existing_document.file_size = docx_path.stat().st_size
                    existing_document.error_message = None
                    db.commit()

                    await document_service.process_document(str(existing_document.id))
                    imported_document_ids.append(str(existing_document.id))
                    continue
                except Exception:
                    db.rollback()
                    logger.exception(
                        "Failed to retry repo-root KB seed document: %s",
                        docx_path,
                    )
                    continue

            try:
                logger.info("Importing repo-root KB seed document: %s", docx_path.name)
                document = await document_service.upload_document(
                    file_data=docx_path.read_bytes(),
                    filename=docx_path.name,
                    file_type=DOCX_MIME_TYPE,
                    user_id=str(uploader.id),
                )
                await document_service.process_document(str(document.id))
                imported_document_ids.append(str(document.id))
            except Exception:
                logger.exception("Failed to import repo-root KB seed document: %s", docx_path)

        return imported_document_ids
