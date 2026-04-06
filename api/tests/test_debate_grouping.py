import pytest
from httpx import AsyncClient
from main import app
from services.debate_service import DebateService


BASE_URL = "http://test"


@pytest.mark.asyncio
async def test_teacher_create_debate_grouping_fallback(monkeypatch):
    async def fake_openai_assign_roles(db, students):
        raise Exception("openai disabled in test")

    monkeypatch.setattr(DebateService, "_openai_assign_roles", fake_openai_assign_roles)

    async with AsyncClient(app=app, base_url=BASE_URL) as client:
        teacher_data = {
            "account": "teacher_grouping_test",
            "password": "Test123456",
            "name": "分组测试教师",
            "email": "teacher_grouping@test.com",
        }
        response = await client.post("/api/auth/register/teacher", json=teacher_data)
        assert response.status_code == 200

        response = await client.post(
            "/api/auth/login", json={"account": "teacher_grouping_test", "password": "Test123456"}
        )
        assert response.status_code == 200
        teacher_token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {teacher_token}"}

        response = await client.post("/api/teacher/classes", json={"name": "分组测试班级"}, headers=headers)
        assert response.status_code == 200
        class_id = response.json()["data"]["id"]

        student_ids = []
        for i in range(4):
            response = await client.post(
                "/api/teacher/students",
                json={
                    "account": f"group_student_{i}",
                    "password": "Test123456",
                    "name": f"分组学生{i}",
                    "class_id": class_id,
                    "email": f"group_student_{i}@test.com",
                },
                headers=headers,
            )
            assert response.status_code == 200
            student_ids.append(response.json()["data"]["user_id"])

        response = await client.post(
            "/api/teacher/debates",
            json={
                "class_id": class_id,
                "topic": "测试智能分组是否生效",
                "duration": 30,
                "description": "3轮辩论",
                "student_ids": student_ids,
            },
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]

        assert "grouping" in data
        assert len(data["grouping"]) == 4
        roles = [x["role"] for x in data["grouping"]]
        assert len(set(roles)) == 4
        reasons = [x.get("role_reason") for x in data["grouping"]]
        assert all(isinstance(r, str) and len(r) == 8 for r in reasons)

        debate_id = data["id"]
        response = await client.get(f"/api/teacher/debates/{debate_id}", headers=headers)
        assert response.status_code == 200
        detail = response.json()["data"]
        assert len(detail.get("grouping", [])) == 4
