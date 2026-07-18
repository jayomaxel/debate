#!/usr/bin/env python3
"""Fail a deployment when the production speech-to-AI probe is not green.

Usage:
    python scripts/check_e2e_release_gate.py --url https://api.example.com

The endpoint is intentionally the only source of truth for the gate. The
script returns a non-zero exit code for disabled, not-configured, failed, or
malformed probe responses, so it can be used directly by CI/CD.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.getenv("E2E_HEALTH_URL", ""),
        help="Base API URL or full /health/e2e URL (also E2E_HEALTH_URL).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("E2E_HEALTH_PROBE_TOKEN", ""),
        help="Optional X-E2E-Probe-Token value.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("E2E_HEALTH_GATE_TIMEOUT_SECONDS", "35")),
        help="HTTP timeout in seconds.",
    )
    return parser


def _probe_url(raw_url: str) -> str:
    url = raw_url.strip().rstrip("/")
    if not url:
        raise ValueError("--url or E2E_HEALTH_URL is required")
    if url.endswith("/health/e2e") or url.endswith("/api/health/e2e"):
        return url
    if url.endswith("/health/readiness") or url.endswith("/api/health/readiness"):
        return url
    return f"{url}/health/e2e"


def run_gate(url: str, token: str = "", timeout: float = 35.0) -> int:
    try:
        endpoint = _probe_url(url)
    except ValueError as exc:
        print(f"E2E release gate: {exc}", file=sys.stderr)
        return 2
    headers = {"Accept": "application/json", "User-Agent": "debate-release-gate/1"}
    if token:
        headers["X-E2E-Probe-Token"] = token

    request = urllib.request.Request(endpoint, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8")
            http_status = response.status
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        http_status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"E2E release gate: request failed: {exc}", file=sys.stderr)
        return 2

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        print(f"E2E release gate: invalid JSON (HTTP {http_status})", file=sys.stderr)
        return 2

    probe_status = payload.get("status")
    eligible = bool((payload.get("release_gate") or {}).get("eligible"))
    probe_id = payload.get("probe_id", "unknown")
    if http_status == 200 and probe_status == "passed" and eligible:
        print(f"E2E release gate: PASS (probe_id={probe_id})")
        return 0

    error = payload.get("error") or "probe did not pass"
    print(
        f"E2E release gate: BLOCK (http={http_status}, status={probe_status}, "
        f"probe_id={probe_id}, error={error})",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    args = _build_parser().parse_args()
    return run_gate(args.url, token=args.token, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
