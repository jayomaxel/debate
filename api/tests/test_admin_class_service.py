"""
测试管理员班级管理功能
"""
import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from services.class_service import ClassService
from models.user import User
from models.class_model import Class
from utils.security import hash_password


# 创建测试数据库
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_teachers(db_session):
    """创建示例教师"""
    teachers = []
    for i in range(3):
        teacher = User(
            id=uuid.uuid4(),
            account=f"teacher{i+1}",
            password_hash=hash_password("Teacher123!"),
            user_type="teacher",
            name=f"教师{i+1}",
            email=f"teacher{i+1}@test.com"
        )
        db_session.add(teacher)
        teachers.append(teacher)
    
    db_session.commit()
    return teachers


@pytest.fixture
def sample_classes(db_session, sample_teachers):
    """创建示例班级"""
    classes = []
    for i, teacher in enumerate(sample_teachers):
        cls = Class(
            id=uuid.uuid4(),
            name=f"班级{i+1}",
            code=f"CODE{i+1}",
            teacher_id=teacher.id
        )
        db_session.add(cls)
        classes.append(cls)
    
    db_session.commit()
    return classes


@pytest.fixture
def sample_students(db_session, sample_classes):
    """创建示例学生"""
    students = []
    for i, cls in enumerate(sample_classes):
        # 为每个班级创建2个学生
        for j in range(2):
            student = User(
                id=uuid.uuid4(),
                account=f"student{i*2+j+1}",
                password_hash=hash_password("Student123!"),
                user_type="student",
                name=f"学生{i*2+j+1}",
                email=f"student{i*2+j+1}@test.com",
                class_id=cls.id
            )
            db_session.add(student)
            students.append(student)
    
    db_session.commit()
    return students


def test_get_all_classes_returns_all_classes(db_session, sample_classes, sample_students):
    """测试管理员可以查看所有班级"""
    result = ClassService.get_all_classes(db_session)
    
    # 验证返回所有班级
    assert len(result) == 3
    
    # 验证每个班级包含必要信息
    for cls in result:
        assert "id" in cls
        assert "name" in cls
        assert "code" in cls
        assert "teacher_id" in cls
        assert "teacher_name" in cls
        assert "student_count" in cls
        assert "created_at" in cls
        
        # 验证学生数量正确
        assert cls["student_count"] == 2


def test_get_all_classes_includes_teacher_name(db_session, sample_classes, sample_teachers):
    """测试获取所有班级时包含教师名称"""
    result = ClassService.get_all_classes(db_session)
    
    # 验证教师名称正确
    for i, cls in enumerate(result):
        assert cls["teacher_name"] == f"教师{i+1}"


def test_get_all_classes_empty_database(db_session):
    """测试空数据库时获取所有班级"""
    result = ClassService.get_all_classes(db_session)
    
    assert result == []


def test_create_class_for_teacher_with_valid_teacher(db_session, sample_teachers):
    """测试管理员为指定教师创建班级"""
    teacher = sample_teachers[0]
    
    result = ClassService.create_class_for_teacher(
        db=db_session,
        teacher_id=str(teacher.id),
        name="新班级"
    )
    
    # 验证返回结果
    assert result is not None
    assert result["name"] == "新班级"
    assert result["teacher_id"] == str(teacher.id)
    assert result["teacher_name"] == teacher.name
    assert result["student_count"] == 0
    assert "code" in result
    assert "created_at" in result
    
    # 验证班级已创建
    created_class = db_session.query(Class).filter(
        Class.name == "新班级"
    ).first()
    
    assert created_class is not None
    assert created_class.teacher_id == teacher.id


def test_create_class_for_teacher_with_invalid_teacher(db_session):
    """测试为不存在的教师创建班级"""
    fake_teacher_id = str(uuid.uuid4())
    
    with pytest.raises(ValueError, match="教师不存在"):
        ClassService.create_class_for_teacher(
            db=db_session,
            teacher_id=fake_teacher_id,
            name="新班级"
        )


def test_create_class_for_teacher_generates_unique_code(db_session, sample_teachers):
    """测试创建班级时生成唯一代码"""
    teacher = sample_teachers[0]
    
    # 创建多个班级
    codes = set()
    for i in range(5):
        result = ClassService.create_class_for_teacher(
            db=db_session,
            teacher_id=str(teacher.id),
            name=f"班级{i}"
        )
        codes.add(result["code"])
    
    # 验证所有代码都是唯一的
    assert len(codes) == 5


def test_update_any_class_name(db_session, sample_classes):
    """测试管理员更新班级名称"""
    cls = sample_classes[0]
    
    result = ClassService.update_any_class(
        db=db_session,
        class_id=str(cls.id),
        name="更新后的班级名称"
    )
    
    # 验证返回结果
    assert result is not None
    assert result["name"] == "更新后的班级名称"
    assert result["id"] == str(cls.id)
    
    # 验证数据库已更新
    updated_class = db_session.query(Class).filter(Class.id == cls.id).first()
    assert updated_class.name == "更新后的班级名称"


