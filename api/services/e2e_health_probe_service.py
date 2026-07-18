"""Observable production probe for the speech-to-AI response chain.

The probe deliberately executes the same ASR and debater agent entry points used
by the websocket flow. It does not return user audio, transcript text, or model
output; only safe metadata and step results are exposed to health-check callers.
"""

from __future__ import annotations

import base64
import binascii
import asyncio
import time
import uuid
import wave
from array import array
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from prometheus_client import Counter, Gauge, Histogram

from config import settings
from logging_config import get_logger


logger = get_logger(__name__)

E2E_PROBE_RUNS = Counter(
    "debate_e2e_probe_runs_total",
    "Number of speech-to-AI end-to-end health probe runs.",
    ("status",),
)
E2E_PROBE_STEP_RUNS = Counter(
    "debate_e2e_probe_step_runs_total",
    "Number of end-to-end probe step executions.",
    ("step", "status"),
)
E2E_PROBE_DURATION = Histogram(
    "debate_e2e_probe_duration_seconds",
    "End-to-end health probe duration in seconds.",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 20, 30, 60, float("inf")),
)
E2E_PROBE_STEP_DURATION = Histogram(
    "debate_e2e_probe_step_duration_seconds",
    "End-to-end health probe step duration in seconds.",
    ("step",),
    buckets=(0.05, 0.1, 0.5, 1, 2, 5, 10, 30, float("inf")),
)
E2E_PROBE_UP = Gauge(
    "debate_e2e_probe_up",
    "Whether the last enabled end-to-end probe passed.",
)
E2E_PROBE_LAST_SUCCESS = Gauge(
    "debate_e2e_probe_last_success_timestamp_seconds",
    "Unix timestamp of the last successful end-to-end probe.",
)

_state_lock = Lock()
_last_probe: dict[str, Any] = {
    "status": "unknown",
    "probe_id": None,
    "checked_at": None,
    "duration_ms": None,
}


def get_last_probe_state() -> dict[str, Any]:
    """Return a copy of the last probe summary for lightweight health output."""
    with _state_lock:
        return dict(_last_probe)


def _set_last_probe_state(summary: dict[str, Any]) -> None:
    with _state_lock:
        _last_probe.clear()
        _last_probe.update(
            {
                "status": summary.get("status"),
                "probe_id": summary.get("probe_id"),
                "checked_at": summary.get("checked_at"),
                "duration_ms": summary.get("duration_ms"),
            }
        )


def _safe_error(exc: BaseException) -> str:
    """Keep health responses useful without exposing credentials or payloads."""
    message = str(exc).strip().replace("\n", " ")
    if len(message) > 240:
        message = f"{message[:237]}..."
    return message or exc.__class__.__name__


def _safe_message(value: Any) -> str:
    """Sanitize provider errors before returning them from a health endpoint."""
    return _safe_error(RuntimeError(str(value)))


def _build_default_wav() -> bytes:
    """Build a valid, short WAV fallback for local/unit-test probing.

    Production must configure ``E2E_HEALTH_PROBE_AUDIO_PATH`` or
    ``E2E_HEALTH_PROBE_AUDIO_B64`` with a recording containing the expected
    phrase. The generated tone is intentionally not accepted as a production
    success signal by the release gate because it normally transcribes empty.
    """
    samples = array("h", [0] * 8000)
    import io

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(samples.tobytes())
    return buffer.getvalue()


