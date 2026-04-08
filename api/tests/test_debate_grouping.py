import pytest
import uuid
from httpx import ASGITransport, AsyncClient
from main import app
from database import SessionLocal, init_db, init_engine
from models.debate import Debate
from services.debate_service import DebateService


BASE_URL = "http://test"


@pytest.mark.asyncio
async def test_teacher_create_debate_grouping_fallback(monkeypatch):
    async def fake_openai_assign_roles(db, students):
        raise Exception("openai disabled in test")

    monkeypatch.setattr(DebateService, "_openai_assign_roles", fake_openai_assign_roles)
    suffix = uuid.uuid4().hex[:8]
    teacher_account = f"teacher_grouping_{suffix}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        teacher_data = {
            "account": teacher_account,
            "password": "Test123456",
            "name": "分组测试教师",
            "email": f"{teacher_account}@test.com",
            "phone": "13800000001",
        }
        response = await client.post("/api/auth/register/teacher", json=teacher_data)
        assert response.status_code == 200

        response = await client.post(
            "/api/auth/login",
            json={
                "account": teacher_account,
                "password": "Test123456",
                "user_type": "teacher",
            },
        )
        assert response.status_code == 200
        teacher_token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {teacher_token}"}

        response = await client.post(
            "/api/teacher/classes",
            json={"name": f"分组测试班级{suffix}"},
            headers=headers,
        )
        assert response.status_code == 200
        class_id = response.json()["data"]["id"]

        student_ids = []
        for i in range(4):
            student_account = f"group_student_{suffix}_{i}"
            response = await client.post(
                "/api/teacher/students",
                json={
                    "account": student_account,
                    "password": "Test123456",
                    "name": f"分组学生{i}",
                    "class_id": class_id,
                    "email": f"{student_account}@test.com",
                },
                headers=headers,
            )
            assert response.status_code == 200
            student_ids.append(response.json()["data"]["id"])

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
        assert all(
            item.get("role_reason") == DebateService.ROLE_REASON[item["role"]]
            for item in data["grouping"]
        )

        debate_id = data["id"]
        response = await client.get(f"/api/teacher/debates/{debate_id}", headers=headers)
        assert response.status_code == 200
        detail = response.json()["data"]
        assert len(detail.get("grouping", [])) == 4


@pytest.mark.asyncio
async def test_teacher_create_debate_rejects_cross_class_students(monkeypatch):
    async def fake_openai_assign_roles(db, students):
        raise Exception("openai disabled in test")

    monkeypatch.setattr(DebateService, "_openai_assign_roles", fake_openai_assign_roles)
    suffix = uuid.uuid4().hex[:8]
    teacher_account = f"teacher_cross_{suffix}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        await client.post(
            "/api/auth/register/teacher",
            json={
                "account": teacher_account,
                "password": "Test123456",
                "name": "跨班校验教师",
                "email": f"{teacher_account}@test.com",
                "phone": "13800000002",
            },
        )
        response = await client.post(
            "/api/auth/login",
            json={
                "account": teacher_account,
                "password": "Test123456",
                "user_type": "teacher",
            },
        )
        teacher_token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {teacher_token}"}

        response = await client.post("/api/teacher/classes", json={"name": f"跨班A{suffix}"}, headers=headers)
        class_a_id = response.json()["data"]["id"]
        response = await client.post("/api/teacher/classes", json={"name": f"跨班B{suffix}"}, headers=headers)
        class_b_id = response.json()["data"]["id"]

        response = await client.post(
            "/api/teacher/students",
            json={
                "account": f"cross_student_{suffix}",
                "password": "Test123456",
                "name": "跨班学生",
                "class_id": class_a_id,
                "email": f"cross_student_{suffix}@test.com",
            },
            headers=headers,
        )
        student_id = response.json()["data"]["id"]

        response = await client.post(
            "/api/teacher/debates",
            json={
                "class_id": class_b_id,
                "topic": "跨班学生校验",
                "duration": 30,
                "description": "测试跨班选择是否被拦截",
                "student_ids": [student_id],
            },
            headers=headers,
        )

        assert response.status_code == 400
        assert "当前班级" in response.json()["detail"]


