from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter
from starlette.middleware.base import BaseHTTPMiddleware

from services.audit_service import AuditService
from utils.security import (
    build_upload_guard_error_contract,
    is_token_session_valid,
    verify_token,
)
from utils.upload_security import (
    UploadPart,
    is_multipart_request,
    parse_multipart_upload_parts,
    resolve_upload_policy,
    validate_upload_part,
)

UPLOAD_GUARD_TOTAL = Counter(
    "debate_upload_guard_total",
    "Total upload guard decisions.",
    ("policy", "result", "code"),
)


class UploadGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        policy = resolve_upload_policy(request.url.path, request.method)
        if policy is None:
            return await call_next(request)

        content_type = request.headers.get("content-type", "")
        if not is_multipart_request(content_type):
            return await call_next(request)

        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex}"

        try:
            body = await request.body()
            parts = parse_multipart_upload_parts(content_type, body)
        except Exception:
            UPLOAD_GUARD_TOTAL.labels(
                policy=policy.name,
                result="failed",
                code="scan_failed",
            ).inc()
            self._record_audit(
                request=request,
                policy_name=policy.name,
                target_type=policy.target_type,
                result="failed",
                target_id=request.url.path,
                metadata={
                    "action": "upload_guard_scan_failed",
                    "path": request.url.path,
                    "request_id": request_id,
                },
            )
            return self._error_response(
                code="scan_failed",
                message="Failed to inspect uploaded file.",
                request_id=request_id,
                status_code=400,
            )

        if not parts:
            return await call_next(request)

        for part in parts:
            validation_error = validate_upload_part(policy, part)
            if validation_error is None:
                continue

            code, message = validation_error
            UPLOAD_GUARD_TOTAL.labels(
                policy=policy.name,
                result="denied",
                code=code,
            ).inc()
            self._record_audit(
                request=request,
                policy_name=policy.name,
                target_type=policy.target_type,
                result="denied",
                target_id=part.filename,
                metadata={
                    "action": "upload_guard_blocked",
                    "path": request.url.path,
                    "filename": part.filename,
                    "content_type": part.content_type,
                    "size": part.size,
                    "request_id": request_id,
                    "reason": code,
                },
            )
            return self._error_response(
                code=code,
                message=message,
                request_id=request_id,
                status_code=400,
            )

        first_part = parts[0]
        UPLOAD_GUARD_TOTAL.labels(
            policy=policy.name,
            result="success",
            code="ok",
        ).inc()
        self._record_audit(
            request=request,
            policy_name=policy.name,
            target_type=policy.target_type,
            result="success",
            target_id=first_part.filename,
            metadata={
                "action": "upload_guard_passed",
                "path": request.url.path,
                "filename": first_part.filename,
                "content_type": first_part.content_type,
                "size": first_part.size,
                "request_id": request_id,
                "file_count": len(parts),
            },
        )
        request.state.upload_guard_request_id = request_id
        request.state.upload_guard_policy = policy.name
        return await call_next(request)

    @staticmethod
    def _error_response(*, code: str, message: str, request_id: str, status_code: int):
        payload = build_upload_guard_error_contract(
            code=code,
            message=message,
            request_id=request_id,
        )
        response = JSONResponse(status_code=status_code, content=payload)
        response.headers["X-Request-Id"] = request_id
        return response

    @staticmethod
    def _record_audit(
        *,
        request: Request,
        policy_name: str,
        target_type: str,
        result: str,
        target_id: str,
        metadata: dict,
    ) -> None:
        actor_id, actor_role = _resolve_request_actor(request)
        AuditService.record_event(
            event_type="upload",
            actor_id=actor_id,
            actor_role=actor_role,
            target_type=target_type,
            target_id=target_id,
            result=result,
            metadata={**metadata, "policy": policy_name},
        )


def _resolve_request_actor(request: Request) -> tuple[str, str]:
    auth_header = str(request.headers.get("authorization") or "")
    if not auth_header.lower().startswith("bearer "):
        return "system", "system"

    token = auth_header.split(" ", 1)[1].strip()
    payload = verify_token(token)
    if not payload or not is_token_session_valid(payload):
        return "system", "system"

    actor_id = str(payload.get("sub") or payload.get("user_id") or "system")
    actor_role = str(payload.get("user_type") or payload.get("role") or "system")
    return actor_id, actor_role
