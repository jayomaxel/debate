"""
Test for require_role middleware function
"""
import pytest
import sys
import os
from unittest.mock import Mock
import uuid

# Add the api directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from middleware.auth_middleware import require_role
from models.user import User


def create_mock_user(user_type: str) -> User:
    """Create a mock user with specified type"""
    user = Mock(spec=User)
    user.id = uuid.uuid4()
    user.account = f"test_{user_type}"
    user.user_type = user_type
    user.name = f"Test {user_type}"
    user.email = f"{user_type}@test.com"
    return user


class TestRequireRoleFunction:
    """Test suite for require_role middleware function"""
    
    def test_require_role_returns_callable(self):
        """Test that require_role returns a callable function"""
        role_checker = require_role(["administrator"])
        assert callable(role_checker)
    
    def test_role_checker_accepts_allowed_role(self):
        """Test that role checker accepts user with allowed role"""
        admin_user = create_mock_user("administrator")
        role_checker = require_role(["administrator"])
        
        # The role_checker should return the user if role matches
        result = role_checker(current_user=admin_user)
        assert result == admin_user
    
    def test_role_checker_rejects_disallowed_role(self):
        """Test that role checker rejects user without allowed role"""
        from fastapi import HTTPException
        
        teacher_user = create_mock_user("teacher")
        role_checker = require_role(["administrator"])
        
        # The role_checker should raise HTTPException for wrong role
        with pytest.raises(HTTPException) as exc_info:
            role_checker(current_user=teacher_user)
        
        assert exc_info.value.status_code == 403
        assert "访问被拒绝" in exc_info.value.detail
        assert "administrator" in exc_info.value.detail
    
    def test_role_checker_accepts_multiple_roles(self):
        """Test that role checker accepts any of multiple allowed roles"""
        teacher_user = create_mock_user("teacher")
        admin_user = create_mock_user("administrator")
        
        role_checker = require_role(["teacher", "administrator"])
        
        # Both should be accepted
        assert role_checker(current_user=teacher_user) == teacher_user
        assert role_checker(current_user=admin_user) == admin_user
    
    def test_role_checker_rejects_when_not_in_multiple_roles(self):
        """Test that role checker rejects user not in any of the allowed roles"""
        from fastapi import HTTPException
        
        student_user = create_mock_user("student")
        role_checker = require_role(["teacher", "administrator"])
        
        with pytest.raises(HTTPException) as exc_info:
            role_checker(current_user=student_user)
        
        assert exc_info.value.status_code == 403
        assert "访问被拒绝" in exc_info.value.detail
    
    def test_error_message_includes_all_required_roles(self):
        """Test that error message lists all required roles"""
        from fastapi import HTTPException
        
        student_user = create_mock_user("student")
        role_checker = require_role(["teacher", "administrator"])
        
        with pytest.raises(HTTPException) as exc_info:
            role_checker(current_user=student_user)
        
        detail = exc_info.value.detail
        assert "teacher" in detail
        assert "administrator" in detail
    
    def test_single_role_requirement(self):
        """Test requiring a single specific role"""
        student_user = create_mock_user("student")
        teacher_user = create_mock_user("teacher")
        
        role_checker = require_role(["student"])
        
        # Student should be accepted
        assert role_checker(current_user=student_user) == student_user
        
        # Teacher should be rejected
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            role_checker(current_user=teacher_user)
        
        assert exc_info.value.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

