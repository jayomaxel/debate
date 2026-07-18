from __future__ import annotations

import math
import re
import socket
import time
from dataclasses import dataclass
from threading import RLock
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from database import get_redis
from services.audit_service import AuditService
from utils.security import is_token_session_valid, verify_token

RATE_LIMIT_TOTAL = Counter(
    "debate_rate_limit_total",
    "Total rate-limit decisions.",
    ("bucket", "result"),
)


@dataclass(frozen=True)
class RateLimitPolicy:
    bucket: str
    path_pattern: re.Pattern[str]
    methods: frozenset[str]
    limit: int
    window_seconds: int
    identity_strategy: str
    audit_event_type: str
    audit_target_type: str

    def matches(self, path: str, method: str) -> bool:
        return method.upper() in self.methods and bool(self.path_pattern.fullmatch(path))


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


RATE_LIMIT_POLICIES = (
    RateLimitPolicy(
        bucket="login",
        path_pattern=re.compile(r"^/api/auth/login$"),
        methods=frozenset({"POST"}),
        limit=10,
        window_seconds=60,
        identity_strategy="ip",
        audit_event_type="auth",
        audit_target_type="session",
    ),
    RateLimitPolicy(
        bucket="admin_kb_upload",
        path_pattern=re.compile(r"^/api/admin/kb/documents$"),
        methods=frozenset({"POST"}),
        limit=12,
        window_seconds=60,
        identity_strategy="user_or_ip",
        audit_event_type="upload",
        audit_target_type="knowledge_document",
    ),
    RateLimitPolicy(
        bucket="avatar_upload",
        path_pattern=re.compile(r"^/api/auth/profile/avatar/upload$"),
        methods=frozenset({"POST"}),
        limit=8,
        window_seconds=60,
        identity_strategy="user_or_ip",
        audit_event_type="upload",
        audit_target_type="profile_avatar",
    ),
    RateLimitPolicy(
        bucket="asr_upload",
        path_pattern=re.compile(r"^/api/voice/asr/transcribe$"),
        methods=frozenset({"POST"}),
        limit=15,
        window_seconds=60,
        identity_strategy="user_or_ip",
        audit_event_type="upload",
        audit_target_type="asr_audio",
    ),
    RateLimitPolicy(
        bucket="teacher_support_upload",
        path_pattern=re.compile(r"^/api/teacher/debates/[^/]+/support-documents$"),
        methods=frozenset({"POST"}),
        limit=10,
        window_seconds=60,
        identity_strategy="user_or_ip",
        audit_event_type="upload",
        audit_target_type="support_document",
    ),
    RateLimitPolicy(
        bucket="report_regeneration",
        path_pattern=re.compile(
            r"^(?:/api/.*/reports/[^/]+(?:/(?:export/(?:pdf|excel)|send-email))?|/api/teacher/debates/[^/]+/report/(?:recalculate|job/retry))$"
        ),
        methods=frozenset({"GET", "POST", "PUT"}),
        limit=6,
        window_seconds=60,
        identity_strategy="user_or_ip",
        audit_event_type="report_regeneration",
        audit_target_type="report",
    ),
    RateLimitPolicy(
        bucket="candidate_topic_generation",
        path_pattern=re.compile(
            r"^(?:/api/(?:teacher|student|admin)/(?:candidate-topics|topic-candidates|topics/(?:candidates|generate)|debate-topics/(?:candidates|generate))|/api/teacher/classes/[^/]+/topic-recommendations)$"
        ),
        methods=frozenset({"POST"}),
        limit=8,
        window_seconds=60,
        identity_strategy="user_or_ip",
        audit_event_type="topic_generation",
        audit_target_type="candidate_topic",
    ),
)