@pytest.mark.asyncio
async def test_teacher_update_debate_can_switch_class_with_matching_students(monkeypatch):
    async def fake_openai_assign_roles(db, students):
        raise Exception("openai disabled in test")

    monkeypatch.setattr(DebateService, "_openai_assign_roles", fake_openai_assign_roles)
    suffix = uuid.uuid4().hex[:8]
    teacher_account = f"teacher_switch_{suffix}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        await client.post(
            "/api/auth/register/teacher",
            json={
                "account": teacher_account,
                "password": "Test123456",
                "name": "切班教师",
                "email": f"{teacher_account}@test.com",
                "phone": "13800000003",
            },
        )
        response = await client.post(
            "/api/auth/login",
            json={
                "account": teacher_account,
                "password": "Test123456",
                "user_type": "teacher",
            },
        )
        teacher_token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {teacher_token}"}

        response = await client.post("/api/teacher/classes", json={"name": f"切班A{suffix}"}, headers=headers)
        class_a_id = response.json()["data"]["id"]
        response = await client.post("/api/teacher/classes", json={"name": f"切班B{suffix}"}, headers=headers)
        class_b_id = response.json()["data"]["id"]

        response = await client.post(
            "/api/teacher/students",
            json={
                "account": f"switch_student_a_{suffix}",
                "password": "Test123456",
                "name": "A班学生",
                "class_id": class_a_id,
                "email": f"switch_student_a_{suffix}@test.com",
            },
            headers=headers,
        )
        student_a_id = response.json()["data"]["id"]

        response = await client.post(
            "/api/teacher/students",
            json={
                "account": f"switch_student_b_{suffix}",
                "password": "Test123456",
                "name": "B班学生",
                "class_id": class_b_id,
                "email": f"switch_student_b_{suffix}@test.com",
            },
            headers=headers,
        )
        student_b_id = response.json()["data"]["id"]

        response = await client.post(
            "/api/teacher/debates",
            json={
                "class_id": class_a_id,
                "topic": "切换班级前",
                "duration": 30,
                "description": "初始辩论",
                "student_ids": [student_a_id],
            },
            headers=headers,
        )
        assert response.status_code == 200
        debate_id = response.json()["data"]["id"]

        response = await client.put(
            f"/api/teacher/debates/{debate_id}",
            json={
                "class_id": class_b_id,
                "topic": "切换班级后",
                "duration": 30,
                "description": "更新到B班",
                "student_ids": [student_b_id],
            },
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["class_id"] == class_b_id
        assert data["student_ids"] == [student_b_id]


@pytest.mark.asyncio
async def test_teacher_can_save_debate_as_draft_without_students():
    suffix = uuid.uuid4().hex[:8]
    teacher_account = f"teacher_draft_{suffix}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.post(
            "/api/auth/register/teacher",
            json={
                "account": teacher_account,
                "password": "Test123456",
                "name": "草稿测试教师",
                "email": f"{teacher_account}@test.com",
                "phone": "13800000004",
            },
        )
        assert response.status_code == 200

        response = await client.post(
            "/api/auth/login",
            json={
                "account": teacher_account,
                "password": "Test123456",
                "user_type": "teacher",
            },
        )
        assert response.status_code == 200
        teacher_token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {teacher_token}"}

        response = await client.post(
            "/api/teacher/classes",
            json={"name": f"草稿班级{suffix}"},
            headers=headers,
        )
        assert response.status_code == 200
        class_id = response.json()["data"]["id"]

        response = await client.post(
            "/api/teacher/debates",
            json={
                "class_id": class_id,
                "topic": "允许先保存草稿再继续配置吗",
                "duration": 30,
                "description": "草稿保存测试",
                "status": "draft",
            },
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "draft"
        assert data["student_ids"] == []


@pytest.mark.asyncio
async def test_teacher_dashboard_counts_actual_participants_and_statuses(monkeypatch):
    async def fake_openai_assign_roles(db, students):
        raise Exception("openai disabled in test")

    monkeypatch.setattr(DebateService, "_openai_assign_roles", fake_openai_assign_roles)
    suffix = uuid.uuid4().hex[:8]
    teacher_account = f"teacher_dashboard_{suffix}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        response = await client.post(
            "/api/auth/register/teacher",
            json={
                "account": teacher_account,
                "password": "Test123456",
                "name": "看板测试教师",
                "email": f"{teacher_account}@test.com",
                "phone": "13800000005",
            },
        )
        assert response.status_code == 200

        response = await client.post(
            "/api/auth/login",
            json={
                "account": teacher_account,
                "password": "Test123456",
                "user_type": "teacher",
            },
        )
        assert response.status_code == 200
        teacher_token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {teacher_token}"}

        response = await client.post(
            "/api/teacher/classes",
            json={"name": f"看板班级{suffix}"},
            headers=headers,
        )
        assert response.status_code == 200
        class_id = response.json()["data"]["id"]

        student_ids = []
        for i in range(3):
            student_account = f"dashboard_student_{suffix}_{i}"
            response = await client.post(
                "/api/teacher/students",
                json={
                    "account": student_account,
                    "password": "Test123456",
                    "name": f"看板学生{i}",
                    "class_id": class_id,
                    "email": f"{student_account}@test.com",
                },
                headers=headers,
            )
            assert response.status_code == 200
            student_ids.append(response.json()["data"]["id"])

        response = await client.post(
            "/api/teacher/debates",
            json={
                "class_id": class_id,
                "topic": "第一场看板测试",
                "duration": 30,
                "description": "第一场",
                "student_ids": student_ids[:2],
                "status": "published",
            },
            headers=headers,
        )
        assert response.status_code == 200
        debate_a_id = response.json()["data"]["id"]

        response = await client.post(
            "/api/teacher/debates",
            json={
                "class_id": class_id,
                "topic": "第二场看板测试",
                "duration": 30,
                "description": "第二场",
                "student_ids": student_ids[1:],
                "status": "published",
            },
            headers=headers,
        )
        assert response.status_code == 200
        debate_b_id = response.json()["data"]["id"]

        init_engine()
        init_db()
        db = SessionLocal()
        try:
            debate_a = db.query(Debate).filter(Debate.id == uuid.UUID(debate_a_id)).one()
            debate_b = db.query(Debate).filter(Debate.id == uuid.UUID(debate_b_id)).one()
            debate_a.status = "in_progress"
            debate_b.status = "completed"
            db.commit()
        finally:
            db.close()

        response = await client.get("/api/teacher/dashboard", headers=headers)
        assert response.status_code == 200
        stats = response.json()["data"]
        assert stats["managed_students"] == 3
        assert stats["participating_students"] == 3
        assert stats["active_debates"] == 1
        assert stats["completed_debates"] == 1
        assert stats["total_debates"] >= 2
