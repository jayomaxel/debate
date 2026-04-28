"""
管理员知识库路由单元测试
测试管理员知识库文档上传端点的功能
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
import uuid
import io

from main import app
from database import Base, get_db
from models.user import User
from models.kb_document import KBDocument
from testing_db import create_test_engine
from utils.security import hash_password, create_token

# 创建测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin_kb_router.db"
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
    KBDocument.__table__.create(bind=engine, checkfirst=True)
    yield
    # 清理表
    KBDocument.__table__.drop(bind=engine, checkfirst=True)
    User.__table__.drop(bind=engine, checkfirst=True)


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


class TestDocumentUpload:
    """测试文档上传端点"""
    
    def test_upload_pdf_as_admin(self, admin_user):
        """测试管理员上传PDF文档"""
        # 创建模拟PDF文件
        file_content = b"PDF content here" * 100
        files = {
            "file": ("test_document.pdf", io.BytesIO(file_content), "application/pdf")
        }
        
        response = client.post(
            "/api/admin/kb/documents",
            files=files,
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["message"] == "文档上传成功，正在后台处理"
        assert "data" in data
        assert data["data"]["filename"] == "test_document.pdf"
        assert data["data"]["file_type"] == "application/pdf"
        assert data["data"]["upload_status"] == "pending"
    
    def test_upload_docx_as_admin(self, admin_user):
        """测试管理员上传DOCX文档"""
        # 创建模拟DOCX文件
        file_content = b"DOCX content here" * 100
        files = {
            "file": ("test_document.docx", io.BytesIO(file_content), 
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        }
        
        response = client.post(
            "/api/admin/kb/documents",
            files=files,
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["filename"] == "test_document.docx"
    
    def test_upload_invalid_file_type(self, admin_user):
        """测试上传不支持的文件类型"""
        # 创建模拟TXT文件
        file_content = b"Text content here"
        files = {
            "file": ("test_document.txt", io.BytesIO(file_content), "text/plain")
        }
        
        response = client.post(
            "/api/admin/kb/documents",
            files=files,
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 400
        assert "不支持的文件类型" in response.json()["detail"]
    
    def test_upload_file_too_large(self, admin_user):
        """测试上传超过大小限制的文件"""
        # 创建11MB的文件（超过10MB限制）
        file_content = b"x" * (11 * 1024 * 1024)
        files = {
            "file": ("large_document.pdf", io.BytesIO(file_content), "application/pdf")
        }
        
        response = client.post(
            "/api/admin/kb/documents",
            files=files,
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 400
        assert "文件大小超过限制" in response.json()["detail"]
    
    def test_upload_without_authentication(self):
        """测试未认证用户上传文档"""
        file_content = b"PDF content here"
        files = {
            "file": ("test_document.pdf", io.BytesIO(file_content), "application/pdf")
        }
        
        response = client.post(
            "/api/admin/kb/documents",
            files=files
        )
        
        # 未认证应该返回401
        assert response.status_code == 401
    
    def test_upload_as_teacher(self, teacher_user):
        """测试教师用户上传文档（应该被拒绝）"""
        file_content = b"PDF content here"
        files = {
            "file": ("test_document.pdf", io.BytesIO(file_content), "application/pdf")
        }
        
        response = client.post(
            "/api/admin/kb/documents",
            files=files,
            headers={"Authorization": f"Bearer {teacher_user['token']}"}
        )
        
        assert response.status_code == 403
        assert "访问被拒绝" in response.json()["detail"]
    
    def test_upload_as_student(self, student_user):
        """测试学生用户上传文档（应该被拒绝）"""
        file_content = b"PDF content here"
        files = {
            "file": ("test_document.pdf", io.BytesIO(file_content), "application/pdf")
        }
        
        response = client.post(
            "/api/admin/kb/documents",
            files=files,
            headers={"Authorization": f"Bearer {student_user['token']}"}
        )
        
        assert response.status_code == 403
        assert "访问被拒绝" in response.json()["detail"]


class TestDocumentList:
    """测试文档列表端点"""
    
    def test_list_documents_empty(self, admin_user):
        """测试获取空文档列表"""
        response = client.get(
            "/api/admin/kb/documents",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["message"] == "获取文档列表成功"
        assert data["data"]["documents"] == []
        assert data["data"]["total"] == 0
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 20
        assert data["data"]["total_pages"] == 0
    
    def test_list_documents_with_data(self, admin_user):
        """测试获取包含文档的列表"""
        # 先上传几个文档
        db = TestingSessionLocal()
        for i in range(3):
            doc = KBDocument(
                id=uuid.uuid4(),
                filename=f"test_doc_{i}.pdf",
                file_path=f"/uploads/test_doc_{i}.pdf",
                file_type="application/pdf",
                file_size=1024 * (i + 1),
                upload_status="completed",
                uploaded_by=admin_user["user"].id
            )
            db.add(doc)
        db.commit()
        db.close()
        
        response = client.get(
            "/api/admin/kb/documents",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert len(data["data"]["documents"]) == 3
        assert data["data"]["total"] == 3
        assert data["data"]["total_pages"] == 1
        
        # 验证文档包含所有必需字段
        doc = data["data"]["documents"][0]
        assert "id" in doc
        assert "filename" in doc
        assert "file_type" in doc
        assert "file_size" in doc
        assert "upload_status" in doc
        assert "uploaded_by" in doc
        assert "uploaded_at" in doc
    
    def test_list_documents_pagination(self, admin_user):
        """测试文档列表分页"""
        # 创建25个文档
        db = TestingSessionLocal()
        for i in range(25):
            doc = KBDocument(
                id=uuid.uuid4(),
                filename=f"test_doc_{i}.pdf",
                file_path=f"/uploads/test_doc_{i}.pdf",
                file_type="application/pdf",
                file_size=1024,
                upload_status="completed",
                uploaded_by=admin_user["user"].id
            )
            db.add(doc)
        db.commit()
        db.close()
        
        # 获取第一页（默认20条）
        response = client.get(
            "/api/admin/kb/documents?page=1&page_size=20",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["documents"]) == 20
        assert data["data"]["total"] == 25
        assert data["data"]["page"] == 1
        assert data["data"]["total_pages"] == 2
        
        # 获取第二页
        response = client.get(
            "/api/admin/kb/documents?page=2&page_size=20",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["documents"]) == 5
        assert data["data"]["page"] == 2
    
    def test_list_documents_custom_page_size(self, admin_user):
        """测试自定义每页数量"""
        # 创建15个文档
        db = TestingSessionLocal()
        for i in range(15):
            doc = KBDocument(
                id=uuid.uuid4(),
                filename=f"test_doc_{i}.pdf",
                file_path=f"/uploads/test_doc_{i}.pdf",
                file_type="application/pdf",
                file_size=1024,
                upload_status="completed",
                uploaded_by=admin_user["user"].id
            )
            db.add(doc)
        db.commit()
        db.close()
        
        # 每页10条
        response = client.get(
            "/api/admin/kb/documents?page=1&page_size=10",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["documents"]) == 10
        assert data["data"]["total"] == 15
        assert data["data"]["page_size"] == 10
        assert data["data"]["total_pages"] == 2
    
    def test_list_documents_invalid_page(self, admin_user):
        """测试无效的页码"""
        response = client.get(
            "/api/admin/kb/documents?page=0",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 400
        assert "页码必须大于0" in response.json()["detail"]
    
    def test_list_documents_invalid_page_size(self, admin_user):
        """测试无效的每页数量"""
        # 测试page_size为0
        response = client.get(
            "/api/admin/kb/documents?page_size=0",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 400
        assert "每页数量必须在1-100之间" in response.json()["detail"]
        
        # 测试page_size超过100
        response = client.get(
            "/api/admin/kb/documents?page_size=101",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 400
        assert "每页数量必须在1-100之间" in response.json()["detail"]
    
    def test_list_documents_without_authentication(self):
        """测试未认证用户获取文档列表"""
        response = client.get("/api/admin/kb/documents")
        
        # 未认证应该返回401
        assert response.status_code == 401
    
    def test_list_documents_as_teacher(self, teacher_user):
        """测试教师用户获取文档列表（应该被拒绝）"""
        response = client.get(
            "/api/admin/kb/documents",
            headers={"Authorization": f"Bearer {teacher_user['token']}"}
        )
        
        assert response.status_code == 403
        assert "访问被拒绝" in response.json()["detail"]
    
    def test_list_documents_as_student(self, student_user):
        """测试学生用户获取文档列表（应该被拒绝）"""
        response = client.get(
            "/api/admin/kb/documents",
            headers={"Authorization": f"Bearer {student_user['token']}"}
        )
        
        assert response.status_code == 403
        assert "访问被拒绝" in response.json()["detail"]


class TestDocumentDeletion:
    """测试文档删除端点"""
    
    def test_delete_document_as_admin(self, admin_user):
        """测试管理员删除文档"""
        # 先创建一个文档
        db = TestingSessionLocal()
        doc = KBDocument(
            id=uuid.uuid4(),
            filename="test_doc_to_delete.pdf",
            file_path="/uploads/test_doc_to_delete.pdf",
            file_type="application/pdf",
            file_size=1024,
            upload_status="completed",
            uploaded_by=admin_user["user"].id
        )
        db.add(doc)
        db.commit()
        doc_id = str(doc.id)
        db.close()
        
        # 删除文档
        response = client.delete(
            f"/api/admin/kb/documents/{doc_id}",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["message"] == "文档删除成功"
        assert data["data"]["document_id"] == doc_id
        assert data["data"]["deleted"] is True
        
        # 验证文档已从数据库删除
        db = TestingSessionLocal()
        deleted_doc = db.query(KBDocument).filter(KBDocument.id == uuid.UUID(doc_id)).first()
        assert deleted_doc is None
        db.close()
    
    def test_delete_nonexistent_document(self, admin_user):
        """测试删除不存在的文档"""
        fake_id = str(uuid.uuid4())
        
        response = client.delete(
            f"/api/admin/kb/documents/{fake_id}",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        assert response.status_code == 404
        # 检查错误消息包含文档ID
        assert fake_id in response.json()["detail"]
    
    def test_delete_document_without_authentication(self):
        """测试未认证用户删除文档"""
        fake_id = str(uuid.uuid4())
        
        response = client.delete(f"/api/admin/kb/documents/{fake_id}")
        
        # 未认证应该返回401
        assert response.status_code == 401
    
    def test_delete_document_as_teacher(self, teacher_user, admin_user):
        """测试教师用户删除文档（应该被拒绝）"""
        # 先创建一个文档
        db = TestingSessionLocal()
        doc = KBDocument(
            id=uuid.uuid4(),
            filename="test_doc.pdf",
            file_path="/uploads/test_doc.pdf",
            file_type="application/pdf",
            file_size=1024,
            upload_status="completed",
            uploaded_by=admin_user["user"].id
        )
        db.add(doc)
        db.commit()
        doc_id = str(doc.id)
        db.close()
        
        # 教师尝试删除
        response = client.delete(
            f"/api/admin/kb/documents/{doc_id}",
            headers={"Authorization": f"Bearer {teacher_user['token']}"}
        )
        
        assert response.status_code == 403
        assert "访问被拒绝" in response.json()["detail"]
        
        # 验证文档仍然存在
        db = TestingSessionLocal()
        doc = db.query(KBDocument).filter(KBDocument.id == uuid.UUID(doc_id)).first()
        assert doc is not None
        db.close()
    
    def test_delete_document_as_student(self, student_user, admin_user):
        """测试学生用户删除文档（应该被拒绝）"""
        # 先创建一个文档
        db = TestingSessionLocal()
        doc = KBDocument(
            id=uuid.uuid4(),
            filename="test_doc.pdf",
            file_path="/uploads/test_doc.pdf",
            file_type="application/pdf",
            file_size=1024,
            upload_status="completed",
            uploaded_by=admin_user["user"].id
        )
        db.add(doc)
        db.commit()
        doc_id = str(doc.id)
        db.close()
        
        # 学生尝试删除
        response = client.delete(
            f"/api/admin/kb/documents/{doc_id}",
            headers={"Authorization": f"Bearer {student_user['token']}"}
        )
        
        assert response.status_code == 403
        assert "访问被拒绝" in response.json()["detail"]
        
        # 验证文档仍然存在
        db = TestingSessionLocal()
        doc = db.query(KBDocument).filter(KBDocument.id == uuid.UUID(doc_id)).first()
        assert doc is not None
        db.close()
    
    def test_delete_document_invalid_uuid(self, admin_user):
        """测试使用无效的UUID删除文档"""
        invalid_id = "not-a-valid-uuid"
        
        response = client.delete(
            f"/api/admin/kb/documents/{invalid_id}",
            headers={"Authorization": f"Bearer {admin_user['token']}"}
        )
        
        # 无效UUID会被当作不存在的文档处理，返回404
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
