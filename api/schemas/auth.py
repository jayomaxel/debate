"""
Authentication schemas for API request/response validation
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """Login request schema"""
    account: str
    password: str
    user_type: str  # "teacher", "student", or "administrator"
    
    class Config:
        json_schema_extra = {
            "example": {
                "account": "admin",
                "password": "Admin123!",
                "user_type": "administrator"
            }
        }


class UserResponse(BaseModel):
    """User information in response"""
    id: str
    account: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    student_id: Optional[str] = None
    class_id: Optional[str] = None
    user_type: str
    avatar: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_mode: Optional[str] = None
    avatar_default_key: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Login response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
    user_type: str  # Role information
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "token_type": "bearer",
                "user": {
                    "id": "1",
                    "account": "admin",
                    "name": "Administrator",
                    "email": "admin@system.local",
                    "user_type": "administrator"
                },
                "user_type": "administrator"
            }
        }


class PasswordChangeRequest(BaseModel):
    """Password change request schema"""
    current_password: str
    new_password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_password": "Admin123!",
                "new_password": "NewSecurePass123!"
            }
        }


class TeacherRegisterRequest(BaseModel):
    """Teacher registration request"""
    account: str  # Teacher ID number
    email: EmailStr
    phone: str
    password: str
    name: str
    class_id: Optional[str] = None


class StudentRegisterRequest(BaseModel):
    """Student registration request"""
    account: str
    password: str
    name: str
    class_id: Optional[str] = None
    email: Optional[EmailStr] = None
    student_id: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    """Update profile request"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    student_id: Optional[str] = None
    class_id: Optional[str] = None


class SelectDefaultAvatarRequest(BaseModel):
    """Select default avatar request"""
    avatar_default_key: str


class DeleteAccountRequest(BaseModel):
    """Delete account request"""
    password: str
