from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from io import BytesIO
from pathlib import Path
from typing import Optional

from config import settings


DOCUMENT_MIME_TYPES = {
    ".pdf": frozenset({"application/pdf"}),
    ".docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        }
    ),
}

IMAGE_MIME_TYPES = {
    ".png": frozenset({"image/png"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".webp": frozenset({"image/webp"}),
}

AUDIO_MIME_TYPES = {
    ".webm": frozenset({"audio/webm", "video/webm", "application/octet-stream"}),
    ".wav": frozenset({"audio/wav", "audio/x-wav", "audio/wave"}),
    ".mp3": frozenset({"audio/mpeg", "audio/mp3"}),
    ".ogg": frozenset({"audio/ogg", "application/ogg"}),
    ".m4a": frozenset({"audio/mp4", "audio/x-m4a", "video/mp4"}),
    ".aac": frozenset({"audio/aac", "audio/x-aac"}),
    ".flac": frozenset({"audio/flac", "audio/x-flac"}),
    ".mp4": frozenset({"audio/mp4", "video/mp4"}),
}


@dataclass(frozen=True)
class UploadPart:
    field_name: str
    filename: str
    content_type: str
    data: bytes

    @property
    def extension(self) -> str:
        return Path(self.filename).suffix.lower()

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class UploadPolicy:
    name: str
    target_type: str
    path_pattern: re.Pattern[str]
    methods: frozenset[str]
    max_bytes: int
    allowed_mime_types: dict[str, frozenset[str]]

    def matches(self, path: str, method: str) -> bool:
        return method.upper() in self.methods and bool(self.path_pattern.fullmatch(path))

    @property
    def allowed_extensions(self) -> frozenset[str]:
        return frozenset(self.allowed_mime_types.keys())


UPLOAD_POLICIES = (
    UploadPolicy(
        name="admin_kb_document",
        target_type="knowledge_document",
        path_pattern=re.compile(r"^/api/admin/kb/documents$"),
        methods=frozenset({"POST"}),
        max_bytes=settings.MAX_UPLOAD_SIZE,
        allowed_mime_types=DOCUMENT_MIME_TYPES,
    ),
    UploadPolicy(
        name="profile_avatar",
        target_type="profile_avatar",
        path_pattern=re.compile(r"^/api/auth/profile/avatar/upload$"),
        methods=frozenset({"POST"}),
        max_bytes=settings.AVATAR_MAX_UPLOAD_SIZE,
        allowed_mime_types=IMAGE_MIME_TYPES,
    ),
    UploadPolicy(
        name="asr_audio",
        target_type="asr_audio",
        path_pattern=re.compile(r"^/api/voice/asr/transcribe$"),
        methods=frozenset({"POST"}),
        max_bytes=settings.MAX_UPLOAD_SIZE,
        allowed_mime_types=AUDIO_MIME_TYPES,
    ),
    UploadPolicy(
        name="teacher_support_document",
        target_type="support_document",
        path_pattern=re.compile(r"^/api/teacher/debates/[^/]+/support-documents$"),
        methods=frozenset({"POST"}),
        max_bytes=settings.MAX_UPLOAD_SIZE,
        allowed_mime_types=DOCUMENT_MIME_TYPES,
    ),
)


def is_multipart_request(content_type: Optional[str]) -> bool:
    return "multipart/form-data" in str(content_type or "").lower()


def resolve_upload_policy(path: str, method: str) -> Optional[UploadPolicy]:
    for policy in UPLOAD_POLICIES:
        if policy.matches(path, method):
            return policy
    return None


def parse_multipart_upload_parts(content_type: str, body: bytes) -> list[UploadPart]:
    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: "
        + content_type.encode("utf-8")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + body
    )
    if not message.is_multipart():
        return []

    parts: list[UploadPart] = []
    for part in message.iter_parts():
        filename = str(part.get_filename() or "").strip()
        if not filename:
            continue
        field_name = str(
            part.get_param("name", header="content-disposition") or "file"
        ).strip()
        payload = part.get_payload(decode=True) or b""
        parts.append(
            UploadPart(
                field_name=field_name,
                filename=filename,
                content_type=str(part.get_content_type() or "").lower().strip(),
                data=payload,
            )
        )
    return parts


def validate_upload_part(policy: UploadPolicy, part: UploadPart) -> Optional[tuple[str, str]]:
    extension = part.extension
    if extension not in policy.allowed_extensions:
        return "extension_invalid", _build_extension_message(policy)

    if part.size > policy.max_bytes:
        return "file_too_large", _build_size_message(policy.max_bytes)

    if not _is_mime_allowed(policy, extension, part.content_type):
        return "mime_invalid", _build_mime_message(policy)

    if not _matches_magic_number(extension, part.data):
        return "magic_number_invalid", _build_magic_message(policy)

    return None


def _is_mime_allowed(policy: UploadPolicy, extension: str, content_type: str) -> bool:
    normalized = str(content_type or "").lower().strip()
    if not normalized:
        return True
    if normalized == "application/octet-stream":
        return True
    allowed = policy.allowed_mime_types.get(extension, frozenset())
    return normalized in allowed


def _matches_magic_number(extension: str, data: bytes) -> bool:
    if extension == ".pdf":
        return data.startswith(b"%PDF-")
    if extension == ".docx":
        return _is_docx(data)
    if extension == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return data.startswith(b"\xff\xd8\xff")
    if extension == ".webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if extension == ".webm":
        return data.startswith(b"\x1a\x45\xdf\xa3")
    if extension == ".wav":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if extension == ".mp3":
        return data.startswith(b"ID3") or (
            len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0
        )
    if extension == ".ogg":
        return data.startswith(b"OggS")
    if extension in {".m4a", ".mp4"}:
        return len(data) >= 12 and data[4:8] == b"ftyp"
    if extension == ".aac":
        return len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xF0) == 0xF0
    if extension == ".flac":
        return data.startswith(b"fLaC")
    return False


def _is_docx(data: bytes) -> bool:
    if not data.startswith(b"PK"):
        return False
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and any(
        name.startswith("word/") for name in names
    )


def _build_extension_message(policy: UploadPolicy) -> str:
    if policy.target_type in {"knowledge_document", "support_document"}:
        return "Only PDF and DOCX uploads are allowed for this object."
    if policy.target_type == "profile_avatar":
        return "Only PNG, JPEG, and WEBP avatar uploads are allowed."
    if policy.target_type == "asr_audio":
        return "Only supported audio uploads are allowed for ASR transcription."
    return "Upload has been blocked by the security policy."


def _build_mime_message(policy: UploadPolicy) -> str:
    if policy.target_type in {"knowledge_document", "support_document"}:
        return "The uploaded document MIME type is not allowed."
    if policy.target_type == "profile_avatar":
        return "The uploaded avatar MIME type is not allowed."
    if policy.target_type == "asr_audio":
        return "The uploaded audio MIME type is not allowed."
    return "The uploaded file MIME type is not allowed."


def _build_magic_message(policy: UploadPolicy) -> str:
    if policy.target_type in {"knowledge_document", "support_document"}:
        return "The uploaded document content does not match its file type."
    if policy.target_type == "profile_avatar":
        return "The uploaded avatar content does not match its file type."
    if policy.target_type == "asr_audio":
        return "The uploaded audio content does not match its file type."
    return "The uploaded file content does not match its file type."


def _build_size_message(max_bytes: int) -> str:
    return f"Uploaded file exceeds the {int(max_bytes / (1024 * 1024))}MB limit."
