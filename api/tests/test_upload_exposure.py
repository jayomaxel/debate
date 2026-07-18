from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from main import app
from services.file_access_service import FileAccessService, PrivateFileNotFound


def test_private_upload_root_is_not_publicly_mounted():
    mounted_paths = {getattr(route, "path", None) for route in app.routes}

    assert "/uploads" not in mounted_paths
    assert "/uploads/audio" not in mounted_paths
    assert "/uploads/asr" not in mounted_paths


def test_anonymous_request_cannot_read_private_audio_by_guessed_path():
    response = TestClient(app).get("/uploads/audio/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav")

    assert response.status_code == 404


def test_private_upload_path_rejects_files_outside_upload_root(
    tmp_path, monkeypatch
):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"private")
    with pytest.raises(PrivateFileNotFound):
        FileAccessService.resolve_private_path(str(outside), (upload_root,))


def test_private_upload_path_accepts_file_inside_upload_root(
    tmp_path, monkeypatch
):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    document = upload_root / "document.pdf"
    document.write_bytes(b"private")
    resolved = FileAccessService.resolve_private_path(str(document), (upload_root,))

    assert resolved == document.resolve()
