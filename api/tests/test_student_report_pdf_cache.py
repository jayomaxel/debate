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
from services.report_service import ReportGenerator
from testing_db import create_test_engine, create_test_schema, drop_test_schema
from utils.security import create_token, hash_password


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


@pytest.fixture(scope="function")
def setup_database():
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
    pdf_path = tmp_path / "existing.pdf"
    pdf_path.write_bytes(pdf_bytes)

    db = TestingSessionLocal()
    debate = db.query(Debate).filter(Debate.id == debate_for_teacher.id).first()
    debate.report_pdf = str(pdf_path)
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
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir), raising=False)

    debate_id = str(debate_for_teacher.id)
    default_path = Path(str(upload_dir).rstrip("/\\")) / "reports" / f"debate_report_{debate_id}.pdf"
    default_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = b"%PDF-1.4\n%cached\n%%EOF"
    default_path.write_bytes(pdf_bytes)

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

    db = TestingSessionLocal()
    debate = db.query(Debate).filter(Debate.id == debate_for_teacher.id).first()
    assert debate.report_pdf is not None and str(debate.report_pdf).strip()
    db.close()
