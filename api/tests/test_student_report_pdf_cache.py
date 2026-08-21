import uuid
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from config import settings
from database import Base, get_db
from main import app
from models.class_model import Class
from models.debate import Debate
from models.score import Score
from models.speech import Speech
from models.user import User
from routers import student as student_router
from schemas.operations import ExportStatus, ReportOperationStateContract, ReportStatus, ScoringStatus
from services.audit_service import AuditService
from services.background_job_runtime import DEBATE_REPORT_JOB_TYPE
from services.background_job_service import BackgroundJobService
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


def _cache_markdown(debate_id: uuid.UUID, markdown_text: str = "# Report\n\nCached markdown"):
    db = TestingSessionLocal()
    try:
        debate = db.query(Debate).filter(Debate.id == debate_id).one()
        debate.report = {
            "report_markdown": markdown_text,
            "report_markdown_hash": student_router._compute_markdown_hash(markdown_text, 0),
        }
        debate.report_pdf = None
        db.commit()
    finally:
        db.close()


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
    from services.file_access_service import FileAccessService

    monkeypatch.setattr(
        FileAccessService,
        "_report_roots",
        staticmethod(lambda: (tmp_path.resolve(),)),
    )

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

    _cache_markdown(debate_for_teacher.id)

    async def fake_render_markdown_to_pdf_async(*args, **kwargs):
        return b"%PDF-1.4\n%generated\n%%EOF"

    monkeypatch.setattr(
        ReportGenerator,
        "render_markdown_to_pdf_async",
        fake_render_markdown_to_pdf_async,
        raising=True,
    )

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


