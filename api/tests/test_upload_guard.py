import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, File, UploadFile
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from middleware.upload_guard import UploadGuardMiddleware
from services.audit_service import AuditService


@pytest.fixture
def upload_client():
    AuditService.clear_events()
    app = FastAPI()
    app.add_middleware(UploadGuardMiddleware)

    @app.post("/api/admin/kb/documents")
    async def upload_admin_document(file: UploadFile = File(...)):
        content = await file.read()
        return {"filename": file.filename, "size": len(content)}

    @app.post("/api/auth/profile/avatar/upload")
    async def upload_avatar(file: UploadFile = File(...)):
        content = await file.read()
        return {"filename": file.filename, "size": len(content)}

    @app.post("/api/voice/asr/transcribe")
    async def upload_asr_audio(file: UploadFile = File(...)):
        content = await file.read()
        return {"filename": file.filename, "size": len(content)}

    @app.post("/api/teacher/debates/{debate_id}/support-documents")
    async def upload_support_document(debate_id: str, file: UploadFile = File(...)):
        content = await file.read()
        return {"debate_id": debate_id, "filename": file.filename, "size": len(content)}

    with TestClient(app) as client:
        yield client

    AuditService.clear_events()


def test_valid_pdf_upload_passes_and_reaches_downstream(upload_client):
    response = upload_client.post(
        "/api/admin/kb/documents",
        files={"file": ("lesson.pdf", b"%PDF-1.7\nmock-pdf", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {"filename": "lesson.pdf", "size": 17}


def test_invalid_document_extension_is_blocked(upload_client):
    response = upload_client.post(
        "/api/admin/kb/documents",
        files={"file": ("lesson.exe", b"MZfake", "application/octet-stream")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "extension_invalid"
    assert payload["request_id"].startswith("req_")


def test_invalid_document_mime_is_blocked(upload_client):
    response = upload_client.post(
        "/api/admin/kb/documents",
        files={"file": ("lesson.pdf", b"%PDF-1.4\nmock-pdf", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "mime_invalid"


def test_invalid_document_magic_number_is_blocked(upload_client):
    response = upload_client.post(
        "/api/admin/kb/documents",
        files={"file": ("lesson.pdf", b"not-a-real-pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "magic_number_invalid"


def test_avatar_size_limit_is_enforced(upload_client):
    oversized_png = b"\x89PNG\r\n\x1a\n" + (b"0" * (2 * 1024 * 1024 + 1))

    response = upload_client.post(
        "/api/auth/profile/avatar/upload",
        files={"file": ("avatar.png", oversized_png, "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "file_too_large"


def test_valid_audio_upload_passes(upload_client):
    response = upload_client.post(
        "/api/voice/asr/transcribe",
        files={"file": ("voice.webm", b"\x1a\x45\xdf\xa3mock-webm", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "voice.webm"


def test_teacher_support_document_route_is_guarded(upload_client):
    response = upload_client.post(
        "/api/teacher/debates/debate-001/support-documents",
        files={"file": ("support.txt", b"plain-text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "extension_invalid"
