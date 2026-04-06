"""
安全工具函数：密码加密、JWT令牌管理
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from config import settings

# 密码加密上下文 - 配置为与bcrypt 4.x兼容
pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12  # 明确指定bcrypt轮数
)


def hash_password(password: str) -> str:
    """
    加密密码

    Args:
        password: 明文密码

    Returns:
        加密后的密码哈希
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 明文密码
        hashed_password: 加密后的密码哈希

    Returns:
        密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建访问令牌

    Args:
        data: 要编码的数据（通常包含user_id和user_type）
        expires_delta: 过期时间增量

    Returns:
        JWT访问令牌
    """
    to_encode = data.copy()

    # 使用标准JWT字段名 'sub' (subject)
    if "user_id" in to_encode and "sub" not in to_encode:
        to_encode["sub"] = to_encode["user_id"]

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    return create_access_token(data, expires_delta)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    创建刷新令牌

    Args:
        data: 要编码的数据（通常包含user_id）

    Returns:
        JWT刷新令牌
    """
    to_encode = data.copy()

    # 使用标准JWT字段名 'sub' (subject)
    if "user_id" in to_encode and "sub" not in to_encode:
        to_encode["sub"] = to_encode["user_id"]

    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    验证JWT令牌

    Args:
        token: JWT令牌
        token_type: 令牌类型（access或refresh）

    Returns:
        解码后的令牌数据，如果验证失败则返回None
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        # 验证令牌类型
        if payload.get("type") != token_type:
            return None

        # 验证过期时间
        exp = payload.get("exp")
        if exp is None or datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(
            timezone.utc
        ):
            return None

        return payload
    except JWTError:
        return None


def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """
    从令牌中获取用户信息

    Args:
        token: JWT访问令牌

    Returns:
        用户信息字典，包含user_id和user_type
    """
    payload = verify_token(token, token_type="access")
    if payload is None:
        return None

    user_id = payload.get("user_id")
    user_type = payload.get("user_type")

    if user_id is None or user_type is None:
        return None

    return {"user_id": user_id, "user_type": user_type}