def test_update_any_class_teacher(db_session, sample_classes, sample_teachers):
    """测试管理员更新班级教师"""
    cls = sample_classes[0]
    new_teacher = sample_teachers[1]
    
    result = ClassService.update_any_class(
        db=db_session,
        class_id=str(cls.id),
        teacher_id=str(new_teacher.id)
    )
    
    # 验证返回结果
    assert result is not None
    assert result["teacher_id"] == str(new_teacher.id)
    assert result["teacher_name"] == new_teacher.name
    
    # 验证数据库已更新
    updated_class = db_session.query(Class).filter(Class.id == cls.id).first()
    assert updated_class.teacher_id == new_teacher.id


def test_update_any_class_both_name_and_teacher(db_session, sample_classes, sample_teachers):
    """测试管理员同时更新班级名称和教师"""
    cls = sample_classes[0]
    new_teacher = sample_teachers[2]
    
    result = ClassService.update_any_class(
        db=db_session,
        class_id=str(cls.id),
        name="新名称",
        teacher_id=str(new_teacher.id)
    )
    
    # 验证返回结果
    assert result is not None
    assert result["name"] == "新名称"
    assert result["teacher_id"] == str(new_teacher.id)
    assert result["teacher_name"] == new_teacher.name
    
    # 验证数据库已更新
    updated_class = db_session.query(Class).filter(Class.id == cls.id).first()
    assert updated_class.name == "新名称"
    assert updated_class.teacher_id == new_teacher.id


def test_update_any_class_with_invalid_class_id(db_session):
    """测试更新不存在的班级"""
    fake_class_id = str(uuid.uuid4())
    
    with pytest.raises(ValueError, match="班级不存在"):
        ClassService.update_any_class(
            db=db_session,
            class_id=fake_class_id,
            name="新名称"
        )


def test_update_any_class_with_invalid_teacher_id(db_session, sample_classes):
    """测试使用不存在的教师ID更新班级"""
    cls = sample_classes[0]
    fake_teacher_id = str(uuid.uuid4())
    
    with pytest.raises(ValueError, match="教师不存在"):
        ClassService.update_any_class(
            db=db_session,
            class_id=str(cls.id),
            teacher_id=fake_teacher_id
        )


def test_delete_any_class_removes_class(db_session, sample_classes):
    """测试管理员删除班级"""
    cls = sample_classes[0]
    class_id = cls.id
    
    result = ClassService.delete_any_class(
        db=db_session,
        class_id=str(class_id)
    )
    
    # 验证返回成功
    assert result is True
    
    # 验证班级已删除
    deleted_class = db_session.query(Class).filter(Class.id == class_id).first()
    assert deleted_class is None


def test_delete_any_class_handles_student_enrollments(db_session, sample_classes, sample_students):
    """测试删除班级时处理学生注册"""
    cls = sample_classes[0]
    class_id = cls.id
    
    # 验证班级有学生
    students_before = db_session.query(User).filter(User.class_id == class_id).all()
    assert len(students_before) == 2
    
    # 删除班级
    result = ClassService.delete_any_class(
        db=db_session,
        class_id=str(class_id)
    )
    
    assert result is True
    
    # 验证学生的class_id已设置为None
    students_after = db_session.query(User).filter(User.class_id == class_id).all()
    assert len(students_after) == 0
    
    # 验证学生仍然存在，只是class_id为None
    for student in students_before:
        updated_student = db_session.query(User).filter(User.id == student.id).first()
        assert updated_student is not None
        assert updated_student.class_id is None


def test_delete_any_class_with_invalid_class_id(db_session):
    """测试删除不存在的班级"""
    fake_class_id = str(uuid.uuid4())
    
    with pytest.raises(ValueError, match="班级不存在"):
        ClassService.delete_any_class(
            db=db_session,
            class_id=fake_class_id
        )


def test_admin_can_manage_classes_from_different_teachers(db_session, sample_classes, sample_teachers):
    """测试管理员可以管理不同教师的班级"""
    # 获取所有班级
    all_classes = ClassService.get_all_classes(db_session)
    assert len(all_classes) == 3
    
    # 更新第一个教师的班级
    result1 = ClassService.update_any_class(
        db=db_session,
        class_id=str(sample_classes[0].id),
        name="更新班级1"
    )
    assert result1["name"] == "更新班级1"
    
    # 更新第二个教师的班级
    result2 = ClassService.update_any_class(
        db=db_session,
        class_id=str(sample_classes[1].id),
        name="更新班级2"
    )
    assert result2["name"] == "更新班级2"
    
    # 删除第三个教师的班级
    result3 = ClassService.delete_any_class(
        db=db_session,
        class_id=str(sample_classes[2].id)
    )
    assert result3 is True
    
    # 验证只剩下2个班级
    remaining_classes = ClassService.get_all_classes(db_session)
    assert len(remaining_classes) == 2


def test_class_response_completeness(db_session, sample_classes, sample_students):
    """测试班级响应包含所有必需字段（验证需求3.5）"""
    result = ClassService.get_all_classes(db_session)
    
    required_fields = [
        "id", "name", "code", "teacher_id", "teacher_name", 
        "student_count", "created_at"
    ]
    
    for cls in result:
        for field in required_fields:
            assert field in cls, f"Missing required field: {field}"
        
        # 验证字段类型
        assert isinstance(cls["id"], str)
        assert isinstance(cls["name"], str)
        assert isinstance(cls["code"], str)
        assert isinstance(cls["teacher_id"], str)
        assert isinstance(cls["teacher_name"], str)
        assert isinstance(cls["student_count"], int)
        assert isinstance(cls["created_at"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
