from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from config import BASE_DIR, settings
from models.debate import Debate


class ReportFileStorageService:
    """Private storage service for debate report artifacts."""

    LOCAL_BACKEND = "local"
    PDF_STORAGE_META_KEY = "report_pdf_storage"
    PDF_DOWNLOAD_NAME = "debate-report.pdf"

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @classmethod
    def _storage_backend(cls) -> str:
        backend = str(
            getattr(settings, "REPORT_FILE_STORAGE_BACKEND", cls.LOCAL_BACKEND)
            or cls.LOCAL_BACKEND
        ).strip().lower()
        return backend if backend == cls.LOCAL_BACKEND else cls.LOCAL_BACKEND

    @classmethod
    def _storage_root(cls) -> Path:
        raw = str(
            getattr(
                settings,
                "REPORT_FILE_STORAGE_DIR",
                "private_storage/reports",
            )
            or "private_storage/reports"
        ).strip()
        root = Path(raw)
        if not root.is_absolute():
            root = (BASE_DIR / root).resolve()
        else:
            root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    @classmethod
    def _legacy_report_root(cls) -> Path:
        upload_root = Path(str(getattr(settings, "UPLOAD_DIR", "uploads") or "uploads"))
        if not upload_root.is_absolute():
            upload_root = (BASE_DIR / upload_root).resolve()
        else:
            upload_root = upload_root.resolve()
        return upload_root / "reports"

    @staticmethod
    def _is_within_root(candidate: Path, root: Path) -> bool:
        try:
            candidate.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    @classmethod
    def build_pdf_download_name(cls) -> str:
        return cls.PDF_DOWNLOAD_NAME

    @classmethod
    def build_pdf_storage_key(cls) -> str:
        token = secrets.token_urlsafe(24).replace("-", "").replace("_", "")
        return f"{token[:2].lower()}/{token}.pdf"

    @classmethod
    def create_pdf_storage_meta(cls) -> Dict[str, Any]:
        return {
            "backend": cls._storage_backend(),
            "storage_key": cls.build_pdf_storage_key(),
            "download_name": cls.build_pdf_download_name(),
            "content_type": "application/pdf",
            "created_at": cls._utc_now_iso(),
        }

    @classmethod
    def extract_pdf_storage_meta(cls, debate: Debate | Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if isinstance(debate, dict):
            report_data = debate
        else:
            report_data = debate.report if isinstance(debate.report, dict) else {}
        meta = report_data.get(cls.PDF_STORAGE_META_KEY)
        return meta if isinstance(meta, dict) else None

    @classmethod
    def resolve_pdf_storage_path(cls, storage_meta: Dict[str, Any]) -> Path:
        if not isinstance(storage_meta, dict):
            raise ValueError("invalid storage metadata")
        if str(storage_meta.get("backend") or cls.LOCAL_BACKEND).strip().lower() != cls.LOCAL_BACKEND:
            raise ValueError("unsupported storage backend")

        storage_key = str(storage_meta.get("storage_key") or "").strip().replace("\\", "/")
        if not storage_key or storage_key.startswith("/") or ".." in storage_key.split("/"):
            raise ValueError("invalid storage key")

        target = (cls._storage_root() / storage_key).resolve()
        if not cls._is_within_root(target, cls._storage_root()):
            raise ValueError("storage path escapes root")
        return target

    @classmethod
    def _safe_legacy_path(cls, candidate: str | Path | None) -> Optional[Path]:
        if not candidate:
            return None
        path = Path(candidate)
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        else:
            path = path.resolve()
        if cls._is_within_root(path, cls._legacy_report_root()):
            return path
        return None

    @classmethod
    def legacy_default_pdf_path(cls, debate_id: str) -> Path:
        return cls._legacy_report_root() / f"debate_report_{debate_id}.pdf"

    @classmethod
    def locate_pdf_artifact(
        cls,
        debate: Debate,
        debate_id: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Path], bool]:
        storage_meta = cls.extract_pdf_storage_meta(debate)
        if storage_meta:
            try:
                stored_path = cls.resolve_pdf_storage_path(storage_meta)
            except ValueError:
                stored_path = None
            if stored_path and stored_path.is_file():
                return storage_meta, stored_path, False

        legacy_candidates = []
        legacy_path = cls._safe_legacy_path(getattr(debate, "report_pdf", None))
        if legacy_path:
            legacy_candidates.append(legacy_path)

        default_legacy_path = cls.legacy_default_pdf_path(debate_id)
        legacy_candidates.append(default_legacy_path)

        for candidate in legacy_candidates:
            if candidate.is_file():
                return None, candidate, True

        return storage_meta, None, False

    @classmethod
    def has_pdf_artifact(cls, debate: Debate, debate_id: str) -> bool:
        _, path, _ = cls.locate_pdf_artifact(debate, debate_id)
        return path is not None and path.is_file()

    @classmethod
    def _delete_managed_file(cls, file_path: Optional[Path]) -> None:
        if not file_path:
            return
        resolved = file_path.resolve()
        if cls._is_within_root(resolved, cls._storage_root()) or cls._is_within_root(
            resolved, cls._legacy_report_root()
        ):
            resolved.unlink(missing_ok=True)

    @classmethod
    def persist_pdf_bytes_for_debate(
        cls,
        debate: Debate,
        pdf_bytes: bytes,
    ) -> Tuple[Dict[str, Any], Path]:
        payload = bytes(pdf_bytes)
        if not payload or not payload.startswith(b"%PDF"):
            raise ValueError("invalid PDF payload")
        _, previous_path, _ = cls.locate_pdf_artifact(debate, str(debate.id))
        storage_meta = cls.create_pdf_storage_meta()
        target_path = cls.resolve_pdf_storage_path(storage_meta)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = target_path.with_name(
            f".{target_path.name}.{secrets.token_hex(8)}.tmp"
        )
        try:
            with temporary_path.open("xb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, target_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        finalized_meta = {
            **storage_meta,
            "byte_size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "generated_at": cls._utc_now_iso(),
        }

        report_data = debate.report if isinstance(debate.report, dict) else {}
        debate.report = {
            **report_data,
            cls.PDF_STORAGE_META_KEY: finalized_meta,
        }
        debate.report_pdf = None

        if previous_path and previous_path.resolve() != target_path.resolve():
            cls._delete_managed_file(previous_path)

        return finalized_meta, target_path

    @classmethod
    def persist_ephemeral_pdf_bytes(cls, pdf_bytes: bytes) -> Path:
        payload = bytes(pdf_bytes)
        if not payload or not payload.startswith(b"%PDF"):
            raise ValueError("invalid PDF payload")
        storage_meta = cls.create_pdf_storage_meta()
        target_path = cls.resolve_pdf_storage_path(storage_meta)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = target_path.with_name(
            f".{target_path.name}.{secrets.token_hex(8)}.tmp"
        )
        try:
            with temporary_path.open("xb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, target_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return target_path

    @classmethod
    def migrate_legacy_pdf_for_debate(
        cls,
        debate: Debate,
        debate_id: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Path], bool]:
        storage_meta, path, is_legacy = cls.locate_pdf_artifact(debate, debate_id)
        if path is None:
            return storage_meta, None, False
        if not is_legacy:
            return storage_meta, path, False

        payload = path.read_bytes()
        if not payload.startswith(b"%PDF"):
            return storage_meta, None, False
        migrated_meta, migrated_path = cls.persist_pdf_bytes_for_debate(debate, payload)
        if path.resolve() != migrated_path.resolve():
            cls._delete_managed_file(path)
        return migrated_meta, migrated_path, True

    @classmethod
    def delete_pdf_artifact_for_debate(cls, debate: Debate) -> None:
        _, file_path, _ = cls.locate_pdf_artifact(debate, str(debate.id))
        cls._delete_managed_file(file_path)
