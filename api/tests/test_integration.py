"""
集成测试 - 测试完整的用户流程
"""
import pytest
import asyncio
from httpx import AsyncClient
from main import app

# 测试基础URL
BASE_URL = "http://test"


@pytest.mark.asyncio
async def test_complete_user_flow():
    """
    测试完整的用户流程：
    1. 教师注册和登录
    2. 创建班级
    3. 添加学生
    4. 创建辩论任务
    5. 学生登录
    6. 学生加入辩论
    """
    async with AsyncClient(app=app, base_url=BASE_URL) as client:
        # 1. 教师注册
        teacher_data = {
            "account": "teacher_test",
            "password": "Test123456",
            "name": "测试教师",
            "email": "teacher@test.com"
        }
        
        response = await client.post("/api/auth/register/teacher", json=teacher_data)
        assert response.status_code == 200
        teacher_id = response.json()["data"]["user_id"]
        
        # 2. 教师登录
        login_data = {
            "account": "teacher_test",
            "password": "Test123456"
        }
        
        response = await client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        teacher_token = response.json()["data"]["access_token"]
        
        headers = {"Authorization": f"Bearer {teacher_token}"}
        
        # 3. 创建班级
        class_data = {
            "name": "测试班级"
        }
        
        response = await client.post(
            "/api/teacher/classes",
            json=class_data,
            headers=headers
        )
        assert response.status_code == 200
        class_id = response.json()["data"]["id"]
        
        # 4. 添加学生
        student_data = {
            "account": "student_test",
            "password": "Test123456",
            "name": "测试学生",
            "class_id": class_id,
            "email": "student@test.com"
        }
        
        response = await client.post(
            "/api/teacher/students",
            json=student_data,
            headers=headers
        )
        assert response.status_code == 200
        student_id = response.json()["data"]["user_id"]
        
        # 5. 创建辩论任务
        debate_data = {
            "class_id": class_id,
            "topic": "人工智能是否会取代人类工作",
            "duration": 30,
            "description": "测试辩论"
        }
        
        response = await client.post(
            "/api/teacher/debates",
            json=debate_data,
            headers=headers
        )
        assert response.status_code == 200
        debate_id = response.json()["data"]["id"]
        
        # 6. 学生登录
        response = await client.post("/api/auth/login", json={
            "account": "student_test",
            "password": "Test123456"
        })
        assert response.status_code == 200
        student_token = response.json()["data"]["access_token"]
        
        student_headers = {"Authorization": f"Bearer {student_token}"}
        
        # 7. 学生查看可参与的辩论
        response = await client.get(
            "/api/student/debates",
            headers=student_headers
        )
        assert response.status_code == 200
        debates = response.json()["data"]
        assert len(debates) > 0


@pytest.mark.asyncio
async def test_authentication_flow():
    """测试认证流程"""
    async with AsyncClient(app=app, base_url=BASE_URL) as client:
        # 注册
        user_data = {
            "account": "auth_test",
            "password": "Test123456",
            "name": "认证测试",
            "email": "auth@test.com"
        }
        
        response = await client.post("/api/auth/register/teacher", json=user_data)
        assert response.status_code == 200
        
        # 登录
        login_data = {
            "account": "auth_test",
            "password": "Test123456"
        }
        
        response = await client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        data = response.json()["data"]
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        
        # 使用access_token访问受保护的资源
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.get("/api/teacher/classes", headers=headers)
        assert response.status_code == 200
        
        # 刷新令牌
        response = await client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert response.status_code == 200
        new_access_token = response.json()["data"]["access_token"]
        assert new_access_token != access_token


@pytest.mark.asyncio
async def test_permission_control():
    """测试权限控制"""
    async with AsyncClient(app=app, base_url=BASE_URL) as client:
        # 创建教师和学生
        teacher_response = await client.post("/api/auth/register/teacher", json={
            "account": "perm_teacher",
            "password": "Test123456",
            "name": "权限测试教师",
            "email": "perm_teacher@test.com"
        })
        teacher_token = (await client.post("/api/auth/login", json={
            "account": "perm_teacher",
            "password": "Test123456"
        })).json()["data"]["access_token"]
        
        # 创建班级
        class_response = await client.post(
            "/api/teacher/classes",
            json={"name": "权限测试班级"},
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        class_id = class_response.json()["data"]["id"]
        
        # 添加学生
        await client.post(
            "/api/teacher/students",
            json={
                "account": "perm_student",
                "password": "Test123456",
                "name": "权限测试学生",
                "class_id": class_id,
                "email": "perm_student@test.com"
            },
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        
        student_token = (await client.post("/api/auth/login", json={
            "account": "perm_student",
            "password": "Test123456"
        })).json()["data"]["access_token"]
        
        # 学生尝试访问教师端点（应该失败）
        response = await client.get(
            "/api/teacher/classes",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 403
        
        # 教师尝试访问学生端点（应该失败）
        response = await client.get(
            "/api/student/profile",
            headers={"Authorization": f"Bearer {teacher_token}"}
        )
        assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
