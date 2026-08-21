"""Centralized authorization and path handling for private files."""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import BASE_DIR, settings
from middleware.auth_middleware import check_debate_access
from models.debate import Debate
from models.document import Document
from models.kb_document import KBDocument
from models.speech import Speech
from models.user import User


PRIVATE_FILE_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
}


class PrivateFileNotFound(LookupError):
    """Use a single not-found outcome so callers do not leak object existence."""


class InvalidMediaTicket(ValueError):
    """Raised when a short-lived media ticket cannot be trusted."""


@dataclass(frozen=True)
class PrivateFile:
    path: Path
    filename: str
    media_type: str
    object_type: str
    object_id: str


class FileAccessService:
    MEDIA_TICKET_TYPE = "private_media"
    MEDIA_TICKET_TTL_SECONDS = 120
    _OBJECT_KEY_RE = re.compile(r"^(audio|asr)/([a-fA-F0-9-]{16,64}\.[A-Za-z0-9]{1,10})$")
    _SAFE_EXTENSION_RE = re.compile(r"^\.[A-Za-z0-9]{1,10}$")

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def random_object_name(original_filename: str, *, fallback_extension: str = "") -> str:
        extension = Path(str(original_filename or "")).suffix.lower()
        if not FileAccessService._SAFE_EXTENSION_RE.fullmatch(extension):
            extension = fallback_extension if FileAccessService._SAFE_EXTENSION_RE.fullmatch(fallback_extension) else ""
        return f"{uuid.uuid4().hex}{extension}"

    @staticmethod
    def _configured_upload_root() -> Path:
        return Path(settings.UPLOAD_DIR).resolve()

    @staticmethod
    def _api_upload_root() -> Path:
        return (BASE_DIR / settings.UPLOAD_DIR).resolve()

    @staticmethod
    def _support_roots() -> tuple[Path, ...]:
        configured = Path(os.getenv("UPLOAD_DIR", "uploads/documents")).resolve()
        return (configured, FileAccessService._configured_upload_root() / "documents")

    @staticmethod
    def _kb_roots() -> tuple[Path, ...]:
        configured = Path(os.getenv("KB_UPLOAD_DIR", "uploads/kb_documents")).resolve()
        return (configured, FileAccessService._configured_upload_root() / "kb_documents")

    @staticmethod
    def _report_roots() -> tuple[Path, ...]:
        return (
            FileAccessService._api_upload_root() / "reports",
            FileAccessService._configured_upload_root() / "reports",
        )

    @staticmethod
    def resolve_report_path(file_path: str | Path) -> Path:
        return FileAccessService.resolve_private_path(file_path, FileAccessService._report_roots())

    @staticmethod
    def allocate_report_path() -> Path:
        root = FileAccessService._report_roots()[0]
        root.mkdir(parents=True, exist_ok=True)
        return root / FileAccessService.random_object_name("report.pdf", fallback_extension=".pdf")

    @staticmethod
    def resolve_private_path(file_path: str | Path, allowed_roots: Iterable[Path]) -> Path:
        raw_path = Path(str(file_path or ""))
        candidate = raw_path.resolve() if raw_path.is_absolute() else (Path.cwd() / raw_path).resolve()
        for root in allowed_roots:
            resolved_root = Path(root).resolve()
            try:
                candidate.relative_to(resolved_root)
            except ValueError:
                continue
            if candidate.is_file():
                return candidate
            break
        raise PrivateFileNotFound("private file not found")

    @staticmethod
    def private_headers() -> dict[str, str]:
        return dict(PRIVATE_FILE_HEADERS)

    def _can_access_debate(self, user: User, debate_id: str) -> bool:
        if user.user_type == "administrator":
            return True
        return check_debate_access(str(user.id), str(debate_id), self.db)

    def report_pdf(self, user: User, debate_id: str) -> PrivateFile:
        debate = self.db.query(Debate).filter(Debate.id == self._uuid(debate_id)).first()
        if not debate or not self._can_access_debate(user, str(debate.id)) or not debate.report_pdf:
            raise PrivateFileNotFound("report not found")
        path = self.resolve_private_path(debate.report_pdf, self._report_roots())
        return PrivateFile(path, f"debate_report_{debate.id}.pdf", "application/pdf", "report", str(debate.id))

    def support_document(self, user: User, debate_id: str, document_id: str) -> PrivateFile:
        document = self.db.query(Document).filter(Document.id == self._uuid(document_id)).first()
        if (
            not document
            or str(document.debate_id) != str(debate_id)
            or not self._can_access_debate(user, str(document.debate_id))
        ):
            raise PrivateFileNotFound("support document not found")
        path = self.resolve_private_path(document.file_path, self._support_roots())
        return PrivateFile(
            path,
            document.filename,
            document.file_type or "application/octet-stream",
            "support_document",
            str(document.id),
        )

    def knowledge_document(self, user: User, document_id: str) -> PrivateFile:
        document = self.db.query(KBDocument).filter(KBDocument.id == self._uuid(document_id)).first()
        is_admin = user.user_type == "administrator"
        if not document or (not is_admin and not bool(document.is_published)):
            raise PrivateFileNotFound("knowledge document not found")
        path = self.resolve_private_path(document.file_path, self._kb_roots())
        return PrivateFile(
            path,
            document.filename,
            document.file_type or "application/octet-stream",
            "knowledge_document",
            str(document.id),
        )

    @staticmethod
    def media_object_key(audio_url: str) -> str:
        parsed = urlparse(str(audio_url or ""))
        path = parsed.path.replace("\\", "/")
        for prefix in ("/uploads/", "uploads/"):
            if path.startswith(prefix):
                path = path[len(prefix):]
                break
        normalized = path.strip("/")
        match = FileAccessService._OBJECT_KEY_RE.fullmatch(normalized)
        if not match:
            raise PrivateFileNotFound("media not found")
        return f"{match.group(1)}/{match.group(2)}"

    def authorize_media_reference(self, user: User, audio_url: str) -> tuple[str, Speech]:
        object_key = self.media_object_key(audio_url)
        filename = object_key.split("/", 1)[1]
        speeches = (
            self.db.query(Speech)
            .filter(Speech.audio_url.isnot(None))
            .filter(Speech.audio_url.like(f"%{filename}"))
            .all()
        )
        speech = next(
            (item for item in speeches if self._safe_media_key(item.audio_url) == object_key),
            None,
        )
        if not speech or not self._can_access_debate(user, str(speech.debate_id)):
            raise PrivateFileNotFound("media not found")
        self.resolve_media_path(object_key)
        return object_key, speech

    @staticmethod
    def _safe_media_key(value: Optional[str]) -> Optional[str]:
        try:
            return FileAccessService.media_object_key(value or "")
        except PrivateFileNotFound:
            return None

    @staticmethod
    def resolve_media_path(object_key: str) -> Path:
        normalized = FileAccessService.media_object_key(f"/uploads/{object_key}")
        kind, filename = normalized.split("/", 1)
        root = FileAccessService._configured_upload_root() / kind
        return FileAccessService.resolve_private_path(root / filename, (root,))

    @staticmethod
    def issue_media_ticket(
        *,
        user_id: str,
        object_key: str,
        speech_id: Optional[str] = None,
        owner_only: bool = False,
        provider_only: bool = False,
        ttl_seconds: int = MEDIA_TICKET_TTL_SECONDS,
    ) -> str:
        normalized_key = FileAccessService.media_object_key(f"/uploads/{object_key}")
        now = datetime.now(timezone.utc)
        payload = {
            "typ": FileAccessService.MEDIA_TICKET_TYPE,
            "sub": str(user_id),
            "object_key": normalized_key,
            "speech_id": str(speech_id) if speech_id else None,
            "owner_only": bool(owner_only),
            "provider_only": bool(provider_only),
            "iat": now,
            "exp": now + timedelta(seconds=max(1, min(int(ttl_seconds), 300))),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def resolve_ticketed_media(self, ticket: str, object_key: str) -> PrivateFile:
        normalized_key = self.media_object_key(f"/uploads/{object_key}")
        try:
            payload = jwt.decode(ticket, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError as exc:
            raise InvalidMediaTicket("invalid or expired media ticket") from exc
        if payload.get("typ") != self.MEDIA_TICKET_TYPE or payload.get("object_key") != normalized_key:
            raise InvalidMediaTicket("media ticket does not match object")
        speech_id = payload.get("speech_id")
        provider_only = bool(payload.get("provider_only"))
        if provider_only and normalized_key.startswith("asr/"):
            object_id = normalized_key
            user = None
        else:
            user = self.db.query(User).filter(User.id == self._uuid(payload.get("sub"))).first()
            if not user or str(user.account).startswith("deleted_"):
                raise InvalidMediaTicket("media ticket user is unavailable")
        if speech_id and not provider_only:
            speech = self.db.query(Speech).filter(Speech.id == self._uuid(speech_id)).first()
            if (
                not speech
                or self._safe_media_key(speech.audio_url) != normalized_key
                or not self._can_access_debate(user, str(speech.debate_id))
            ):
                raise InvalidMediaTicket("media access is no longer allowed")
            object_id = str(speech.id)
        elif payload.get("owner_only") and not provider_only:
            object_id = normalized_key
        elif not provider_only:
            raise InvalidMediaTicket("media ticket has no authorized object")
        path = self.resolve_media_path(normalized_key)
        return PrivateFile(
            path,
            path.name,
            self._media_type(path.suffix),
            "speech_media",
            object_id,
        )

    @staticmethod
    def ticketed_media_url(object_key: str, ticket: str) -> str:
        kind, filename = object_key.split("/", 1)
        return f"/api/voice/media/{kind}/{filename}?ticket={ticket}"

    @staticmethod
    def _media_type(extension: str) -> str:
        return {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".webm": "audio/webm",
            ".ogg": "audio/ogg",
            ".m4a": "audio/mp4",
            ".pcm": "application/octet-stream",
        }.get(extension.lower(), "application/octet-stream")

    @staticmethod
    def _uuid(value: object) -> object:
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            return value
