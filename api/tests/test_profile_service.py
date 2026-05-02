import uuid

import pytest

from models.class_model import Class
from models.user import User
from services.avatar_service import AvatarService
from services.profile_service import ProfileService


@pytest.fixture
def profile_teacher_and_classes(db_session):
    teacher = User(
        id=uuid.uuid4(),
        account="profile_teacher",
        password_hash="hashed_password",
        user_type="teacher",
        name="Profile Teacher",
        email="profile-teacher@test.com",
    )
    db_session.add(teacher)
    db_session.flush()

    class_a = Class(
        id=uuid.uuid4(),
        name="Class A",
        code="CLASSA",
        teacher_id=teacher.id,
    )
    class_b = Class(
        id=uuid.uuid4(),
        name="Class B",
        code="CLASSB",
        teacher_id=teacher.id,
    )
    db_session.add_all([class_a, class_b])
    db_session.commit()

    return teacher, class_a, class_b


def test_student_can_set_class_once(db_session, profile_teacher_and_classes):
    _, class_a, _ = profile_teacher_and_classes
    student = User(
        id=uuid.uuid4(),
        account="student_without_class",
        password_hash="hashed_password",
        user_type="student",
        name="Student Without Class",
        email="student-without-class@test.com",
    )
    db_session.add(student)
    db_session.commit()

    result = ProfileService.update_profile(
        db=db_session,
        user_id=str(student.id),
        class_id=str(class_a.id),
    )

    db_session.refresh(student)
    assert result["class_id"] == str(class_a.id)
    assert student.class_id == class_a.id


def test_student_cannot_change_selected_class(db_session, profile_teacher_and_classes):
    _, class_a, class_b = profile_teacher_and_classes
    student = User(
        id=uuid.uuid4(),
        account="student_locked_class",
        password_hash="hashed_password",
        user_type="student",
        name="Student Locked Class",
        email="student-locked-class@test.com",
        class_id=class_a.id,
    )
    db_session.add(student)
    db_session.commit()

    with pytest.raises(ValueError, match="学生选择班级后不可修改"):
        ProfileService.update_profile(
            db=db_session,
            user_id=str(student.id),
            class_id=str(class_b.id),
        )


def test_student_cannot_clear_selected_class(db_session, profile_teacher_and_classes):
    _, class_a, _ = profile_teacher_and_classes
    student = User(
        id=uuid.uuid4(),
        account="student_clear_class",
        password_hash="hashed_password",
        user_type="student",
        name="Student Clear Class",
        email="student-clear-class@test.com",
        class_id=class_a.id,
    )
    db_session.add(student)
    db_session.commit()

    with pytest.raises(ValueError, match="学生选择班级后不可修改"):
        ProfileService.update_profile(
            db=db_session,
            user_id=str(student.id),
            class_id="",
        )


def test_student_can_update_profile_with_same_class(db_session, profile_teacher_and_classes):
    _, class_a, _ = profile_teacher_and_classes
    student = User(
        id=uuid.uuid4(),
        account="student_same_class",
        password_hash="hashed_password",
        user_type="student",
        name="Old Name",
        email="student-same-class@test.com",
        class_id=class_a.id,
    )
    db_session.add(student)
    db_session.commit()

    result = ProfileService.update_profile(
        db=db_session,
        user_id=str(student.id),
        name="New Name",
        class_id=str(class_a.id),
    )

    db_session.refresh(student)
    assert result["name"] == "New Name"
    assert result["class_id"] == str(class_a.id)
    assert student.name == "New Name"
    assert student.class_id == class_a.id


def test_profile_includes_avatar_payload(db_session):
    student = User(
        id=uuid.uuid4(),
        account="student_avatar_profile",
        password_hash="hashed_password",
        user_type="student",
        name="Avatar Student",
        email="student-avatar-profile@test.com",
        avatar_default_key="minimal-block-01",
    )
    db_session.add(student)
    db_session.commit()

    profile = ProfileService.get_profile(db=db_session, user_id=str(student.id))

    assert profile["avatar_mode"] == "default"
    assert profile["avatar_default_key"] == "minimal-block-01"
    assert profile["avatar"]
    assert profile["avatar_url"] == profile["avatar"]


def test_apply_default_avatar_updates_profile(db_session):
    teacher = User(
        id=uuid.uuid4(),
        account="teacher_avatar_default",
        password_hash="hashed_password",
        user_type="teacher",
        name="Default Avatar Teacher",
        email="teacher-avatar-default@test.com",
    )
    db_session.add(teacher)
    db_session.commit()

    AvatarService.apply_default_avatar(
        db=db_session,
        user=teacher,
        default_key="minimal-block-02",
    )

    refreshed = ProfileService.get_profile(db=db_session, user_id=str(teacher.id))
    assert refreshed["avatar_mode"] == "default"
    assert refreshed["avatar_default_key"] == "minimal-block-02"
