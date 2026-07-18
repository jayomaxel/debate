"""Helpers for stable operational API responses."""

import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from schemas.operations import OperationalErrorCode, OperationalErrorContract


def request_id_from(request: Request) -> str:
    return (
        str(request.headers.get("x-request-id") or "").strip()
        or str(getattr(request.state, "request_id", "") or "").strip()
        or f"req_{uuid.uuid4().hex}"
    )


def operational_error_response(
    request: Request,
    *,
    code: OperationalErrorCode,
    message: str,
    status_code: int,
    retryable: bool,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = request_id_from(request)
    payload = OperationalErrorContract(
        code=code,
        message=message,
        request_id=request_id,
        retryable=retryable,
        details=details or {},
    ).model_dump(mode="json")
    response = JSONResponse(status_code=status_code, content=payload)
    response.headers["X-Request-Id"] = request_id
    return response

