from pathlib import Path

import pytest
from fastapi import HTTPException

from main import app
from routers import teacher


def test_private_upload_root_is_not_publicly_mounted():
    mounted_paths = {getattr(route, "path", None) for route in app.routes}

    assert "/uploads" not in mounted_paths
    assert "/uploads/audio" in mounted_paths
    assert "/uploads/asr" in mounted_paths


def test_private_upload_path_rejects_files_outside_upload_root(
    tmp_path, monkeypatch
):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"private")
    monkeypatch.setattr(teacher.settings, "UPLOAD_DIR", str(upload_root))

    with pytest.raises(HTTPException) as exc_info:
        teacher._resolve_private_upload_path(str(outside))

    assert exc_info.value.status_code == 404


def test_private_upload_path_accepts_file_inside_upload_root(
    tmp_path, monkeypatch
):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    document = upload_root / "document.pdf"
    document.write_bytes(b"private")
    monkeypatch.setattr(teacher.settings, "UPLOAD_DIR", str(upload_root))

    resolved = teacher._resolve_private_upload_path(str(document))

    assert resolved == document.resolve()
