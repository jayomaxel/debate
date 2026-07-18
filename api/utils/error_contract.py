from __future__ import annotations

import re
import uuid
from http import HTTPStatus
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from logging_config import get_logger


logger = get_logger(__name__)

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_PUBLIC_SERVER_ERROR_PATTERN = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9，。！？、（）()《》：: -]{1,48}$")
_SERVER_ERROR_MESSAGE = "服务器内部错误，请稍后重试"
_VALIDATION_ERROR_MESSAGE = "请求参数校验失败"
_GENERIC_OPERATION_ERROR_MESSAGE = "请求处理失败，请稍后重试"


def install_error_contract(app: FastAPI) -> None:
    """Install request id propagation and normalized JSON error responses."""

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = resolve_request_id(request)
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


def resolve_request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    if isinstance(existing, str) and _REQUEST_ID_PATTERN.fullmatch(existing):
        return existing

    upload_guard_id = getattr(request.state, "upload_guard_request_id", None)
    if isinstance(upload_guard_id, str) and _REQUEST_ID_PATTERN.fullmatch(upload_guard_id):
        request.state.request_id = upload_guard_id
        return upload_guard_id

    header_id = request.headers.get("x-request-id")
    if isinstance(header_id, str) and _REQUEST_ID_PATTERN.fullmatch(header_id):
        request.state.request_id = header_id
        return header_id

    request_id = f"req_{uuid.uuid4().hex}"
    request.state.request_id = request_id
    return request_id


def build_error_contract(
    *,
    code: int | str,
    message: str,
    request_id: str,
    detail: Any = None,
    data: Any = None,
    errors: Any = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }

    if detail is not None:
        payload["detail"] = detail
    if data is not None:
        payload["data"] = data
    if errors is not None:
        payload["errors"] = errors

    return payload


def public_exception_detail(exc: BaseException | object) -> str:
    """Return a client-safe message for values caught by broad ``except`` blocks.

    Router-level ``detail=str(exc)`` leaked driver, provider and filesystem
    diagnostics before the global exception handler could sanitize them. Keep a
    short, human-readable business message only when it passes the same public
    message policy; otherwise use a stable generic message that the frontend can
    render together with its request id.
    """

    message = str(exc or "").strip()
    return message if _is_public_server_error_message(message) else _GENERIC_OPERATION_ERROR_MESSAGE


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = resolve_request_id(request)
    status_code = int(exc.status_code)
    message, detail, data, errors = _normalize_http_detail(status_code, exc.detail)
    payload = build_error_contract(
        code=status_code,
        message=message,
        request_id=request_id,
        detail=detail,
        data=data,
        errors=errors,
    )
    headers = dict(getattr(exc, "headers", None) or {})
    headers["X-Request-Id"] = request_id
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
        headers=headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = resolve_request_id(request)
    errors = exc.errors()
    payload = build_error_contract(
        code=422,
        message=_VALIDATION_ERROR_MESSAGE,
        request_id=request_id,
        detail=errors,
        errors=errors,
    )
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(payload),
        headers={"X-Request-Id": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = resolve_request_id(request)
    logger.exception(
        "Unhandled API exception",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        },
    )
    payload = build_error_contract(
        code=500,
        message=_SERVER_ERROR_MESSAGE,
        request_id=request_id,
        detail=_SERVER_ERROR_MESSAGE,
    )
    return JSONResponse(
        status_code=500,
        content=jsonable_encoder(payload),
        headers={"X-Request-Id": request_id},
    )


def _normalize_http_detail(
    status_code: int,
    detail: Any,
) -> tuple[str, Any, Optional[Any], Optional[Any]]:
    if status_code >= 500:
        if _is_public_server_error_message(detail):
            message = str(detail)
            return message, message, None, None
        return _SERVER_ERROR_MESSAGE, _SERVER_ERROR_MESSAGE, None, None

    if isinstance(detail, dict):
        message = str(
            detail.get("message")
            or detail.get("detail")
            or _default_status_message(status_code)
        )
        data = detail.get("data")
        errors = detail.get("errors")
        return message, detail.get("detail", message), data, errors

    if detail is None:
        message = _default_status_message(status_code)
    elif isinstance(detail, str):
        message = detail
    else:
        message = str(detail)

    return message, detail if detail is not None else message, None, None


def _default_status_message(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP error"


def _is_public_server_error_message(detail: Any) -> bool:
    if not isinstance(detail, str):
        return False

    message = detail.strip()
    if not _PUBLIC_SERVER_ERROR_PATTERN.fullmatch(message):
        return False

    unsafe_markers = (
        "Exception",
        "Traceback",
        "File ",
        "SELECT ",
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "sqlite",
        "postgres",
        "password",
        "secret",
        "api_key",
        "token",
        "config",
        "connection",
        "timeout",
        "permission denied",
        "://",
    )
    lowered = message.lower()
    return not any(marker.lower() in lowered for marker in unsafe_markers)