def load_probe_audio() -> tuple[bytes, str, Optional[str]]:
    """Load configured probe audio and return bytes, format and an error."""
    audio_format = (settings.E2E_HEALTH_PROBE_AUDIO_FORMAT or "wav").strip().lower()
    configured_path = (settings.E2E_HEALTH_PROBE_AUDIO_PATH or "").strip()
    configured_b64 = (settings.E2E_HEALTH_PROBE_AUDIO_B64 or "").strip()

    if configured_path:
        path = Path(configured_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        try:
            audio_data = path.read_bytes()
        except OSError as exc:
            return b"", audio_format, f"probe audio file unavailable: {_safe_error(exc)}"
        if not audio_data:
            return b"", audio_format, "probe audio file is empty"
        return audio_data, audio_format, None

    if configured_b64:
        try:
            audio_data = base64.b64decode(configured_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            return b"", audio_format, f"probe audio base64 is invalid: {_safe_error(exc)}"
        if not audio_data:
            return b"", audio_format, "probe audio base64 is empty"
        return audio_data, audio_format, None

    # Keep local development and unit tests runnable, but explicitly surface the
    # missing production fixture in the result instead of silently passing it.
    if settings.IS_PRODUCTION:
        return b"", audio_format, (
            "production probe audio is not configured; set "
            "E2E_HEALTH_PROBE_AUDIO_PATH or E2E_HEALTH_PROBE_AUDIO_B64"
        )
    return _build_default_wav(), audio_format, None


class E2EHealthProbeService:
    """Run the ASR -> transcript -> AI response production chain."""

    async def run(self, db) -> dict[str, Any]:
        probe_id = str(uuid.uuid4())
        started = time.perf_counter()
        deadline = started + max(0.1, float(settings.E2E_HEALTH_PROBE_TIMEOUT_SECONDS))
        checked_at = time.time()
        steps: dict[str, dict[str, Any]] = {}
        status = "failed"

        if not settings.E2E_HEALTH_PROBE_ENABLED:
            summary = self._summary(
                probe_id,
                checked_at,
                started,
                status="disabled",
                steps=steps,
                error="E2E_HEALTH_PROBE_ENABLED is false",
            )
            E2E_PROBE_RUNS.labels(status="disabled").inc()
            E2E_PROBE_UP.set(0)
            _set_last_probe_state(summary)
            logger.warning(
                "E2E speech-to-AI probe disabled",
                extra={"probe_id": probe_id, "status": "disabled"},
            )
            return summary

        audio_data, audio_format, audio_error = load_probe_audio()
        if audio_error:
            steps["audio"] = {"status": "failed", "error": audio_error}
            E2E_PROBE_STEP_RUNS.labels(step="audio", status="failed").inc()
            summary = self._summary(
                probe_id,
                checked_at,
                started,
                status="not_configured" if "not configured" in audio_error else "failed",
                steps=steps,
                error=audio_error,
            )
            E2E_PROBE_RUNS.labels(status=summary["status"]).inc()
            E2E_PROBE_UP.set(0)
            _set_last_probe_state(summary)
            logger.error(
                "E2E speech-to-AI probe is not configured",
                extra={"probe_id": probe_id, "status": summary["status"]},
            )
            return summary

        steps["audio"] = {"status": "passed", "bytes": len(audio_data), "format": audio_format}
        E2E_PROBE_STEP_RUNS.labels(step="audio", status="passed").inc()

        try:
            from utils.voice_processor import voice_processor

            step_started = time.perf_counter()
            asr_result = await asyncio.wait_for(
                voice_processor.transcribe_audio(
                    audio_data,
                    audio_format=audio_format,
                    language="zh",
                    db=db,
                ),
                timeout=max(0.1, deadline - time.perf_counter()),
            )
            asr_elapsed = time.perf_counter() - step_started
            E2E_PROBE_STEP_DURATION.labels(step="asr").observe(asr_elapsed)
            text = self._extract_text(asr_result)
            asr_error = asr_result.get("error") if isinstance(asr_result, dict) else None
            expected_text = (settings.E2E_HEALTH_PROBE_EXPECTED_TEXT or "").strip()
            expected_ok = not expected_text or expected_text.lower() in text.lower()
            if asr_error or not text or not expected_ok:
                reason = _safe_message(asr_error) if asr_error else (
                    "transcript is empty" if not text else "transcript did not match expected text"
                )
                steps["asr"] = {
                    "status": "failed",
                    "duration_ms": round(asr_elapsed * 1000, 2),
                    "text_length": len(text),
                    "expected_text_configured": bool(expected_text),
                    "error": reason,
                }
                E2E_PROBE_STEP_RUNS.labels(step="asr", status="failed").inc()
                return self._finish(
                    probe_id, checked_at, started, steps, error=f"ASR step failed: {reason}"
                )
            steps["asr"] = {
                "status": "passed",
                "duration_ms": round(asr_elapsed * 1000, 2),
                "text_length": len(text),
                "expected_text_configured": bool(expected_text),
            }
            E2E_PROBE_STEP_RUNS.labels(step="asr", status="passed").inc()

            from agents.debater_agent import AIDebaterAgent

            step_started = time.perf_counter()
            agent = AIDebaterAgent(position=1, db=db)
            response = await asyncio.wait_for(
                agent.generate_free_debate_speech(
                    topic="生产链路健康探针",
                    stance="中立",
                    context=[{"role": "user", "content": text}],
                    recent_speeches=[],
                ),
                timeout=max(0.1, deadline - time.perf_counter()),
            )
            ai_elapsed = time.perf_counter() - step_started
            E2E_PROBE_STEP_DURATION.labels(step="ai").observe(ai_elapsed)
            ai_text = str(response or "").strip()
            is_fallback = not ai_text or ai_text.startswith("[AI")
            if is_fallback:
                reason = "AI response is empty or fallback marker"
                steps["ai"] = {
                    "status": "failed",
                    "duration_ms": round(ai_elapsed * 1000, 2),
                    "response_length": len(ai_text),
                    "fallback": True,
                    "error": reason,
                }
                E2E_PROBE_STEP_RUNS.labels(step="ai", status="failed").inc()
                return self._finish(
                    probe_id, checked_at, started, steps, error=f"AI step failed: {reason}"
                )
            steps["ai"] = {
                "status": "passed",
                "duration_ms": round(ai_elapsed * 1000, 2),
                "response_length": len(ai_text),
                "fallback": False,
            }
            E2E_PROBE_STEP_RUNS.labels(step="ai", status="passed").inc()
            status = "passed"
        except Exception as exc:
            logger.exception("E2E speech-to-AI health probe failed", extra={"probe_id": probe_id})
            E2E_PROBE_STEP_RUNS.labels(step="runtime", status="failed").inc()
            steps.setdefault("runtime", {"status": "failed", "error": _safe_error(exc)})
            return self._finish(
                probe_id, checked_at, started, steps, error=f"probe execution failed: {_safe_error(exc)}"
            )

        summary = self._summary(probe_id, checked_at, started, status=status, steps=steps)
        E2E_PROBE_RUNS.labels(status="passed").inc()
        E2E_PROBE_UP.set(1)
        E2E_PROBE_LAST_SUCCESS.set(time.time())
        _set_last_probe_state(summary)
        logger.info(
            "E2E speech-to-AI probe passed",
            extra={
                "probe_id": probe_id,
                "status": "passed",
                "duration_ms": summary["duration_ms"],
            },
        )
        return summary

    @staticmethod
    def _extract_text(result: Any) -> str:
        if isinstance(result, dict):
            for key in ("text", "transcript", "content"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return ""
        if isinstance(result, list):
            return " ".join(
                text
                for text in (E2EHealthProbeService._extract_text(item) for item in result)
                if text
            ).strip()
        return str(result or "").strip()

    def _finish(
        self,
        probe_id: str,
        checked_at: float,
        started: float,
        steps: dict[str, dict[str, Any]],
        error: str,
    ) -> dict[str, Any]:
        summary = self._summary(
            probe_id, checked_at, started, status="failed", steps=steps, error=error
        )
        E2E_PROBE_RUNS.labels(status="failed").inc()
        E2E_PROBE_UP.set(0)
        _set_last_probe_state(summary)
        logger.error(
            "E2E speech-to-AI probe failed",
            extra={
                "probe_id": probe_id,
                "status": "failed",
                "duration_ms": summary["duration_ms"],
                "error": error,
            },
        )
        return summary

    @staticmethod
    def _summary(
        probe_id: str,
        checked_at: float,
        started: float,
        *,
        status: str,
        steps: dict[str, dict[str, Any]],
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        result = {
            "status": status,
            "probe_id": probe_id,
            "checked_at": checked_at,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "steps": steps,
            "release_gate": {
                "required": bool(settings.RELEASE_GATE_REQUIRE_E2E_HEALTH),
                "eligible": status == "passed",
            },
        }
        E2E_PROBE_DURATION.observe(result["duration_ms"] / 1000)
        if error:
            result["error"] = error
        return result


e2e_health_probe_service = E2EHealthProbeService()
