"""
认证API路由
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from database import get_db
from models.user import User
from services.auth_service import AuthService
from services.avatar_service import AvatarService
from middleware.auth_middleware import verify_token_middleware
from schemas.auth import SelectDefaultAvatarRequest

router = APIRouter(prefix="/api/auth", tags=["认证"])


# Pydantic模型
class TeacherRegisterRequest(BaseModel):
    account: str  # 教工号
    email: EmailStr
    phone: str
    password: str
    name: str


class StudentRegisterRequest(BaseModel):
    account: str
    password: str
    name: str
    class_id: Optional[str] = None  # 班级ID（可选）
    email: Optional[EmailStr] = None
    student_id: Optional[str] = None


class LoginRequest(BaseModel):
    account: str
    password: str
    user_type: str  # teacher、student或administrator


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
    class_id: Optional[str] = None  # 新增：班级ID


# API端点
@router.get("/classes/public", summary="获取公开班级列表")
async def get_public_classes(db: Session = Depends(get_db)):
    """
    获取所有班级列表（用于注册时选择）
    返回班级ID、名称、教师姓名等信息
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
                "teacher_name": teacher.name if teacher else "未知",
                "student_count": db.query(User).filter(User.class_id == cls.id).count()
            })
        
        return {
            "code": 200,
            "message": "获取成功",
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取班级列表失败: {str(e)}"
        )
@router.post("/register/teacher", summary="教师注册")
async def register_teacher(
    request: TeacherRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    教师注册
    
    - **account**: 教工号
    - **email**: 邮箱
    - **phone**: 手机号
    - **password**: 密码
    - **name**: 姓名
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
            "message": "注册成功",
            "data": user
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/register/student", summary="学生注册")
async def register_student(
    request: StudentRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    学生注册
    
    - **account**: 账号
    - **password**: 密码
    - **name**: 姓名
    - **class_id**: 班级ID（可选）
    - **email**: 邮箱（可选）
    - **student_id**: 学号（可选）
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
            "message": "注册成功",
            "data": user
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", summary="用户登录")
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    用户登录
    
    - **account**: 璐﹀彿
    - **password**: 密码
    - **user_type**: 用户类型（teacher、student或administrator）
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
            "message": "登录成功",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/refresh", summary="刷新令牌")
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    刷新访问令牌
    
    - **refresh_token**: 刷新令牌
    """
    try:
        result = AuthService.refresh_token(
            db=db,
            refresh_token=request.refresh_token
        )
        return {
            "code": 200,
            "message": "刷新成功",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/change-password", summary="修改密码")
async def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware)
):
    """
    修改密码（需要登录）
    
    - **old_password**: 旧密码
    - **new_password**: 新密码
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
            "message": "密码修改成功"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/profile", summary="获取个人信息")
async def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware)
):
    """
    获取当前用户的个人信息（需要登录）
    """
    from services.profile_service import ProfileService
    
    try:
        profile = ProfileService.get_profile(db=db, user_id=str(current_user.id))
        return {
            "code": 200,
            "message": "获取成功",
            "data": profile
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/profile", summary="更新个人信息")
async def update_profile(
    request: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware)
):
    """
    更新个人信息（需要登录）
    
    - **name**: 姓名（可选）
    - **email**: 邮箱（可选）
    - **phone**: 手机号（可选）
    - **student_id**: 学号（可选，仅学生）
    - **class_id**: 班级ID（可选，仅学生）
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
            "message": "更新成功",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/avatars/defaults", summary="获取默认头像列表")
async def get_default_avatars():
    return {
        "code": 200,
        "message": "获取成功",
        "data": AvatarService.list_default_avatars(),
    }


@router.post("/profile/avatar/upload", summary="上传自定义头像")
async def upload_profile_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware),
):
    try:
        content = await file.read()
        avatar_payload = AvatarService.apply_custom_avatar(
            db=db,
            user=current_user,
            content=content,
            filename=file.filename,
        )
        return {
            "code": 200,
            "message": "头像上传成功",
            "data": avatar_payload,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/profile/avatar/default", summary="切换默认头像")
async def select_default_avatar(
    request: SelectDefaultAvatarRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware),
):
    try:
        avatar_payload = AvatarService.apply_default_avatar(
            db=db,
            user=current_user,
            default_key=request.avatar_default_key,
        )
        return {
            "code": 200,
            "message": "默认头像已更新",
            "data": avatar_payload,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/profile/avatar", summary="清除头像")
async def clear_profile_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware),
):
    avatar_payload = AvatarService.clear_avatar(db=db, user=current_user)
    return {
        "code": 200,
        "message": "头像已清除",
        "data": avatar_payload,
    }



class DeleteAccountRequest(BaseModel):
    password: str


@router.post("/delete-account", summary="注销账户")
async def delete_account(
    request: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_token_middleware),
):
    """
    注销账户
    
    - **password**: 密码（用于确认）
    
    注意：
    - 学生账户：软删除，保留匿名化的历史数据
    - 教师账户：需要先删除或转移所有班级
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
