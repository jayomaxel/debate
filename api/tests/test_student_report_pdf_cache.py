import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from config import settings
from database import Base, get_db
from main import app
from models.class_model import Class
from models.debate import Debate
from models.user import User
from routers import student as student_router
from services.audit_service import AuditService
from services.report_file_storage_service import ReportFileStorageService
from services.report_service import ReportGenerator
from testing_db import create_test_engine, create_test_schema, drop_test_schema
from utils.security import create_token, hash_password
from utils.markdown_to_pdf import MarkdownToPdfConverter


SQLALCHEMY_DATABASE_URL = "sqlite:///./test_student_report_pdf_cache.db"
engine = create_test_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def override_app_database():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


class FakeReport:
    def to_dict(self):
        return {"debate_id": "fake-report", "overall_score": 88}


@pytest.fixture(scope="function")
def setup_database():
    drop_test_schema(engine)
    create_test_schema(engine)
    yield
    drop_test_schema(engine)


@pytest.fixture
def teacher_user(setup_database):
    db = TestingSessionLocal()
    teacher = User(
        id=uuid.uuid4(),
        account="teacher_pdf",
        name="Test Teacher",
        password_hash=hash_password("password123"),
        user_type="teacher",
        email="teacher_pdf@test.com",
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    db.close()
    return teacher


@pytest.fixture
def teacher_token(teacher_user):
    return create_token({"sub": str(teacher_user.id), "user_type": "teacher"})


@pytest.fixture
def debate_for_teacher(setup_database, teacher_user):
    db = TestingSessionLocal()
    cls = Class(
        id=uuid.uuid4(),
        name="Test Class",
        code="CLASS001",
        teacher_id=teacher_user.id,
    )
    db.add(cls)
    db.commit()

    debate = Debate(
        id=uuid.uuid4(),
        topic="测试辩题",
        description="",
        duration=3,
        invitation_code="A1B2C3",
        class_id=cls.id,
        teacher_id=teacher_user.id,
        status="completed",
        report_pdf=None,
    )
    db.add(debate)
    db.commit()
    db.refresh(debate)
    db.close()
    return debate


def test_export_pdf_returns_existing_report_pdf(tmp_path, teacher_token, debate_for_teacher, monkeypatch):
    pdf_bytes = b"%PDF-1.4\n%test\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    storage_root = tmp_path / "private-report-storage"
    monkeypatch.setattr(
        settings,
        "REPORT_FILE_STORAGE_DIR",
        str(storage_root),
        raising=False,
    )
    storage_meta = ReportFileStorageService.create_pdf_storage_meta()
    pdf_path = ReportFileStorageService.resolve_pdf_storage_path(storage_meta)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(pdf_bytes)

    db = TestingSessionLocal()
    debate = db.query(Debate).filter(Debate.id == debate_for_teacher.id).first()
    debate.report = {
        ReportFileStorageService.PDF_STORAGE_META_KEY: storage_meta,
        "report_pdf_renderer_version": MarkdownToPdfConverter.RENDERER_VERSION,
    }
    debate.report_pdf = None
    db.commit()
    db.close()

    async def should_not_call(*args, **kwargs):
        raise AssertionError("should not generate when cached pdf exists")

    monkeypatch.setattr(ReportGenerator, "export_to_pdf_async", should_not_call, raising=True)
    monkeypatch.setattr(ReportGenerator, "generate_student_report", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not generate report")), raising=True)

    resp = client.get(
        f"/api/student/reports/{debate_for_teacher.id}/export/pdf",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 200
    assert resp.content == pdf_bytes


def test_export_pdf_uses_default_path_and_writes_report_pdf(tmp_path, teacher_token, debate_for_teacher, monkeypatch):
    upload_dir = tmp_path / "uploads"
    private_root = tmp_path / "private-report-storage"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir), raising=False)
    monkeypatch.setattr(settings, "REPORT_FILE_STORAGE_DIR", str(private_root), raising=False)

    debate_id = str(debate_for_teacher.id)
    default_path = Path(str(upload_dir).rstrip("/\\")) / "reports" / f"debate_report_{debate_id}.pdf"
    default_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = b"%PDF-1.4\n%cached\n%%EOF"
    default_path.write_bytes(pdf_bytes)

    db = TestingSessionLocal()
    debate = db.query(Debate).filter(Debate.id == debate_for_teacher.id).first()
    debate.report = {
        "report_pdf_renderer_version": MarkdownToPdfConverter.RENDERER_VERSION,
    }
    db.commit()
    db.close()

    async def should_not_call(*args, **kwargs):
        raise AssertionError("should not generate when default pdf exists")

    monkeypatch.setattr(ReportGenerator, "export_to_pdf_async", should_not_call, raising=True)
    monkeypatch.setattr(ReportGenerator, "generate_student_report", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not generate report")), raising=True)

    resp = client.get(
        f"/api/student/reports/{debate_for_teacher.id}/export/pdf",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 200
    assert resp.content == pdf_bytes
    assert "debate_report_" not in resp.headers["content-disposition"]

    db = TestingSessionLocal()
    debate = db.query(Debate).filter(Debate.id == debate_for_teacher.id).first()
    storage_meta = debate.report.get(ReportFileStorageService.PDF_STORAGE_META_KEY)
    assert isinstance(storage_meta, dict)
    assert storage_meta["backend"] == "local"
    assert debate_id not in storage_meta["storage_key"]
    assert debate.report_pdf is None
    migrated_path = ReportFileStorageService.resolve_pdf_storage_path(storage_meta)
    assert migrated_path.exists()
    assert not default_path.exists()
    db.close()


def test_export_pdf_generation_records_audit_event(tmp_path, teacher_token, debate_for_teacher, monkeypatch):
    AuditService.clear_events()
    upload_dir = tmp_path / "uploads"
    private_root = tmp_path / "private-report-storage"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir), raising=False)
    monkeypatch.setattr(settings, "REPORT_FILE_STORAGE_DIR", str(private_root), raising=False)

    markdown_text = "# Report\n\nCached markdown"
    db = TestingSessionLocal()
    debate = db.query(Debate).filter(Debate.id == debate_for_teacher.id).first()
    debate.report = {
        "report_markdown": markdown_text,
        "report_markdown_hash": student_router._compute_markdown_hash(markdown_text, 0),
    }
    debate.report_pdf = None
    db.commit()
    db.close()

    async def fake_ensure_report_ready(*args, **kwargs):
        return {"ready": True}

    async def fake_render_markdown_to_pdf_async(*args, **kwargs):
        return b"%PDF-1.4\n%generated\n%%EOF"

    monkeypatch.setattr(student_router, "_ensure_report_ready", fake_ensure_report_ready, raising=True)
    monkeypatch.setattr(ReportGenerator, "render_markdown_to_pdf_async", fake_render_markdown_to_pdf_async, raising=True)

    resp = client.get(
        f"/api/student/reports/{debate_for_teacher.id}/export/pdf",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )

    assert resp.status_code == 200
    assert "debate_report_" not in resp.headers["content-disposition"]
    events = AuditService.list_events(limit=10, event_type="report_regeneration")
    assert events
    event = events[0]
    assert event["target_id"] == str(debate_for_teacher.id)
    assert event["result"] == "success"
    assert event["metadata"]["action"] == "export_report_pdf"
    assert event["metadata"]["generated_pdf"] is True
    assert event["metadata"]["generated_markdown"] is False
    assert str(debate_for_teacher.id) not in str(event["metadata"]["pdf_storage_key"])
    AuditService.clear_events()


def test_get_student_report_records_audit_event(teacher_token, debate_for_teacher, monkeypatch):
    AuditService.clear_events()

    async def fake_ensure_report_ready(*args, **kwargs):
        return {"ready": True}

    monkeypatch.setattr(student_router, "_ensure_report_ready", fake_ensure_report_ready, raising=True)
    monkeypatch.setattr(ReportGenerator, "generate_student_report", lambda *a, **k: FakeReport(), raising=True)

    resp = client.get(
        f"/api/student/reports/{debate_for_teacher.id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )

    assert resp.status_code == 200
    events = AuditService.list_events(limit=10, event_type="report_regeneration")
    assert events
    event = events[0]
    assert event["target_id"] == str(debate_for_teacher.id)
    assert event["metadata"]["action"] == "get_student_report"
    assert event["metadata"]["generated_report"] is True
    AuditService.clear_events()


def test_export_report_excel_records_audit_event(teacher_token, debate_for_teacher, monkeypatch):
    AuditService.clear_events()

    async def fake_ensure_report_ready(*args, **kwargs):
        return {"ready": True}

    monkeypatch.setattr(student_router, "_ensure_report_ready", fake_ensure_report_ready, raising=True)
    monkeypatch.setattr(ReportGenerator, "generate_student_report", lambda *a, **k: FakeReport(), raising=True)
    monkeypatch.setattr(ReportGenerator, "export_to_excel", lambda *a, **k: b"excel-bytes", raising=True)

    resp = client.get(
        f"/api/student/reports/{debate_for_teacher.id}/export/excel",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )

    assert resp.status_code == 200
    events = AuditService.list_events(limit=10, event_type="report_regeneration")
    assert events
    event = events[0]
    assert event["target_id"] == str(debate_for_teacher.id)
    assert event["metadata"]["action"] == "export_report_excel"
    assert event["metadata"]["generated_report"] is True
    assert event["metadata"]["export_format"] == "excel"
    AuditService.clear_events()
