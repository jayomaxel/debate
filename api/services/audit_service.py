from __future__ import annotations

import json
import socket
from collections import deque
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Optional

from prometheus_client import Counter

from config import settings
from database import get_redis
from logging_config import get_logger
from utils.security import build_audit_log_event_contract

logger = get_logger(__name__)

AUDIT_EVENT_TOTAL = Counter(
    "debate_audit_events_total",
    "Total number of security audit events recorded.",
    ("event_type", "result"),
)


class AuditService:
    _MAX_EVENTS = 1000
    _REDIS_KEY = "audit:events"
    _memory_events: deque[str] = deque(maxlen=_MAX_EVENTS)
    _lock = RLock()
    _redis_disabled = False

    @classmethod
    def record_event(
        cls,
        *,
        event_type: str,
        actor_id: str,
        actor_role: str,
        target_type: str,
        target_id: str,
        result: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        event = build_audit_log_event_contract(
            event_type=event_type,
            actor_id=str(actor_id or "system"),
            actor_role=str(actor_role or "system"),
            target_type=str(target_type or "unknown"),
            target_id=str(target_id or "unknown"),
            result=result,
            metadata=metadata or {},
        )
        normalized_event = cls._normalize_event(event)
        cls._store_event(normalized_event)
        AUDIT_EVENT_TOTAL.labels(event_type=event_type, result=result).inc()
        return normalized_event

    @classmethod
    def list_events(
        cls,
        *,
        limit: int = 50,
        event_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        result: Optional[str] = None,
        target_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or 50), 200))
        events = cls._load_events()
        filtered: list[dict[str, Any]] = []

        for event in events:
            if event_type and str(event.get("event_type")) != str(event_type):
                continue
            if actor_id and str(event.get("actor_id")) != str(actor_id):
                continue
            if result and str(event.get("result")) != str(result):
                continue
            if target_type and str(event.get("target_type")) != str(target_type):
                continue
            filtered.append(event)
            if len(filtered) >= normalized_limit:
                break

        return filtered

    @classmethod
    def clear_events(cls) -> None:
        with cls._lock:
            cls._memory_events.clear()

        redis_client = cls._get_redis_client()
        if redis_client is None:
            return

        try:
            redis_client.delete(cls._REDIS_KEY)
        except Exception as exc:  # pragma: no cover - depends on runtime services
            cls._redis_disabled = True
            logger.warning("Failed to clear Redis audit events: %s", exc)

    @classmethod
    def _normalize_event(cls, event: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(event)
        created_at = normalized.get("created_at")
        if isinstance(created_at, datetime):
            normalized["created_at"] = created_at.astimezone(timezone.utc).isoformat()
        elif created_at is None:
            normalized["created_at"] = datetime.now(timezone.utc).isoformat()
        normalized["metadata"] = dict(normalized.get("metadata") or {})
        return normalized

    @classmethod
    def _serialize_event(cls, event: dict[str, Any]) -> str:
        return json.dumps(event, ensure_ascii=True, separators=(",", ":"))

    @classmethod
    def _deserialize_event(cls, payload: str) -> Optional[dict[str, Any]]:
        try:
            event = json.loads(payload)
        except (TypeError, ValueError):
            return None
        return event if isinstance(event, dict) else None

    @classmethod
    def _store_event(cls, event: dict[str, Any]) -> None:
        serialized = cls._serialize_event(event)
        with cls._lock:
            cls._memory_events.appendleft(serialized)

        redis_client = cls._get_redis_client()
        if redis_client is None:
            return

        try:
            pipeline = redis_client.pipeline()
            pipeline.lpush(cls._REDIS_KEY, serialized)
            pipeline.ltrim(cls._REDIS_KEY, 0, cls._MAX_EVENTS - 1)
            pipeline.execute()
        except Exception as exc:  # pragma: no cover - depends on runtime services
            cls._redis_disabled = True
            logger.warning("Failed to persist audit event to Redis: %s", exc)

    @classmethod
    def _load_events(cls) -> list[dict[str, Any]]:
        redis_client = cls._get_redis_client()
        if redis_client is not None:
            try:
                payloads = redis_client.lrange(cls._REDIS_KEY, 0, cls._MAX_EVENTS - 1)
                events = [
                    event
                    for payload in payloads
                    if (event := cls._deserialize_event(payload)) is not None
                ]
                if events:
                    return events
            except Exception as exc:  # pragma: no cover - depends on runtime services
                cls._redis_disabled = True
                logger.warning("Failed to read audit events from Redis: %s", exc)

        with cls._lock:
            payloads = list(cls._memory_events)
        return [
            event
            for payload in payloads
            if (event := cls._deserialize_event(payload)) is not None
        ]

    @staticmethod
    def _get_redis_client():
        if AuditService._redis_disabled:
            return None
        try:
            with socket.create_connection(
                (settings.REDIS_HOST, int(settings.REDIS_PORT)),
                timeout=0.5,
            ):
                pass
        except OSError:
            AuditService._redis_disabled = True
            return None
        try:
            return get_redis()
        except Exception as exc:  # pragma: no cover - defensive fallback
            AuditService._redis_disabled = True
            logger.warning("Failed to resolve Redis client for audit service: %s", exc)
            return None