def test_student_report_read_queues_missing_scores_without_inline_scoring(
    teacher_token,
    debate_for_teacher,
):
    db = TestingSessionLocal()
    try:
        db.add(
            Speech(
                id=uuid.uuid4(),
                debate_id=debate_for_teacher.id,
                speaker_id=None,
                speaker_type="ai",
                speaker_role="ai_1",
                phase="opening",
                side="negative",
                content="A valid unscored speech.",
                duration=20,
                is_valid_for_scoring=True,
                timestamp=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        f"/api/student/reports/{debate_for_teacher.id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )

    assert response.status_code == 202
    assert response.json()["data"]["report_status"] == "processing"
    db = TestingSessionLocal()
    try:
        assert db.query(Score).count() == 0
        job = BackgroundJobService.get_latest_for_target(
            db,
            job_type=DEBATE_REPORT_JOB_TYPE,
            target_type="debate",
            target_id=str(debate_for_teacher.id),
        )
        assert job is not None and job.status == "queued"
    finally:
        db.close()


@pytest.mark.parametrize("rendered", [b"", b"not-a-pdf"])
def test_pdf_invalid_renderer_output_uses_stable_error_contract(
    tmp_path,
    teacher_token,
    debate_for_teacher,
    monkeypatch,
    rendered,
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"), raising=False)
    _cache_markdown(debate_for_teacher.id)

    async def invalid_renderer(*args, **kwargs):
        return rendered

    monkeypatch.setattr(
        ReportGenerator,
        "render_markdown_to_pdf_async",
        invalid_renderer,
        raising=True,
    )
    response = client.get(
        f"/api/student/reports/{debate_for_teacher.id}/export/pdf",
        headers={
            "Authorization": f"Bearer {teacher_token}",
            "X-Request-Id": "req-invalid-pdf",
        },
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "REPORT_PDF_RENDER_FAILED"
    assert body["request_id"] == "req-invalid-pdf"
    assert body["retryable"] is True
    db = TestingSessionLocal()
    try:
        debate = db.query(Debate).filter(Debate.id == debate_for_teacher.id).one()
        assert debate.report["report_pdf_status"] == "failed"
    finally:
        db.close()


def test_markdown_empty_response_uses_distinct_error_contract(
    tmp_path,
    teacher_token,
    debate_for_teacher,
    monkeypatch,
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"), raising=False)
    db = TestingSessionLocal()
    try:
        db.add(
            Speech(
                id=uuid.uuid4(),
                debate_id=debate_for_teacher.id,
                speaker_id=None,
                speaker_type="ai",
                speaker_role="ai_1",
                phase="opening",
                content="Speech content for markdown generation.",
                duration=20,
                is_valid_for_scoring=True,
                timestamp=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    ready_state = ReportOperationStateContract(
        debate_id=str(debate_for_teacher.id),
        scoring_status=ScoringStatus.READY,
        report_status=ReportStatus.READY,
        export_status=ExportStatus.NOT_GENERATED,
    )
    monkeypatch.setattr(
        student_router.ReportStateService,
        "enqueue_if_pending",
        lambda *args, **kwargs: ready_state,
        raising=True,
    )

    async def empty_markdown(*args, **kwargs):
        return None

    monkeypatch.setattr(
        ReportGenerator,
        "generate_markdown_report_async",
        empty_markdown,
        raising=True,
    )
    response = client.get(
        f"/api/student/reports/{debate_for_teacher.id}/export/pdf",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "REPORT_MARKDOWN_GENERATION_FAILED"
    db = TestingSessionLocal()
    try:
        debate = db.query(Debate).filter(Debate.id == debate_for_teacher.id).one()
        assert debate.report["report_markdown_status"] == "failed"
        assert debate.report["report_markdown_error"] == "empty_result"
    finally:
        db.close()


def test_pdf_renderer_exception_does_not_break_report_read(
    tmp_path,
    teacher_token,
    debate_for_teacher,
    monkeypatch,
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"), raising=False)
    _cache_markdown(debate_for_teacher.id)

    async def broken_renderer(*args, **kwargs):
        raise RuntimeError("sensitive renderer internals")

    monkeypatch.setattr(
        ReportGenerator,
        "render_markdown_to_pdf_async",
        broken_renderer,
        raising=True,
    )
    failed_export = client.get(
        f"/api/student/reports/{debate_for_teacher.id}/export/pdf",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert failed_export.status_code == 503
    assert failed_export.json()["code"] == "REPORT_PDF_RENDER_FAILED"
    assert "sensitive renderer" not in failed_export.text

    monkeypatch.setattr(
        ReportGenerator,
        "generate_student_report",
        lambda *a, **k: FakeReport(),
        raising=True,
    )
    report_response = client.get(
        f"/api/student/reports/{debate_for_teacher.id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert report_response.status_code == 200
    assert report_response.json()["data"]["operation_state"]["export_status"] == "failed"


def test_pdf_storage_failure_uses_stable_error_contract(
    tmp_path,
    teacher_token,
    debate_for_teacher,
    monkeypatch,
):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"), raising=False)
    _cache_markdown(debate_for_teacher.id)

    async def valid_renderer(*args, **kwargs):
        return b"%PDF-1.4\n%%EOF"

    def failed_write(*args, **kwargs):
        raise OSError("sensitive disk path")

    monkeypatch.setattr(
        ReportGenerator,
        "render_markdown_to_pdf_async",
        valid_renderer,
        raising=True,
    )
    monkeypatch.setattr(
        ReportFileStorageService,
        "persist_pdf_bytes_for_debate",
        failed_write,
        raising=True,
    )
    response = client.get(
        f"/api/student/reports/{debate_for_teacher.id}/export/pdf",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )

    assert response.status_code == 507
    assert response.json()["code"] == "REPORT_STORAGE_WRITE_FAILED"
    assert "sensitive disk path" not in response.text


def test_pdf_generation_is_atomic_and_three_reads_render_once(
    tmp_path,
    teacher_token,
    debate_for_teacher,
    monkeypatch,
):
    upload_dir = tmp_path / "uploads"
    private_root = tmp_path / "private-report-storage"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir), raising=False)
    monkeypatch.setattr(settings, "REPORT_FILE_STORAGE_DIR", str(private_root), raising=False)
    _cache_markdown(debate_for_teacher.id)
    calls = 0

    async def counted_renderer(*args, **kwargs):
        nonlocal calls
        calls += 1
        return b"%PDF-1.4\n%atomic\n%%EOF"

    monkeypatch.setattr(
        ReportGenerator,
        "render_markdown_to_pdf_async",
        counted_renderer,
        raising=True,
    )
    responses = [
        client.get(
            f"/api/student/reports/{debate_for_teacher.id}/export/pdf",
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        for _ in range(3)
    ]

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert calls == 1
    assert not list(private_root.rglob("*.tmp"))


def test_deleted_pdf_cache_is_regenerated_and_returns_ready(
    tmp_path,
    teacher_token,
    debate_for_teacher,
    monkeypatch,
):
    private_root = tmp_path / "private-report-storage"
    monkeypatch.setattr(
        settings,
        "REPORT_FILE_STORAGE_DIR",
        str(private_root),
        raising=False,
    )
    _cache_markdown(debate_for_teacher.id)
    calls = 0

    async def counted_renderer(*args, **kwargs):
        nonlocal calls
        calls += 1
        return b"%PDF-1.4\n%regenerated\n%%EOF"

    monkeypatch.setattr(
        ReportGenerator,
        "render_markdown_to_pdf_async",
        counted_renderer,
        raising=True,
    )
    first = client.get(
        f"/api/student/reports/{debate_for_teacher.id}/export/pdf",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert first.status_code == 200

    db = TestingSessionLocal()
    try:
        debate = db.query(Debate).filter(Debate.id == debate_for_teacher.id).one()
        old_meta = dict(
            debate.report[ReportFileStorageService.PDF_STORAGE_META_KEY]
        )
        old_path = ReportFileStorageService.resolve_pdf_storage_path(old_meta)
        old_path.unlink()
    finally:
        db.close()

    second = client.get(
        f"/api/student/reports/{debate_for_teacher.id}/export/pdf",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert second.status_code == 200
    assert calls == 2

    db = TestingSessionLocal()
    try:
        debate = db.query(Debate).filter(Debate.id == debate_for_teacher.id).one()
        new_meta = debate.report[ReportFileStorageService.PDF_STORAGE_META_KEY]
        assert new_meta["storage_key"] != old_meta["storage_key"]
        assert ReportFileStorageService.resolve_pdf_storage_path(new_meta).is_file()
        assert debate.report["report_pdf_status"] == "ready"
    finally:
        db.close()


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
