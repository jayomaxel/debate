"""
安全工具函数：密码加密、JWT令牌管理
"""

import json
import logging
import socket
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Dict, Optional
import uuid

from passlib.context import CryptContext
from jose import JWTError, jwt

from config import settings

# 密码加密上下文 - 配置为与bcrypt 4.x兼容
pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12  # 明确指定bcrypt轮数
)
logger = logging.getLogger(__name__)

_memory_session_store: Dict[str, Dict[str, Any]] = {}
_memory_user_session_index: Dict[str, set[str]] = {}
_memory_session_lock = RLock()
_memory_ws_ticket_store: Dict[str, Dict[str, Any]] = {}
_memory_ws_ticket_lock = RLock()
_memory_legacy_token_revocations: Dict[str, str] = {}
_memory_legacy_token_lock = RLock()
_session_redis_disabled = False
_session_redis_lock = RLock()


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

    issued_at = datetime.now(timezone.utc)
    to_encode.setdefault("jti", str(uuid.uuid4()))
    to_encode.update({"exp": expire, "iat": issued_at, "type": "access"})
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
    issued_at = datetime.now(timezone.utc)
    to_encode.setdefault("jti", str(uuid.uuid4()))
    to_encode.update({"exp": expire, "iat": issued_at, "type": "refresh"})
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _session_ttl_seconds() -> int:
    return int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)


def _ws_ticket_ttl_seconds() -> int:
    return 5 * 60


def _session_key(session_id: str) -> str:
    return f"auth:session:{session_id}"


def _user_sessions_key(user_id: str) -> str:
    return f"auth:user_sessions:{user_id}"


def _ws_ticket_key(ticket: str) -> str:
    return f"auth:ws_ticket:{ticket}"


def _legacy_access_revocation_key(user_id: str) -> str:
    return f"auth:legacy_access_revoked_at:{user_id}"


