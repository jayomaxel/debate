"""
璁よ瘉API璺敱
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from database import get_db
from models.user import User
from services.auth_service import AuthService
from middleware.auth_middleware import verify_token_middleware

router = APIRouter(prefix="/api/auth", tags=["璁よ瘉"])


# Pydantic妯″瀷
class TeacherRegisterRequest(BaseModel):
    account: str  # 鏁欏伐鍙?
    email: EmailStr
    phone: str
    password: str
    name: str


class StudentRegisterRequest(BaseModel):
    account: str
    password: str
    name: str
    class_id: Optional[str] = None  # 鐝骇ID锛堝彲閫夛級
    email: Optional[EmailStr] = None
    student_id: Optional[str] = None


class LoginRequest(BaseModel):
    account: str
    password: str
    user_type: str  # teacher銆乻tudent鎴朼dministrator


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    student_id: Optional[str] = None
    class_id: Optional[str] = None  # 鏂板锛氱彮绾D


# API绔偣
@router.get("/classes/public", summary="获取公开班级列表")
async def get_public_classes(db: Session = Depends(get_db)):
    """
    鑾峰彇鎵€鏈夌彮绾у垪琛紙鐢ㄤ簬娉ㄥ唽鏃堕€夋嫨锛?
    杩斿洖鐝骇ID銆佸悕绉般€佹暀甯堝鍚嶇瓑淇℃伅
    """
    from models.class_model import Class
    from models.user import User
    
    try:
        classes = db.query(Class).join(User, Class.teacher_id == User.id).all()
        
        result = []
        for cls in classes:
            teacher = db.query(User).filter(User.id == cls.teacher_id).first()
            result.append({
                "id": str(cls.id),
                "name": cls.name,
                "code": cls.code,
                "teacher_name": teacher.name if teacher else "鏈煡",
                "student_count": db.query(User).filter(User.class_id == cls.id).count()
            })
        
        return {
            "code": 200,
            "message": "鑾峰彇鎴愬姛",
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"鑾峰彇鐝骇鍒楄〃澶辫触: {str(e)}"
        )
@router.post("/register/teacher", summary="鏁欏笀娉ㄥ唽")
async def register_teacher(
    request: TeacherRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    鏁欏笀娉ㄥ唽
    
    - **account**: 鏁欏伐鍙?
    - **email**: 閭
    - **phone**: 鎵嬫満鍙?
    - **password**: 瀵嗙爜
    - **name**: 濮撳悕
    """
    try:
        user = AuthService.register_teacher(
            db=db,
            account=request.account,
            email=request.email,
            phone=request.phone,
            password=request.password,
            name=request.name
        )
        return {
            "code": 200,
            "message": "娉ㄥ唽鎴愬姛",
            "data": user
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/register/student", summary="瀛︾敓娉ㄥ唽")
async def register_student(
    request: StudentRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    瀛︾敓娉ㄥ唽
    
    - **account**: 璐﹀彿
    - **password**: 瀵嗙爜
    - **name**: 濮撳悕
    - **class_id**: 鐝骇ID锛堝彲閫夛級
    - **email**: 閭锛堝彲閫夛級
    - **student_id**: 瀛﹀彿锛堝彲閫夛級
    """
    try:
        user = AuthService.register_student(
            db=db,
            account=request.account,
            password=request.password,
            name=request.name,
            class_id=request.class_id,
            email=request.email,
            student_id=request.student_id
        )
        return {
            "code": 200,
            "message": "娉ㄥ唽鎴愬姛",
            "data": user
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", summary="鐢ㄦ埛鐧诲綍")
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    鐢ㄦ埛鐧诲綍
    
    - **account**: 璐﹀彿
    - **password**: 瀵嗙爜
    - **user_type**: 鐢ㄦ埛绫诲瀷锛坱eacher銆乻tudent鎴朼dministrator锛?
    """
    try:
        result = AuthService.login(
            db=db,
            account=request.account,
            password=request.password,
            user_type=request.user_type
        )
        return {
            "code": 200,
            "message": "鐧诲綍鎴愬姛",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/refresh", summary="鍒锋柊浠ょ墝")
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    鍒锋柊璁块棶浠ょ墝
    
    - **refresh_token**: 鍒锋柊浠ょ墝
    """
    try:
        result = AuthService.refresh_token(
            db=db,
            refresh_token=request.refresh_token
        )
        return {
            "code": 200,
            "message": "鍒锋柊鎴愬姛",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/change-password", summary="淇敼瀵嗙爜")
async def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware)
):
    """
    淇敼瀵嗙爜锛堥渶瑕佺櫥褰曪級
    
    - **old_password**: 鏃у瘑鐮?
    - **new_password**: 鏂板瘑鐮?
    """
    try:
        AuthService.change_password(
            db=db,
            user_id=str(current_user.id),
            old_password=request.old_password,
            new_password=request.new_password
        )
        return {
            "code": 200,
            "message": "瀵嗙爜淇敼鎴愬姛"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/profile", summary="鑾峰彇涓汉淇℃伅")
async def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware)
):
    """
    鑾峰彇褰撳墠鐢ㄦ埛鐨勪釜浜轰俊鎭紙闇€瑕佺櫥褰曪級
    """
    from services.profile_service import ProfileService
    
    try:
        profile = ProfileService.get_profile(db=db, user_id=str(current_user.id))
        return {
            "code": 200,
            "message": "鑾峰彇鎴愬姛",
            "data": profile
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/profile", summary="鏇存柊涓汉淇℃伅")
async def update_profile(
    request: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware)
):
    """
    鏇存柊涓汉淇℃伅锛堥渶瑕佺櫥褰曪級
    
    - **name**: 濮撳悕锛堝彲閫夛級
    - **email**: 閭锛堝彲閫夛級
    - **phone**: 鎵嬫満鍙凤紙鍙€夛級
    - **student_id**: 瀛﹀彿锛堝彲閫夛紝浠呭鐢燂級
    - **class_id**: 鐝骇ID锛堝彲閫夛紝浠呭鐢燂級
    """
    from services.profile_service import ProfileService
    
    try:
        result = ProfileService.update_profile(
            db=db,
            user_id=str(current_user.id),
            name=request.name,
            email=request.email,
            phone=request.phone,
            student_id=request.student_id,
            class_id=request.class_id
        )
        return {
            "code": 200,
            "message": "鏇存柊鎴愬姛",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )



class DeleteAccountRequest(BaseModel):
    password: str


@router.post("/delete-account", summary="娉ㄩ攢璐︽埛")
async def delete_account(
    request: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware),
):
    """
    娉ㄩ攢璐︽埛
    
    - **password**: 瀵嗙爜锛堢敤浜庣‘璁わ級
    
    娉ㄦ剰锛?
    - 瀛︾敓璐︽埛锛氳蒋鍒犻櫎锛屼繚鐣欏尶鍚嶅寲鐨勫巻鍙叉暟鎹?
    - 鏁欏笀璐︽埛锛氶渶瑕佸厛鍒犻櫎鎴栬浆绉绘墍鏈夌彮绾?
    """
    
    try:
        result = AuthService.delete_account(
            db=db,
            user_id=str(current_user.id),
            password=request.password
        )
        return {
            "code": 200,
            "message": result["message"],
            "data": {
                "data_retained": result["data_retained"],
                "note": result["note"]
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

