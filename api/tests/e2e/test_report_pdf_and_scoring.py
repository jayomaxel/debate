import uuid

import pytest
from fastapi.testclient import TestClient

from config import settings
from database import get_db
from main import app
from models.class_model import Class
from models.debate import Debate
from models.user import User
from routers import student as student_router
from services.report_service import ReportGenerator
from tests.test_markdown_pdf import test_markdown_to_pdf as _real_pdf_renderer_proof
from tests.test_score_fallback_isolation import (
    test_fallback_is_excluded_from_profiles_averages_rankings_and_training as _fallback_isolation_proof,
)
from utils.security import create_token, hash_password


pytestmark = [pytest.mark.e2e, pytest.mark.integration]


@pytest.mark.asyncio
async def test_real_pdf_renderer_gate():
    await _real_pdf_renderer_proof()


def test_pdf_failure_is_retryable_then_three_exports_render_once(
    tmp_path,
    monkeypatch,
    e2e_db,
    e2e_session_factory,
):
    teacher = User(
        id=uuid.uuid4(),
        account=f"pdf-e2e-teacher-{uuid.uuid4().hex[:8]}",
        name="PDF E2E Teacher",
        password_hash=hash_password("password123"),
        user_type="teacher",
        email=f"{uuid.uuid4().hex}@example.test",
    )
    class_obj = Class(
        id=uuid.uuid4(),
        name="PDF E2E Class",
        code=uuid.uuid4().hex[:10],
        teacher_id=teacher.id,
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="PDF E2E cache",
        description="",
        duration=3,
        invitation_code=uuid.uuid4().hex[:6],
        class_id=class_obj.id,
        teacher_id=teacher.id,
        status="completed",
        report_pdf=None,
    )
    markdown = "# Report\n\nCached markdown from PostgreSQL"
    debate.report = {
        "report_markdown": markdown,
        "report_markdown_hash": student_router._compute_markdown_hash(markdown, 0),
    }
    e2e_db.add(teacher)
    e2e_db.flush()
    e2e_db.add(class_obj)
    e2e_db.flush()
    e2e_db.add(debate)
    e2e_db.commit()

    def override_get_db():
        db = e2e_session_factory()
        try:
            yield db
        finally:
            db.close()

    private_root = tmp_path / "private-report-storage"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"), raising=False)
    monkeypatch.setattr(settings, "REPORT_FILE_STORAGE_DIR", str(private_root), raising=False)
    app.dependency_overrides[get_db] = override_get_db
    token = create_token({"sub": str(teacher.id), "user_type": "teacher"})
    headers = {"Authorization": f"Bearer {token}"}

    async def invalid_renderer(*args, **kwargs):
        return b"not-a-pdf"

    calls = 0

    async def counted_renderer(*args, **kwargs):
        nonlocal calls
        calls += 1
        return b"%PDF-1.4\n%atomic\n%%EOF"

    client = TestClient(app)
    try:
        monkeypatch.setattr(
            ReportGenerator,
            "render_markdown_to_pdf_async",
            invalid_renderer,
            raising=True,
        )
        failed = client.get(
            f"/api/student/reports/{debate.id}/export/pdf",
            headers={**headers, "X-Request-Id": "req-e2e-invalid-pdf"},
        )
        assert failed.status_code == 503
        assert failed.json()["code"] == "REPORT_PDF_RENDER_FAILED"
        assert failed.json()["retryable"] is True

        e2e_db.expire_all()
        assert e2e_db.get(Debate, debate.id).report["report_pdf_status"] == "failed"

        monkeypatch.setattr(
            ReportGenerator,
            "render_markdown_to_pdf_async",
            counted_renderer,
            raising=True,
        )
        responses = [
            client.get(
                f"/api/student/reports/{debate.id}/export/pdf",
                headers=headers,
            )
            for _ in range(3)
        ]
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert calls == 1
    assert not list(private_root.rglob("*.tmp"))

    e2e_db.expire_all()
    stored = e2e_db.get(Debate, debate.id)
    assert stored.report["report_pdf_status"] == "ready"
    assert stored.report["report_pdf_storage"]["storage_key"]
    assert stored.report_pdf is None


def test_fallback_is_visible_but_excluded_from_analytics_gate(e2e_db):
    _fallback_isolation_proof(e2e_db)
