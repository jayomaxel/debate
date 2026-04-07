"""
学生知识库路由单元测试
测试学生知识库问答端点的功能
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch, MagicMock
import uuid

from main import app
from database import Base, get_db
from models.user import User
from testing_db import create_test_engine
from utils.security import hash_password, create_token

# 创建测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_student_kb_router.db"
engine = create_test_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """覆盖数据库依赖"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    """设置测试数据库"""
    # 只创建我们需要的表（不创建chunks和conversations表，因为SQLite不支持ARRAY和JSONB类型）
    User.__table__.create(bind=engine, checkfirst=True)
    yield
    # 清理表
    User.__table__.drop(bind=engine, checkfirst=True)


@pytest.fixture
def student_user(setup_database):
    """创建学生用户"""
    db = TestingSessionLocal()
    student = User(
        id=uuid.uuid4(),
        account="student001",
        name="Test Student",
        password_hash=hash_password("password123"),
        user_type="student",
        email="student@test.com"
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    student_token = create_token({"sub": str(student.id), "user_type": "student"})
    db.close()
    return {"user": student, "token": student_token}


@pytest.fixture
def teacher_user(setup_database):
    """创建教师用户"""
    db = TestingSessionLocal()
    teacher = User(
        id=uuid.uuid4(),
        account="teacher001",
        name="Test Teacher",
        password_hash=hash_password("password123"),
        user_type="teacher",
        email="teacher@test.com"
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    teacher_token = create_token({"sub": str(teacher.id), "user_type": "teacher"})
    db.close()
    return {"user": teacher, "token": teacher_token}


@pytest.fixture
def admin_user(setup_database):
    """创建管理员用户"""
    db = TestingSessionLocal()
    admin = User(
        id=uuid.uuid4(),
        account="admin",
        name="Administrator",
        password_hash=hash_password("Admin123!"),
        user_type="administrator",
        email="admin@system.local"
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    admin_token = create_token({"sub": str(admin.id), "user_type": "administrator"})
    db.close()
    return {"user": admin, "token": admin_token}


class TestAskQuestionEndpoint:
    """测试提问端点"""
    
    def test_ask_question_success_with_kb(self, student_user):
        """测试成功提问（使用知识库）"""
        # Mock RAGService.ask_question方法
        mock_result = {
            "answer": "根据知识库文档，辩论的基本要素包括论点、论据和论证。",
            "sources": [
                {
                    "document_id": str(uuid.uuid4()),
                    "document_name": "辩论基础知识.pdf",
                    "excerpt": "辩论的基本要素包括论点、论据和论证...",
                    "similarity_score": 0.85
                }
            ],
            "used_kb": True,
            "confidence": "high"
        }
        
        with patch('services.rag_service.RAGService.ask_question', new_callable=AsyncMock) as mock_ask:
            mock_ask.return_value = mock_result
            
            response = client.post(
                "/api/student/kb/ask",
                json={
                    "question": "什么是辩论的基本要素？",
                    "session_id": "test-session-123"
                },
                headers={"Authorization": f"Bearer {student_user['token']}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert data["message"] == "回答生成成功"
            assert "data" in data
            
            result_data = data["data"]
            assert result_data["answer"] == mock_result["answer"]
            assert result_data["used_kb"] is True
            assert result_data["confidence"] == "high"
            assert len(result_data["sources"]) == 1
            assert result_data["sources"][0]["document_name"] == "辩论基础知识.pdf"
            
            # 验证调用参数
            mock_ask.assert_called_once()
            call_args = mock_ask.call_args
            assert call_args[1]["question"] == "什么是辩论的基本要素？"
            assert call_args[1]["user_id"] == str(student_user["user"].id)
            assert call_args[1]["session_id"] == "test-session-123"
    
    def test_ask_question_success_without_kb(self, student_user):
        """测试成功提问（不使用知识库，基于一般知识）"""
        # Mock RAGService.ask_question方法
        mock_result = {
            "answer": "辩论是一种通过逻辑推理和证据支持来论证观点的活动。",
            "sources": [],
            "used_kb": False,
            "confidence": "none"
        }
        
        with patch('services.rag_service.RAGService.ask_question', new_callable=AsyncMock) as mock_ask:
            mock_ask.return_value = mock_result
            
            response = client.post(
                "/api/student/kb/ask",
                json={
                    "question": "什么是辩论？",
                    "session_id": "test-session-456"
                },
                headers={"Authorization": f"Bearer {student_user['token']}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            
            result_data = data["data"]
            assert result_data["used_kb"] is False
            assert result_data["confidence"] == "none"
            assert len(result_data["sources"]) == 0
    
    def test_ask_question_empty_question(self, student_user):
        """测试空问题验证"""
        response = client.post(
            "/api/student/kb/ask",
            json={
                "question": "   ",  # 空白字符串
                "session_id": "test-session-789"
            },
            headers={"Authorization": f"Bearer {student_user['token']}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "问题不能为空" in data["detail"]
    
    def test_ask_question_missing_question(self, student_user):
        """测试缺少问题字段"""
        response = client.post(
            "/api/student/kb/ask",
            json={
                "session_id": "test-session-789"
            },
            headers={"Authorization": f"Bearer {student_user['token']}"}
        )
        
        assert response.status_code == 422  # Pydantic validation error
    
    def test_ask_question_missing_session_id(self, student_user):
        """测试缺少session_id字段"""
        response = client.post(
            "/api/student/kb/ask",
            json={
                "question": "什么是辩论？"
            },
            headers={"Authorization": f"Bearer {student_user['token']}"}
        )
        
        assert response.status_code == 422  # Pydantic validation error
    
    def test_ask_question_unauthorized(self):
        """测试未认证访问"""
        response = client.post(
            "/api/student/kb/ask",
            json={
                "question": "什么是辩论？",
                "session_id": "test-session-123"
            }
        )
        
        assert response.status_code == 401
    
    def test_ask_question_wrong_role_teacher(self, teacher_user):
        """测试教师角色访问（应该被拒绝）"""
        response = client.post(
            "/api/student/kb/ask",
            json={
                "question": "什么是辩论？",
                "session_id": "test-session-123"
            },
            headers={"Authorization": f"Bearer {teacher_user['token']}"}
        )
        
        assert response.status_code == 403
    
    def test_ask_question_wrong_role_admin(self, admin_user):
        """测试管理员角色访问（应该被拒绝）"""
        response = client.post(
            "/api/student/kb/ask",
            json={
                "question": "什么是辩论？",
                "session_id": "test-session-123"
            },
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 403
    
    def test_ask_question_rag_service_error(self, student_user):
        """测试RAG服务错误处理"""
        # Mock RAGService.ask_question抛出RuntimeError
        with patch('services.rag_service.RAGService.ask_question', new_callable=AsyncMock) as mock_ask:
            mock_ask.side_effect = RuntimeError("LLM API调用失败")
            
            response = client.post(
                "/api/student/kb/ask",
                json={
                    "question": "什么是辩论？",
                    "session_id": "test-session-123"
                },
                headers={"Authorization": f"Bearer {student_user['token']}"}
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "回答生成失败" in data["detail"]
    
    def test_ask_question_low_confidence(self, student_user):
        """测试低置信度回答"""
        # Mock RAGService.ask_question返回低置信度结果
        mock_result = {
            "answer": "根据知识库，辩论可能涉及多个方面...",
            "sources": [
                {
                    "document_id": str(uuid.uuid4()),
                    "document_name": "辩论概述.pdf",
                    "excerpt": "辩论涉及多个方面...",
                    "similarity_score": 0.72
                }
            ],
            "used_kb": True,
            "confidence": "low"
        }
        
        with patch('services.rag_service.RAGService.ask_question', new_callable=AsyncMock) as mock_ask:
            mock_ask.return_value = mock_result
            
            response = client.post(
                "/api/student/kb/ask",
                json={
                    "question": "辩论有哪些技巧？",
                    "session_id": "test-session-123"
                },
                headers={"Authorization": f"Bearer {student_user['token']}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            result_data = data["data"]
            assert result_data["confidence"] == "low"
            assert result_data["used_kb"] is True


class TestGetConversationHistoryEndpoint:
    """测试获取对话历史端点"""
    
    def test_get_conversation_history_success(self, student_user):
        """测试成功获取对话历史"""
        # Mock RAGService.get_conversation_history方法
        mock_conversations = [
            {
                "id": str(uuid.uuid4()),
                "question": "什么是辩论的基本要素？",
                "answer": "根据知识库文档，辩论的基本要素包括论点、论据和论证。",
                "sources": [
                    {
                        "document_id": str(uuid.uuid4()),
                        "document_name": "辩论基础知识.pdf",
                        "excerpt": "辩论的基本要素包括论点、论据和论证...",
                        "similarity_score": 0.85
                    }
                ],
                "created_at": "2024-01-15T10:30:00"
            },
            {
                "id": str(uuid.uuid4()),
                "question": "如何准备辩论？",
                "answer": "准备辩论需要充分研究主题，收集证据，组织论点。",
                "sources": [],
                "created_at": "2024-01-15T10:25:00"
            }
        ]
        
        with patch('services.rag_service.RAGService.get_conversation_history') as mock_get_history:
            mock_get_history.return_value = mock_conversations
            
            response = client.get(
                "/api/student/kb/conversations/test-session-123",
                headers={"Authorization": f"Bearer {student_user['token']}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert data["message"] == "对话历史获取成功"
            assert "data" in data
            
            result_data = data["data"]
            assert "conversations" in result_data
            assert "count" in result_data
            assert result_data["count"] == 2
            assert len(result_data["conversations"]) == 2
            
            # 验证第一条对话
            first_conv = result_data["conversations"][0]
            assert first_conv["question"] == "什么是辩论的基本要素？"
            assert "辩论的基本要素包括论点、论据和论证" in first_conv["answer"]
            assert len(first_conv["sources"]) == 1
            
            # 验证调用参数
            mock_get_history.assert_called_once()
            call_args = mock_get_history.call_args
            assert call_args[1]["user_id"] == str(student_user["user"].id)
            assert call_args[1]["session_id"] == "test-session-123"
            assert call_args[1]["limit"] == 20  # 默认值
    
    def test_get_conversation_history_with_custom_limit(self, student_user):
        """测试使用自定义limit获取对话历史"""
        mock_conversations = [
            {
                "id": str(uuid.uuid4()),
                "question": "测试问题",
                "answer": "测试答案",
                "sources": [],
                "created_at": "2024-01-15T10:30:00"
            }
        ]
        
        with patch('services.rag_service.RAGService.get_conversation_history') as mock_get_history:
            mock_get_history.return_value = mock_conversations
            
            response = client.get(
                "/api/student/kb/conversations/test-session-456?limit=5",
                headers={"Authorization": f"Bearer {student_user['token']}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            
            # 验证调用参数中的limit
            mock_get_history.assert_called_once()
            call_args = mock_get_history.call_args
            assert call_args[1]["limit"] == 5
    
    def test_get_conversation_history_empty(self, student_user):
        """测试获取空对话历史"""
        with patch('services.rag_service.RAGService.get_conversation_history') as mock_get_history:
            mock_get_history.return_value = []
            
            response = client.get(
                "/api/student/kb/conversations/new-session",
                headers={"Authorization": f"Bearer {student_user['token']}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            
            result_data = data["data"]
            assert result_data["count"] == 0
            assert len(result_data["conversations"]) == 0
    
    def test_get_conversation_history_invalid_limit(self, student_user):
        """测试无效的limit参数"""
        response = client.get(
            "/api/student/kb/conversations/test-session-123?limit=0",
            headers={"Authorization": f"Bearer {student_user['token']}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "limit参数必须大于0" in data["detail"]
    
    def test_get_conversation_history_negative_limit(self, student_user):
        """测试负数limit参数"""
        response = client.get(
            "/api/student/kb/conversations/test-session-123?limit=-5",
            headers={"Authorization": f"Bearer {student_user['token']}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "limit参数必须大于0" in data["detail"]
    
    def test_get_conversation_history_unauthorized(self):
        """测试未认证访问"""
        response = client.get(
            "/api/student/kb/conversations/test-session-123"
        )
        
        assert response.status_code == 401
    
    def test_get_conversation_history_wrong_role_teacher(self, teacher_user):
        """测试教师角色访问（应该被拒绝）"""
        response = client.get(
            "/api/student/kb/conversations/test-session-123",
            headers={"Authorization": f"Bearer {teacher_user['token']}"}
        )
        
        assert response.status_code == 403
    
    def test_get_conversation_history_wrong_role_admin(self, admin_user):
        """测试管理员角色访问（应该被拒绝）"""
        response = client.get(
            "/api/student/kb/conversations/test-session-123",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 403
    
    def test_get_conversation_history_service_error(self, student_user):
        """测试RAG服务错误处理"""
        with patch('services.rag_service.RAGService.get_conversation_history') as mock_get_history:
            mock_get_history.side_effect = RuntimeError("数据库查询失败")
            
            response = client.get(
                "/api/student/kb/conversations/test-session-123",
                headers={"Authorization": f"Bearer {student_user['token']}"}
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "获取对话历史失败" in data["detail"]
    
    def test_get_conversation_history_value_error(self, student_user):
        """测试RAG服务验证错误处理"""
        with patch('services.rag_service.RAGService.get_conversation_history') as mock_get_history:
            mock_get_history.side_effect = ValueError("会话ID不能为空")
            
            response = client.get(
                "/api/student/kb/conversations/test-session-123",
                headers={"Authorization": f"Bearer {student_user['token']}"}
            )
            
            assert response.status_code == 400
            data = response.json()
            assert "会话ID不能为空" in data["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