def _serialize_session_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _deserialize_session_payload(raw: str) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _build_session_payload(
    *,
    session_id: str,
    user_id: str,
    user_type: str,
    requires_reauth: bool = False,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    now = _utcnow()
    expires_at = now + timedelta(seconds=_session_ttl_seconds())
    return {
        "session_id": session_id,
        "user_id": user_id,
        "user_type": user_type,
        "requires_reauth": bool(requires_reauth),
        "created_at": created_at or now.isoformat(),
        "updated_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


def _is_session_expired(payload: Dict[str, Any]) -> bool:
    raw_expires_at = payload.get("expires_at")
    if not isinstance(raw_expires_at, str) or not raw_expires_at.strip():
        return True
    expires_at = _coerce_datetime(raw_expires_at)
    if expires_at is None:
        return True
    return expires_at <= _utcnow()


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _persist_memory_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    session_id = str(payload["session_id"])
    user_id = str(payload["user_id"])
    with _memory_session_lock:
        _memory_session_store[session_id] = dict(payload)
        _memory_user_session_index.setdefault(user_id, set()).add(session_id)
    return dict(payload)


def _load_memory_session(session_id: str) -> Optional[Dict[str, Any]]:
    normalized_session_id = str(session_id)
    with _memory_session_lock:
        payload = _memory_session_store.get(normalized_session_id)
        if payload is None:
            return None
        payload_copy = dict(payload)
    if _is_session_expired(payload_copy):
        revoke_server_session(normalized_session_id)
        return None
    return payload_copy


def _delete_memory_session(session_id: str) -> bool:
    normalized_session_id = str(session_id)
    removed = False
    with _memory_session_lock:
        payload = _memory_session_store.pop(normalized_session_id, None)
        if payload is not None:
            removed = True
            user_id = str(payload.get("user_id") or "")
            session_ids = _memory_user_session_index.get(user_id)
            if session_ids is not None:
                session_ids.discard(normalized_session_id)
                if not session_ids:
                    _memory_user_session_index.pop(user_id, None)
    return removed


def _list_memory_user_sessions(user_id: str) -> set[str]:
    normalized_user_id = str(user_id)
    with _memory_session_lock:
        return set(_memory_user_session_index.get(normalized_user_id, set()))


def _persist_memory_ws_ticket(payload: Dict[str, Any]) -> Dict[str, Any]:
    ticket = str(payload["ticket"])
    with _memory_ws_ticket_lock:
        _memory_ws_ticket_store[ticket] = dict(payload)
    return dict(payload)


def _load_memory_ws_ticket(ticket: str) -> Optional[Dict[str, Any]]:
    normalized_ticket = str(ticket or "").strip()
    with _memory_ws_ticket_lock:
        payload = _memory_ws_ticket_store.get(normalized_ticket)
        if payload is None:
            return None
        payload_copy = dict(payload)
    if _is_session_expired(payload_copy):
        revoke_ws_ticket(normalized_ticket)
        return None
    return payload_copy


def _delete_memory_ws_ticket(ticket: str) -> bool:
    normalized_ticket = str(ticket or "").strip()
    with _memory_ws_ticket_lock:
        return _memory_ws_ticket_store.pop(normalized_ticket, None) is not None


def _set_memory_legacy_access_revocation(user_id: str, revoked_at: datetime) -> str:
    normalized_user_id = str(user_id or "").strip()
    normalized_revoked_at = revoked_at.astimezone(timezone.utc).isoformat()
    with _memory_legacy_token_lock:
        existing = _memory_legacy_token_revocations.get(normalized_user_id)
        existing_dt = _coerce_datetime(existing)
        if existing_dt is not None and existing_dt >= revoked_at:
            return existing
        _memory_legacy_token_revocations[normalized_user_id] = normalized_revoked_at
    return normalized_revoked_at


def _get_memory_legacy_access_revocation(user_id: str) -> Optional[datetime]:
    normalized_user_id = str(user_id or "").strip()
    with _memory_legacy_token_lock:
        raw = _memory_legacy_token_revocations.get(normalized_user_id)
    return _coerce_datetime(raw)


def _get_redis_session_client():
    global _session_redis_disabled
    with _session_redis_lock:
        if _session_redis_disabled:
            return None
    try:
        with socket.create_connection(
            (settings.REDIS_HOST, int(settings.REDIS_PORT)),
            timeout=0.5,
        ):
            pass
    except OSError:
        _disable_redis_session_backend("socket preflight failed")
        return None
    try:
        from database import get_redis

        return get_redis()
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("Failed to resolve Redis session client: %s", exc)
        return None


def _disable_redis_session_backend(reason: str) -> None:
    global _session_redis_disabled
    with _session_redis_lock:
        if _session_redis_disabled:
            return
        _session_redis_disabled = True
    logger.warning("Redis session backend disabled for current process: %s", reason)


def persist_server_session(
    *,
    session_id: str,
    user_id: str,
    user_type: str,
    requires_reauth: bool = False,
) -> Dict[str, Any]:
    existing_session = get_server_session(session_id)
    payload = _build_session_payload(
        session_id=str(session_id),
        user_id=str(user_id),
        user_type=str(user_type),
        requires_reauth=requires_reauth,
        created_at=(existing_session or {}).get("created_at"),
    )
    redis_client = _get_redis_session_client()
    if redis_client is not None:
        try:
            ttl = _session_ttl_seconds()
            pipeline = redis_client.pipeline()
            pipeline.setex(_session_key(str(session_id)), ttl, _serialize_session_payload(payload))
            pipeline.sadd(_user_sessions_key(str(user_id)), str(session_id))
            pipeline.expire(_user_sessions_key(str(user_id)), ttl)
            pipeline.execute()
            _persist_memory_session(payload)
            return dict(payload)
        except Exception as exc:  # pragma: no cover - depends on runtime services
            _disable_redis_session_backend(f"persist failed: {exc}")
    return _persist_memory_session(payload)


def get_server_session(session_id: str) -> Optional[Dict[str, Any]]:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return None

    redis_client = _get_redis_session_client()
    if redis_client is not None:
        try:
            raw_payload = redis_client.get(_session_key(normalized_session_id))
            if raw_payload:
                payload = _deserialize_session_payload(raw_payload)
                if payload is None:
                    return None
                if _is_session_expired(payload):
                    revoke_server_session(normalized_session_id)
                    return None
                _persist_memory_session(payload)
                return payload
        except Exception as exc:  # pragma: no cover - depends on runtime services
            _disable_redis_session_backend(f"read failed: {exc}")

    return _load_memory_session(normalized_session_id)


def is_server_session_active(session_id: str, user_id: Optional[str] = None) -> bool:
    payload = get_server_session(session_id)
    if payload is None:
        return False
    if user_id is not None and str(payload.get("user_id")) != str(user_id):
        return False
    return not bool(payload.get("requires_reauth"))


def revoke_server_session(session_id: str) -> bool:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return False

    removed = _delete_memory_session(normalized_session_id)
    redis_client = _get_redis_session_client()
    if redis_client is not None:
        try:
            raw_payload = redis_client.get(_session_key(normalized_session_id))
            payload = _deserialize_session_payload(raw_payload) if raw_payload else None
            user_id = str((payload or {}).get("user_id") or "")
            pipeline = redis_client.pipeline()
            pipeline.delete(_session_key(normalized_session_id))
            if user_id:
                pipeline.srem(_user_sessions_key(user_id), normalized_session_id)
            pipeline.execute()
            return removed or raw_payload is not None
        except Exception as exc:  # pragma: no cover - depends on runtime services
            _disable_redis_session_backend(f"revoke failed: {exc}")
    return removed


def revoke_all_server_sessions(user_id: str) -> int:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return 0

    session_ids = _list_memory_user_sessions(normalized_user_id)
    redis_client = _get_redis_session_client()
    if redis_client is not None:
        try:
            session_ids.update(redis_client.smembers(_user_sessions_key(normalized_user_id)) or set())
        except Exception as exc:  # pragma: no cover - depends on runtime services
            _disable_redis_session_backend(f"user session index read failed: {exc}")

    revoked_count = 0
    for session_id in session_ids:
        if revoke_server_session(session_id):
            revoked_count += 1

    if redis_client is not None:
        try:
            redis_client.delete(_user_sessions_key(normalized_user_id))
        except Exception as exc:  # pragma: no cover - depends on runtime services
            _disable_redis_session_backend(f"user session cleanup failed: {exc}")

    with _memory_session_lock:
        _memory_user_session_index.pop(normalized_user_id, None)

    return revoked_count


def persist_ws_ticket(
    *,
    ticket: str,
    room_id: str,
    user_id: str,
    user_type: str,
    session_id: Optional[str] = None,
    auth_iat: Optional[Any] = None,
    expires_at: Optional[datetime] = None,
    single_use: bool = True,
) -> Dict[str, Any]:
    normalized_expires_at = expires_at or (_utcnow() + timedelta(seconds=_ws_ticket_ttl_seconds()))
    payload = {
        "ticket": str(ticket),
        "room_id": str(room_id),
        "user_id": str(user_id),
        "user_type": str(user_type),
        "session_id": str(session_id or "").strip() or None,
        "auth_iat": auth_iat,
        "single_use": bool(single_use),
        "created_at": _utcnow().isoformat(),
        "expires_at": normalized_expires_at.astimezone(timezone.utc).isoformat(),
    }
    redis_client = _get_redis_session_client()
    if redis_client is not None:
        try:
            ttl = max(1, int((normalized_expires_at.astimezone(timezone.utc) - _utcnow()).total_seconds()))
            redis_client.setex(
                _ws_ticket_key(str(ticket)),
                ttl,
                _serialize_session_payload(payload),
            )
            _persist_memory_ws_ticket(payload)
            return dict(payload)
        except Exception as exc:  # pragma: no cover - depends on runtime services
            _disable_redis_session_backend(f"ws ticket persist failed: {exc}")
    return _persist_memory_ws_ticket(payload)


def get_ws_ticket(ticket: str) -> Optional[Dict[str, Any]]:
    normalized_ticket = str(ticket or "").strip()
    if not normalized_ticket:
        return None

    redis_client = _get_redis_session_client()
    if redis_client is not None:
        try:
            raw_payload = redis_client.get(_ws_ticket_key(normalized_ticket))
            if raw_payload:
                payload = _deserialize_session_payload(raw_payload)
                if payload is None:
                    return None
                if _is_session_expired(payload):
                    revoke_ws_ticket(normalized_ticket)
                    return None
                _persist_memory_ws_ticket(payload)
                return payload
        except Exception as exc:  # pragma: no cover - depends on runtime services
            _disable_redis_session_backend(f"ws ticket read failed: {exc}")

    return _load_memory_ws_ticket(normalized_ticket)


def revoke_ws_ticket(ticket: str) -> bool:
    normalized_ticket = str(ticket or "").strip()
    if not normalized_ticket:
        return False

    removed = _delete_memory_ws_ticket(normalized_ticket)
    redis_client = _get_redis_session_client()
    if redis_client is not None:
        try:
            deleted = redis_client.delete(_ws_ticket_key(normalized_ticket))
            return removed or bool(deleted)
        except Exception as exc:  # pragma: no cover - depends on runtime services
            _disable_redis_session_backend(f"ws ticket revoke failed: {exc}")
    return removed


def revoke_legacy_access_tokens(
    user_id: str,
    *,
    revoked_at: Optional[datetime] = None,
) -> Optional[datetime]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return None

    normalized_revoked_at = (revoked_at or _utcnow()).astimezone(timezone.utc)
    stored_iso = _set_memory_legacy_access_revocation(
        normalized_user_id,
        normalized_revoked_at,
    )
    redis_client = _get_redis_session_client()
    if redis_client is not None:
        try:
            redis_client.set(
                _legacy_access_revocation_key(normalized_user_id),
                stored_iso,
            )
        except Exception as exc:  # pragma: no cover - depends on runtime services
            _disable_redis_session_backend(f"legacy token revoke failed: {exc}")
    return _coerce_datetime(stored_iso)


def get_legacy_access_revoked_at(user_id: str) -> Optional[datetime]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return None

    redis_client = _get_redis_session_client()
    if redis_client is not None:
        try:
            raw_value = redis_client.get(_legacy_access_revocation_key(normalized_user_id))
            revoked_at = _coerce_datetime(raw_value)
            if revoked_at is not None:
                _set_memory_legacy_access_revocation(normalized_user_id, revoked_at)
                return revoked_at
        except Exception as exc:  # pragma: no cover - depends on runtime services
            _disable_redis_session_backend(f"legacy token read failed: {exc}")

    return _get_memory_legacy_access_revocation(normalized_user_id)


def is_legacy_access_token_valid(user_id: str, payload: Dict[str, Any]) -> bool:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return False

    revoked_at = get_legacy_access_revoked_at(normalized_user_id)
    if revoked_at is None:
        return True

    token_iat = _coerce_datetime(payload.get("iat"))
    if token_iat is None:
        return False
    return token_iat > revoked_at


def consume_ws_ticket(ticket: str, *, room_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    payload = get_ws_ticket(ticket)
    if payload is None:
        return None

    if room_id is not None and str(payload.get("room_id")) != str(room_id):
        return None

    user_id = str(payload.get("user_id") or "").strip()
    session_id = str(payload.get("session_id") or "").strip()
    if session_id:
        if not is_server_session_active(session_id, user_id=user_id):
            revoke_ws_ticket(ticket)
            return None
    elif not is_legacy_access_token_valid(user_id, payload):
        revoke_ws_ticket(ticket)
        return None

    if bool(payload.get("single_use", True)):
        revoke_ws_ticket(ticket)
    return payload


def is_token_session_valid(payload: Dict[str, Any]) -> bool:
    session_id = str(payload.get("session_id") or "").strip()
    user_id = str(payload.get("sub") or payload.get("user_id") or "").strip()
    if not user_id:
        return False
    if not session_id:
        return is_legacy_access_token_valid(user_id, payload)
    return is_server_session_active(session_id, user_id=user_id)


def normalize_contract_role(user_type: str) -> str:
    """Normalize internal user types to the frozen auth contract roles."""
    normalized = str(user_type or "").strip().lower()
    if normalized == "administrator":
        return "admin"
    if normalized in {"teacher", "student", "admin"}:
        return normalized
    return "student"


def build_auth_session_contract(
    *,
    access_token: str,
    access_token_expires_in: int,
    session_id: str,
    user_id: str,
    username: str,
    role: str,
    refresh_strategy: str = "server_session",
    requires_reauth: bool = False,
) -> Dict[str, Any]:
    """Build the frozen auth session payload used by package C."""
    return {
        "access_token": access_token,
        "access_token_expires_in": int(access_token_expires_in),
        "session_id": session_id,
        "user": {
            "id": user_id,
            "username": username,
            "role": normalize_contract_role(role),
        },
        "refresh_strategy": refresh_strategy,
        "requires_reauth": bool(requires_reauth),
    }


def build_ws_ticket_contract(
    *,
    room_id: str,
    ticket: str,
    expires_at: datetime,
    connection_url: str,
) -> Dict[str, Any]:
    """Build the frozen websocket ticket payload."""
    return {
        "ticket": ticket,
        "room_id": room_id,
        "expires_at": expires_at,
        "connection_url": connection_url,
    }
