#!/usr/bin/env python3
"""Prepare a complete local debate room without five manual browser logins.

The script uses the same public HTTP and WebSocket contracts as the web app:

1. create/reuse an isolated teacher, class, and four students;
2. log in as the teacher and publish a debate with deterministic roles;
3. log in as every student and validate joining by invitation code;
4. optionally connect all students, complete their checklists, and keep them online.

Examples (run from the repository root):

    python scripts/auto_prepare_debate.py
    python scripts/auto_prepare_debate.py --auto-ready --keep-open
    python scripts/auto_prepare_debate.py --visual
    python scripts/auto_prepare_debate.py --interactive
    python scripts/auto_prepare_debate.py --interactive-ready-only \
        --existing-debate-id <id> --existing-invitation-code <code>

The default credentials are intentionally restricted to loopback URLs. Use
explicit environment variables and --allow-remote only in a disposable test
environment.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

DEFAULT_BASE_URL = "http://localhost:8860"
DEFAULT_TEACHER_ACCOUNT = "auto_flow_teacher"
DEFAULT_TEACHER_PASSWORD = "FlowAuto@2026"
DEFAULT_STUDENT_PASSWORD = "FlowAuto@2026"
DEFAULT_CLASS_NAME = "自动化全流程测试班"
DEFAULT_STUDENTS = (
    ("auto_flow_student1", "自动流程学生一", "AUTO-FLOW-001", "debater_1"),
    ("auto_flow_student2", "自动流程学生二", "AUTO-FLOW-002", "debater_2"),
    ("auto_flow_student3", "自动流程学生三", "AUTO-FLOW-003", "debater_3"),
    ("auto_flow_student4", "自动流程学生四", "AUTO-FLOW-004", "debater_4"),
)
LOGIC_TEST_STUDENTS = (
    ("logic_test_student1", "逻辑测试学生一", "LOGIC-TEST-001", "debater_1"),
    ("logic_test_student2", "逻辑测试学生二", "LOGIC-TEST-002", "debater_2"),
    ("logic_test_student3", "逻辑测试学生三", "LOGIC-TEST-003", "debater_3"),
    ("logic_test_student4", "逻辑测试学生四", "LOGIC-TEST-004", "debater_4"),
)


class AutomationError(RuntimeError):
    """Raised when an API contract or automation precondition fails."""


@dataclass(frozen=True)
class Session:
    account: str
    user_type: str
    access_token: str
    user: dict[str, Any]
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_in: int | None = None


def _unwrap(payload: Any) -> Any:
    if (
        isinstance(payload, dict)
        and "data" in payload
        and ("code" in payload or "message" in payload)
    ):
        return payload["data"]
    return payload


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message") or payload
        if isinstance(detail, (dict, list)):
            return json.dumps(detail, ensure_ascii=False)
        return str(detail)
    return str(payload)


def _request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    token: str | None = None,
    expected: tuple[int, ...] = (200,),
    **kwargs: Any,
) -> Any:
    headers = dict(kwargs.pop("headers", {}) or {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = client.request(method, path, headers=headers, **kwargs)
    if response.status_code not in expected:
        raise AutomationError(
            f"{method.upper()} {path} failed: HTTP {response.status_code}: "
            f"{_response_detail(response)}"
        )
    if not response.content:
        return None
    return _unwrap(response.json())


def _find_edge(executable: str | None = None) -> Path:
    if executable:
        candidate = Path(executable).expanduser()
        if candidate.is_file():
            return candidate
        raise AutomationError(f"Edge executable does not exist: {candidate}")

    candidates: list[Path] = []
    for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        root = os.getenv(env_name)
        if root:
            candidates.append(
                Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise AutomationError(
        "Microsoft Edge was not found. Pass its path with --edge-path."
    )


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_edge_page(
    port: int, process: subprocess.Popen[Any], timeout: float = 15.0
) -> str:
    deadline = time.monotonic() + timeout
    last_error = "Edge DevTools endpoint was not ready"
    with httpx.Client(timeout=1.0, trust_env=False) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise AutomationError(
                    f"Edge exited before its test window opened (code={process.returncode})"
                )
            try:
                response = client.get(f"http://127.0.0.1:{port}/json/list")
                response.raise_for_status()
                targets = response.json()
                for target in targets:
                    if target.get("type") == "page" and target.get(
                        "webSocketDebuggerUrl"
                    ):
                        return str(target["webSocketDebuggerUrl"])
            except (httpx.HTTPError, ValueError) as exc:
                last_error = str(exc)
            time.sleep(0.1)
    raise AutomationError(f"Could not connect to the Edge test window: {last_error}")


async def _inject_browser_session(
    debugger_url: str,
    session: Session,
    arena_url: str,
    window_label: str,
) -> None:
    session_values = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": session.token_type,
    }
    if session.expires_in:
        session_values["token_expires_at"] = str(
            int(time.time() * 1000) + session.expires_in * 1000
        )
    local_values = {
        "user_info": json.dumps(session.user, ensure_ascii=False, separators=(",", ":"))
    }
    injection = (
        "(() => {"
        f"const sessionValues={json.dumps(session_values, ensure_ascii=False)};"
        f"const localValues={json.dumps(local_values, ensure_ascii=False)};"
        "for(const [key,value] of Object.entries(sessionValues)){"
        "sessionStorage.setItem(key,String(value));}"
        "for(const [key,value] of Object.entries(localValues)){"
        "localStorage.setItem(key,String(value));}"
        "})();"
    )

    next_id = 0
    async with websockets.connect(
        debugger_url, open_timeout=10, ping_interval=None, max_size=8 * 1024 * 1024
    ) as socket_connection:

        async def command(method: str, params: dict[str, Any] | None = None) -> Any:
            nonlocal next_id
            next_id += 1
            command_id = next_id
            await socket_connection.send(
                json.dumps({"id": command_id, "method": method, "params": params or {}})
            )
            while True:
                message = json.loads(
                    await asyncio.wait_for(socket_connection.recv(), timeout=15)
                )
                if message.get("id") != command_id:
                    continue
                if message.get("error"):
                    raise AutomationError(
                        f"Edge session injection failed at {method}: {message['error']}"
                    )
                return message.get("result") or {}

        await command("Page.enable")
        await command("Page.addScriptToEvaluateOnNewDocument", {"source": injection})
        navigation = await command("Page.navigate", {"url": arena_url})
        if navigation.get("errorText"):
            raise AutomationError(
                f"Edge could not open {window_label}: {navigation['errorText']}"
            )
        await command("Page.bringToFront")

        deadline = asyncio.get_running_loop().time() + 15
        page_state: dict[str, Any] = {}
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.2)
            result = await command(
                "Runtime.evaluate",
                {
                    "expression": (
                        "({href:location.href,title:document.title,"
                        "ready:document.readyState})"
                    ),
                    "returnByValue": True,
                },
            )
            page_state = result.get("result", {}).get("value", {})
            if (
                page_state.get("href") == arena_url
                and page_state.get("ready") == "complete"
            ):
                break
        if page_state.get("href") != arena_url:
            raise AutomationError(
                f"{window_label} was redirected instead of entering the arena: "
                f"{page_state.get('href') or 'unknown URL'}"
            )
        await command(
            "Runtime.evaluate",
            {"expression": f"document.title={json.dumps(window_label, ensure_ascii=False)}"},
        )


def _open_authenticated_browser(
    session: Session,
    arena_url: str,
    edge_path: str | None,
    window_label: str,
    window_index: int = 0,
) -> None:
    executable = _find_edge(edge_path)
    port = _free_loopback_port()
    profile_dir = tempfile.mkdtemp(prefix=f"debate-{session.user_type}-edge-")
    offset = 36 * max(0, window_index)
    process = subprocess.Popen(
        [
            str(executable),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=msEdgeFirstRunExperience",
            f"--window-position={offset},{offset}",
            "--window-size=1180,820",
            "--new-window",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        debugger_url = _wait_for_edge_page(port, process)
        asyncio.run(
            _inject_browser_session(
                debugger_url,
                session,
                arena_url,
                window_label,
            )
        )
    except Exception:
        process.terminate()
        raise
    print(f"[OK] {window_label} signed in and opened: {arena_url}")


def _try_login(
    client: httpx.Client, account: str, password: str, user_type: str
) -> Session | None:
    response = client.post(
        "/api/auth/login",
        json={"account": account, "password": password, "user_type": user_type},
    )
    if response.status_code == 401:
        return None
    if response.status_code != 200:
        raise AutomationError(
            f"Login failed for {account}: HTTP {response.status_code}: "
            f"{_response_detail(response)}"
        )
    payload = _unwrap(response.json())
    token = str(payload.get("access_token") or "")
    user = payload.get("user") or {}
    if not token or not user.get("id"):
        raise AutomationError(f"Login response for {account} is missing token/user id")
    expires_in: int | None = None
    try:
        if payload.get("expires_in") is not None:
            expires_in = int(payload["expires_in"])
    except (TypeError, ValueError):
        pass
    return Session(
        account=account,
        user_type=user_type,
        access_token=token,
        user=user,
        refresh_token=str(payload.get("refresh_token") or ""),
        token_type=str(payload.get("token_type") or "bearer"),
        expires_in=expires_in,
    )


def _ensure_teacher(client: httpx.Client, account: str, password: str) -> Session:
    session = _try_login(client, account, password, "teacher")
    if session:
        print(f"[OK] Reused teacher: {account}")
        return session

    response = client.post(
        "/api/auth/register/teacher",
        json={
            "account": account,
            "email": f"{account}@example.com",
            "phone": "13800008888",
            "password": password,
            "name": "自动流程测试教师",
        },
    )
    if response.status_code != 200:
        raise AutomationError(
            f"Teacher {account!r} cannot log in and cannot be registered. "
            "The account may already exist with another password. "
            f"Registration response: HTTP {response.status_code}: "
            f"{_response_detail(response)}"
        )
    session = _try_login(client, account, password, "teacher")
    if not session:
        raise AutomationError(
            f"Teacher {account!r} was registered but login still failed"
        )
    print(f"[OK] Registered teacher: {account}")
    return session


def _ensure_class(
    client: httpx.Client, teacher: Session, class_name: str
) -> dict[str, Any]:
    classes = _request(
        client, "GET", "/api/teacher/classes", token=teacher.access_token
    )
    for item in classes or []:
        if str(item.get("name")) == class_name:
            print(f"[OK] Reused class: {class_name} ({item.get('code')})")
            return item
    created = _request(
        client,
        "POST",
        "/api/teacher/classes",
        token=teacher.access_token,
        json={"name": class_name},
    )
    print(f"[OK] Created class: {class_name} ({created.get('code')})")
    return created


def _ensure_student(
    client: httpx.Client,
    *,
    account: str,
    name: str,
    student_id: str,
    password: str,
    class_id: str,
) -> Session:
    session = _try_login(client, account, password, "student")
    if session:
        actual_class = str(session.user.get("class_id") or "")
        if actual_class != class_id:
            raise AutomationError(
                f"Student {account!r} already exists in class {actual_class or '<none>'}, "
                f"not the automation class {class_id}"
            )
        print(f"[OK] Reused student: {account}")
        return session

    response = client.post(
        "/api/auth/register/student",
        json={
            "account": account,
            "password": password,
            "name": name,
            "class_id": class_id,
            "email": f"{account}@example.com",
            "student_id": student_id,
        },
    )
    if response.status_code != 200:
        raise AutomationError(
            f"Student {account!r} cannot log in and cannot be registered. "
            "The account may already exist with another password. "
            f"Registration response: HTTP {response.status_code}: "
            f"{_response_detail(response)}"
        )
    session = _try_login(client, account, password, "student")
    if not session:
        raise AutomationError(
            f"Student {account!r} was registered but login still failed"
        )
    print(f"[OK] Registered student: {account}")
    return session


def _ensure_student_assessment(client: httpx.Client, student: Session) -> None:
    assessment = _request(
        client,
        "GET",
        "/api/student/assessment",
        token=student.access_token,
    )
    if assessment:
        print(f"[OK] Reused ability assessment: {student.account}")
        return
    _request(
        client,
        "POST",
        "/api/student/assessment",
        token=student.access_token,
        json={
            "personality_type": "ENTP",
            "expression_willingness": 80,
            "logical_thinking": 82,
            "stablecoin_knowledge": 76,
            "financial_knowledge": 78,
            "critical_thinking": 84,
        },
    )
    print(f"[OK] Completed ability assessment: {student.account}")


def _publish_debate(
    client: httpx.Client,
    teacher: Session,
    class_id: str,
    students: list[Session],
    topic: str,
    duration: int,
    student_specs: tuple[tuple[str, str, str, str], ...] = DEFAULT_STUDENTS,
) -> dict[str, Any]:
    role_assignments = [
        {
            "user_id": str(student.user["id"]),
            "role": student_specs[index][3],
            "override_reason": "local_e2e_automation",
        }
        for index, student in enumerate(students)
    ]
    debate = _request(
        client,
        "POST",
        "/api/teacher/debates",
        token=teacher.access_token,
        json={
            "class_id": class_id,
            "topic": topic,
            "duration": duration,
            "description": "由 scripts/auto_prepare_debate.py 创建的本地端到端测试辩论。",
            "student_ids": [str(student.user["id"]) for student in students],
            "role_assignments": role_assignments,
            "config_meta": {
                "mode": "competition",
                "role_assignment_mode": "strength_first",
                "assignment_policy": "ai_recommend_then_confirm",
                "rounds": 3,
                "topic_source": "manual",
            },
            "status": "published",
        },
    )
    if not debate.get("id") or not debate.get("invitation_code"):
        raise AutomationError("Create debate response is missing id/invitation_code")
    print(
        f"[OK] Published debate: {debate['id']} "
        f"(invitation_code={debate['invitation_code']})"
    )
    return debate


def _join_students(
    client: httpx.Client, students: list[Session], invitation_code: str
) -> list[dict[str, Any]]:
    joined: list[dict[str, Any]] = []
    for student in students:
        item = _request(
            client,
            "POST",
            "/api/student/debates/join",
            token=student.access_token,
            json={"invitation_code": invitation_code},
        )
        joined.append(item)
        print(f"[OK] Joined: {student.account} -> {item.get('role')}")
    return joined


def _websocket_url(base_url: str, room_id: str, ticket: str) -> str:
    parsed = urlsplit(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    prefix = parsed.path.rstrip("/")
    return (
        f"{scheme}://{parsed.netloc}{prefix}/ws/debate/{quote(room_id, safe='')}"
        f"?ticket={quote(ticket, safe='')}"
    )


async def _receive_initial_state(socket: Any, account: str) -> dict[str, Any]:
    for _ in range(8):
        raw = await asyncio.wait_for(socket.recv(), timeout=10)
        message = json.loads(raw)
        if message.get("type") == "state_update":
            return message.get("data") or {}
        if message.get("type") in {"error", "permission_denied"}:
            raise AutomationError(f"WebSocket rejected {account}: {message}")
    raise AutomationError(f"WebSocket did not send initial state for {account}")


async def _wait_until_started(socket: Any, timeout: float = 20.0) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        remaining = max(0.1, deadline - asyncio.get_running_loop().time())
        raw = await asyncio.wait_for(socket.recv(), timeout=remaining)
        message = json.loads(raw)
        message_type = message.get("type")
        data = message.get("data") or {}
        if message_type == "debate_started":
            return data
        if (
            message_type == "state_update"
            and str(data.get("current_phase")) != "waiting"
        ):
            return data
        if message_type in {"error", "permission_denied"}:
            raise AutomationError(f"Auto-ready failed: {message}")
    raise AutomationError("All checklists were submitted, but the debate did not start")


async def _auto_ready(
    client: httpx.Client,
    base_url: str,
    room_id: str,
    students: list[Session],
    *,
    keep_open: bool,
    hold_seconds: float,
) -> None:
    async with AsyncExitStack() as stack:
        sockets: list[Any] = []
        for student in students:
            ticket = _request(
                client,
                "GET",
                "/api/auth/ws-ticket",
                token=student.access_token,
                params={"room_id": room_id},
            )
            socket = await stack.enter_async_context(
                websockets.connect(
                    _websocket_url(base_url, room_id, str(ticket["ticket"])),
                    open_timeout=10,
                    # The app-level ping below is enough for this local helper.
                    # Disabling protocol keepalive avoids a noisy traceback when
                    # the API is briefly busy starting an AI turn.
                    ping_interval=None,
                )
            )
            state = await _receive_initial_state(socket, student.account)
            sockets.append(socket)
            print(
                f"[OK] Online: {student.account} "
                f"(phase={state.get('current_phase')}, "
                f"ready={state.get('waiting_status', {}).get('ready_count', 0)})"
            )

        for student, socket in zip(students, sockets):
            await socket.send(
                json.dumps(
                    {"type": "waiting_checklist_update", "data": {"items": [True] * 4}}
                )
            )
            print(f"[OK] Ready checklist submitted: {student.account}")

        started = await _wait_until_started(sockets[0])
        print(
            "[OK] Debate started automatically: "
            f"phase={started.get('current_phase') or 'opening'}"
        )

        if keep_open:
            print(
                "[HOLD] Four student connections remain online. Press Ctrl+C to stop."
            )
            try:
                while True:
                    await asyncio.sleep(30)
                    for socket in sockets:
                        await socket.send(json.dumps({"type": "ping", "data": {}}))
            except ConnectionClosed as exc:
                print(
                    "[STOP] A simulated student connection was closed by the server "
                    f"(code={exc.code}, reason={exc.reason or 'none'})."
                )
        elif hold_seconds > 0:
            print(f"[HOLD] Keeping students online for {hold_seconds:g} seconds...")
            await asyncio.sleep(hold_seconds)


def _is_loopback_url(base_url: str) -> bool:
    host = (urlsplit(base_url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("DEBATE_TEST_BASE_URL", DEFAULT_BASE_URL),
        help="Web/API base URL (default: http://localhost:8860)",
    )
    parser.add_argument(
        "--teacher-account",
        default=os.getenv("DEBATE_TEST_TEACHER_ACCOUNT", DEFAULT_TEACHER_ACCOUNT),
    )
    parser.add_argument(
        "--teacher-password",
        default=os.getenv("DEBATE_TEST_TEACHER_PASSWORD", DEFAULT_TEACHER_PASSWORD),
    )
    parser.add_argument(
        "--student-password",
        default=os.getenv("DEBATE_TEST_STUDENT_PASSWORD", DEFAULT_STUDENT_PASSWORD),
    )
    parser.add_argument("--class-name", default=DEFAULT_CLASS_NAME)
    parser.add_argument(
        "--topic",
        default=None,
        help="Debate topic; defaults to a timestamped automation topic",
    )
    parser.add_argument("--duration", type=int, default=35)
    parser.add_argument(
        "--existing-debate-id",
        help="Reuse an already published debate instead of creating another one",
    )
    parser.add_argument(
        "--existing-invitation-code",
        help="Invitation code paired with --existing-debate-id",
    )
    parser.add_argument(
        "--auto-ready",
        action="store_true",
        help="Connect all four students and complete the readiness checklist",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open Edge directly in the teacher arena with an injected login session",
    )
    parser.add_argument(
        "--visual",
        action="store_true",
        help=(
            "One-click visual mode: auto-ready students, keep them online, and open "
            "the signed-in teacher arena in Edge"
        ),
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help=(
            "Full logic-test mode: create a separate four-student team, complete "
            "all readiness checklists, and open one signed-in teacher window plus "
            "four independent student windows"
        ),
    )
    parser.add_argument(
        "--interactive-ready-only",
        action="store_true",
        help=(
            "Submit all four logic-test student checklists for an existing debate "
            "without opening duplicate browser windows"
        ),
    )
    parser.add_argument(
        "--edge-path",
        default=os.getenv("DEBATE_TEST_EDGE_PATH"),
        help="Optional explicit path to msedge.exe",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep the four student WebSockets online until Ctrl+C (requires --auto-ready)",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=30.0,
        help="Seconds to keep students online after auto-start (default: 30)",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow creating test accounts on a non-loopback URL",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def run(args: argparse.Namespace) -> int:
    if args.visual:
        args.auto_ready = True
        args.keep_open = True
        args.open_browser = True

    if args.interactive:
        args.open_browser = True
        args.auto_ready = True
        if not args.keep_open:
            # The real student browser windows remain connected, so the helper
            # WebSockets only need to live long enough to submit readiness.
            args.hold_seconds = 0.0

    if args.interactive_ready_only:
        args.auto_ready = True
        args.open_browser = False
        args.hold_seconds = 0.0

    base_url = args.base_url.strip().rstrip("/")
    if not _is_loopback_url(base_url) and not args.allow_remote:
        raise AutomationError(
            "Refusing to create fixed test accounts on a remote host. "
            "Use a disposable test environment and pass --allow-remote explicitly."
        )
    if args.keep_open and not args.auto_ready:
        raise AutomationError("--keep-open requires --auto-ready")
    if args.duration <= 0:
        raise AutomationError("--duration must be positive")
    if bool(args.existing_debate_id) != bool(args.existing_invitation_code):
        raise AutomationError(
            "--existing-debate-id and --existing-invitation-code must be used together"
        )
    if args.interactive_ready_only and not args.existing_debate_id:
        raise AutomationError(
            "--interactive-ready-only requires --existing-debate-id and "
            "--existing-invitation-code"
        )

    topic = args.topic or (
        "自动化流程测试：人工智能是否应该成为课堂学习的基础工具？ "
        f"[{datetime.now().strftime('%Y%m%d-%H%M%S')}]"
    )
    print(f"[INFO] Target: {base_url}")

    with httpx.Client(
        base_url=base_url,
        timeout=args.timeout,
        trust_env=False,
    ) as client:
        health = _request(client, "GET", "/api/health")
        print(
            f"[OK] API health: {health.get('status', 'reachable') if isinstance(health, dict) else 'reachable'}"
        )

        teacher = _ensure_teacher(client, args.teacher_account, args.teacher_password)
        class_item = _ensure_class(client, teacher, args.class_name)
        class_id = str(class_item["id"])
        student_specs = (
            LOGIC_TEST_STUDENTS
            if args.interactive or args.interactive_ready_only
            else DEFAULT_STUDENTS
        )
        students = [
            _ensure_student(
                client,
                account=account,
                name=name,
                student_id=student_id,
                password=args.student_password,
                class_id=class_id,
            )
            for account, name, student_id, _role in student_specs
        ]
        for student in students:
            _ensure_student_assessment(client, student)

        debate = (
            {
                "id": args.existing_debate_id,
                "invitation_code": args.existing_invitation_code,
            }
            if args.existing_debate_id
            else _publish_debate(
                client,
                teacher,
                class_id,
                students,
                topic,
                args.duration,
                student_specs,
            )
        )
        if args.existing_debate_id:
            print(f"[OK] Reusing debate: {args.existing_debate_id}")
        joined = _join_students(client, students, str(debate["invitation_code"]))

        summary = {
            "base_url": base_url,
            "debate_id": str(debate["id"]),
            "invitation_code": str(debate["invitation_code"]),
            "topic": topic,
            "teacher": args.teacher_account,
            "students": [
                {"account": session.account, "role": item.get("role")}
                for session, item in zip(students, joined)
            ],
            "teacher_arena_url": f"{base_url}/teacher/debates/{debate['id']}/arena",
            "student_arena_url": f"{base_url}/student/debates/{debate['id']}/arena",
        }
        print("\n=== AUTOMATION RESULT ===")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print("\n=== TEST CREDENTIALS ===")
        print(f"teacher: {args.teacher_account} / {args.teacher_password}")
        for student in students:
            print(f"student: {student.account} / {args.student_password}")

        if args.open_browser:
            _open_authenticated_browser(
                teacher,
                str(summary["teacher_arena_url"]),
                args.edge_path,
                "逻辑测试-教师观察台",
            )

        if args.interactive:
            for index, student in enumerate(students, start=1):
                _open_authenticated_browser(
                    student,
                    str(summary["student_arena_url"]),
                    args.edge_path,
                    f"逻辑测试-学生{index}-{student.account}",
                    window_index=index,
                )
            print("\n=== FULL LOGIC TEST CHECKLIST ===")
            print("1. 脚本会自动完成四份准备清单并开赛，无需再逐窗点击准备项。")
            print("2. 轮到哪位学生，就只在对应窗口开麦并说一段包含具体主张和论据的话。")
            print("3. 核对转写文本是否逐句忠实，不允许把未说过的话补进记录。")
            print("4. 核对 AI 是否回应刚才的具体论点，并能引用前序发言而非输出固定稿。")
            print("5. 完成所有阶段后等待报告状态变为 ready，再检查逐人评分、证据和 PDF。")
            print("提示：五个窗口使用独立浏览器配置，任务栏中可分别切换；只给当前学生窗口麦克风权限。")

        if args.auto_ready:
            asyncio.run(
                _auto_ready(
                    client,
                    base_url,
                    str(debate["id"]),
                    students,
                    keep_open=args.keep_open,
                    hold_seconds=max(0.0, args.hold_seconds),
                )
            )

    return 0


def main() -> int:
    try:
        return run(_build_parser().parse_args())
    except KeyboardInterrupt:
        print("\n[STOP] Automation connections closed.")
        return 130
    except (AutomationError, httpx.HTTPError, OSError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
