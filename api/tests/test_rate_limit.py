import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, File, UploadFile
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from middleware import rate_limit
from middleware.rate_limit import RateLimitMiddleware, reset_rate_limit_state
from services.audit_service import AuditService
from utils.security import create_access_token


@pytest.fixture
def rate_limit_client(monkeypatch):
    reset_rate_limit_state()
    AuditService.clear_events()
    monkeypatch.setattr(rate_limit, "_get_redis_client", lambda: None)
    monkeypatch.setattr(rate_limit.time, "time", lambda: 1_700_000_000.0)
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/api/auth/login")
    async def login():
        return {"ok": True}

    @app.post("/api/admin/kb/documents")
    async def upload_document(file: UploadFile = File(...)):
        content = await file.read()
        return {"size": len(content)}

    @app.get("/api/student/reports/{debate_id}")
    async def get_report(debate_id: str):
        return {"debate_id": debate_id, "ok": True}

    @app.get("/api/student/reports/{debate_id}/export/pdf")
    async def export_report_pdf(debate_id: str):
        return {"debate_id": debate_id, "ok": True}

    @app.post("/api/student/reports/{debate_id}/send-email")
    async def send_report_email(debate_id: str):
        return {"debate_id": debate_id, "ok": True}

    @app.post("/api/teacher/topics/generate")
    async def generate_topics():
        return {"topics": ["topic-a"]}

    @app.post("/api/teacher/classes/{class_id}/topic-recommendations")
    async def generate_class_topic_recommendations(class_id: str):
        return {"class_id": class_id, "topics": ["topic-a"]}

    @app.post("/api/teacher/debates/{debate_id}/report/recalculate")
    async def recalculate_teacher_report(debate_id: str):
        return {"debate_id": debate_id, "ok": True}

    with TestClient(app) as client:
        yield client

    reset_rate_limit_state()
    AuditService.clear_events()


def test_login_rate_limit_blocks_after_threshold(rate_limit_client):
    for _ in range(10):
        response = rate_limit_client.post("/api/auth/login")
        assert response.status_code == 200

    blocked = rate_limit_client.post("/api/auth/login")

    assert blocked.status_code == 429
    assert blocked.json()["data"]["bucket"] == "login"
    assert int(blocked.headers["Retry-After"]) >= 1


def test_upload_rate_limit_uses_user_identity_when_token_is_present(rate_limit_client):
    user_one_headers = {
        "Authorization": f"Bearer {create_access_token({'user_id': 'user-one', 'user_type': 'teacher'})}"
    }
    user_two_headers = {
        "Authorization": f"Bearer {create_access_token({'user_id': 'user-two', 'user_type': 'teacher'})}"
    }

    for _ in range(12):
        response = rate_limit_client.post(
            "/api/admin/kb/documents",
            headers=user_one_headers,
            files={"file": ("doc.pdf", b"%PDF-1.4\nx", "application/pdf")},
        )
        assert response.status_code == 200

    blocked = rate_limit_client.post(
        "/api/admin/kb/documents",
        headers=user_one_headers,
        files={"file": ("doc.pdf", b"%PDF-1.4\nx", "application/pdf")},
    )
    allowed_other_user = rate_limit_client.post(
        "/api/admin/kb/documents",
        headers=user_two_headers,
        files={"file": ("doc.pdf", b"%PDF-1.4\nx", "application/pdf")},
    )

    assert blocked.status_code == 429
    assert allowed_other_user.status_code == 200


def test_rate_limit_sets_remaining_headers(rate_limit_client):
    response = rate_limit_client.post("/api/auth/login")

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Remaining"] == "9"


def test_report_pdf_export_generation_is_rate_limited(rate_limit_client):
    for _ in range(6):
        response = rate_limit_client.get("/api/student/reports/debate-1/export/pdf")
        assert response.status_code == 200

    blocked = rate_limit_client.get("/api/student/reports/debate-1/export/pdf")

    assert blocked.status_code == 429
    assert blocked.json()["data"]["bucket"] == "report_regeneration"
    events = AuditService.list_events(event_type="report_regeneration", result="denied")
    assert events[0]["metadata"]["bucket"] == "report_regeneration"


def test_report_fetch_generation_is_rate_limited(rate_limit_client):
    for _ in range(6):
        response = rate_limit_client.get("/api/student/reports/debate-1")
        assert response.status_code == 200

    blocked = rate_limit_client.get("/api/student/reports/debate-1")

    assert blocked.status_code == 429
    assert blocked.json()["data"]["bucket"] == "report_regeneration"


def test_candidate_topic_generation_is_rate_limited(rate_limit_client):
    for _ in range(8):
        response = rate_limit_client.post("/api/teacher/classes/class-1/topic-recommendations")
        assert response.status_code == 200

    blocked = rate_limit_client.post("/api/teacher/classes/class-1/topic-recommendations")

    assert blocked.status_code == 429
    assert blocked.json()["data"]["bucket"] == "candidate_topic_generation"
    events = AuditService.list_events(event_type="topic_generation", result="denied")
    assert events[0]["target_type"] == "candidate_topic"


def test_legacy_candidate_topic_generation_route_remains_rate_limited(rate_limit_client):
    for _ in range(8):
        response = rate_limit_client.post("/api/teacher/topics/generate")
        assert response.status_code == 200

    blocked = rate_limit_client.post("/api/teacher/topics/generate")

    assert blocked.status_code == 429
    assert blocked.json()["data"]["bucket"] == "candidate_topic_generation"


def test_teacher_report_recalculation_route_is_rate_limited(rate_limit_client):
    for _ in range(6):
        response = rate_limit_client.post("/api/teacher/debates/debate-1/report/recalculate")
        assert response.status_code == 200

    blocked = rate_limit_client.post("/api/teacher/debates/debate-1/report/recalculate")

    assert blocked.status_code == 429
    assert blocked.json()["data"]["bucket"] == "report_regeneration"
