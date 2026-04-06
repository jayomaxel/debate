"""
Class management schemas for API request/response validation
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ClassResponse(BaseModel):
    """Class response schema with complete information"""
    id: str
    name: str
    code: str
    teacher_id: str
    teacher_name: str  # Included for administrator view
    student_count: int  # Included for administrator view
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Advanced Debate Class",
                "code": "ADC2024",
                "teacher_id": "123e4567-e89b-12d3-a456-426614174001",
                "teacher_name": "Dr. Smith",
                "student_count": 25,
                "created_at": "2024-01-15T10:30:00"
            }
        }


class ClassCreate(BaseModel):
    """Class creation request schema"""
    name: str
    code: Optional[str] = None  # Optional, can be auto-generated
    teacher_id: str  # Required for administrator to assign class to teacher
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Advanced Debate Class",
                "code": "ADC2024",
                "teacher_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }


class ClassUpdate(BaseModel):
    """Class update request schema"""
    name: Optional[str] = None
    code: Optional[str] = None
    teacher_id: Optional[str] = None  # Allow reassigning to different teacher
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Advanced Debate Class - Updated",
                "code": "ADC2024-V2"
            }
        }


class ClassListResponse(BaseModel):
    """Response for listing multiple classes"""
    classes: list[ClassResponse]
    total: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "classes": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "Advanced Debate Class",
                        "code": "ADC2024",
                        "teacher_id": "123e4567-e89b-12d3-a456-426614174001",
                        "teacher_name": "Dr. Smith",
                        "student_count": 25,
                        "created_at": "2024-01-15T10:30:00"
                    }
                ],
                "total": 1
            }
        }


class SimpleClassResponse(BaseModel):
    """Simplified class response for teacher view"""
    id: str
    name: str
    code: str
    created_at: datetime
    student_count: int
    
    class Config:
        from_attributes = True