_memory_rate_limits: dict[str, tuple[int, float]] = {}
_memory_lock = RLock()
_redis_rate_limit_disabled = False


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        policy = resolve_rate_limit_policy(request.url.path, request.method)
        if policy is None:
            return await call_next(request)

        identity = _resolve_identity(request, policy.identity_strategy)
        decision = _check_rate_limit(policy, identity)

        if not decision.allowed:
            RATE_LIMIT_TOTAL.labels(bucket=policy.bucket, result="denied").inc()
            AuditService.record_event(
                event_type=policy.audit_event_type,
                actor_id=identity,
                actor_role="system",
                target_type=policy.audit_target_type,
                target_id=request.url.path,
                result="denied",
                metadata={
                    "action": "rate_limited",
                    "bucket": policy.bucket,
                    "retry_after_seconds": decision.retry_after_seconds,
                    "path": request.url.path,
                },
            )
            return _rate_limit_response(policy, decision)

        RATE_LIMIT_TOTAL.labels(bucket=policy.bucket, result="allowed").inc()
        response = await call_next(request)
        _apply_rate_limit_headers(response, decision)
        return response


def resolve_rate_limit_policy(path: str, method: str) -> Optional[RateLimitPolicy]:
    for policy in RATE_LIMIT_POLICIES:
        if policy.matches(path, method):
            return policy
    return None


def reset_rate_limit_state() -> None:
    with _memory_lock:
        _memory_rate_limits.clear()


def _check_rate_limit(policy: RateLimitPolicy, identity: str) -> RateLimitDecision:
    now = time.time()
    window_id = math.floor(now / policy.window_seconds)
    retry_after = max(1, policy.window_seconds - int(now % policy.window_seconds))
    counter_key = f"rate_limit:{policy.bucket}:{identity}:{window_id}"

    redis_client = _get_redis_client()
    if redis_client is not None:
        try:
            pipeline = redis_client.pipeline()
            pipeline.incr(counter_key)
            pipeline.expire(counter_key, policy.window_seconds + 1)
            current_count, _ = pipeline.execute()
            current_count = int(current_count or 0)
            remaining = max(0, policy.limit - current_count)
            return RateLimitDecision(
                allowed=current_count <= policy.limit,
                limit=policy.limit,
                remaining=remaining,
                retry_after_seconds=retry_after,
            )
        except Exception:
            _disable_redis_rate_limit_backend()
            pass

    with _memory_lock:
        current_count, expires_at = _memory_rate_limits.get(counter_key, (0, now + retry_after))
        if expires_at <= now:
            current_count = 0
            expires_at = now + retry_after
        current_count += 1
        _memory_rate_limits[counter_key] = (current_count, expires_at)

    remaining = max(0, policy.limit - current_count)
    return RateLimitDecision(
        allowed=current_count <= policy.limit,
        limit=policy.limit,
        remaining=remaining,
        retry_after_seconds=max(1, int(expires_at - now)),
    )


def _rate_limit_response(policy: RateLimitPolicy, decision: RateLimitDecision) -> JSONResponse:
    response = JSONResponse(
        status_code=429,
        content={
            "code": 429,
            "message": "Too many requests",
            "data": {
                "bucket": policy.bucket,
                "retry_after_seconds": decision.retry_after_seconds,
            },
        },
    )
    _apply_rate_limit_headers(response, decision)
    return response


def _apply_rate_limit_headers(response, decision: RateLimitDecision) -> None:
    response.headers["Retry-After"] = str(decision.retry_after_seconds)
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)


def _resolve_identity(request: Request, strategy: str) -> str:
    ip = _resolve_client_ip(request)
    if strategy == "ip":
        return f"ip:{ip}"

    auth_header = str(request.headers.get("authorization") or "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        payload = verify_token(token)
        if payload and is_token_session_valid(payload):
            user_id = str(payload.get("sub") or payload.get("user_id") or "").strip()
            if user_id:
                return f"user:{user_id}"

    return f"ip:{ip}"


def _resolve_client_ip(request: Request) -> str:
    forwarded_for = str(request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return str(request.client.host)
    return "unknown"


def _get_redis_client():
    if _redis_rate_limit_disabled:
        return None
    try:
        with socket.create_connection(
            (settings.REDIS_HOST, int(settings.REDIS_PORT)),
            timeout=0.5,
        ):
            pass
    except OSError:
        _disable_redis_rate_limit_backend()
        return None
    try:
        return get_redis()
    except Exception:
        _disable_redis_rate_limit_backend()
        return None


def _disable_redis_rate_limit_backend() -> None:
    global _redis_rate_limit_disabled
    _redis_rate_limit_disabled = True
