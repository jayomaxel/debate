import asyncio

import main
from services.kb_vector_schema_service import KBVectorSchemaService


class _DummySession:
    def execute(self, _query):
        return None

    def close(self):
        return None


def test_database_health_uses_runtime_session_factory(monkeypatch):
    dummy_session = _DummySession()

    monkeypatch.setattr(main.database_module, "SessionLocal", lambda: dummy_session)

    ok, error = main._database_health()

    assert ok is True
    assert error is None


def test_metrics_endpoint_exposes_operational_status(monkeypatch):
    monkeypatch.setattr(main, "_database_health", lambda: (True, None))
    monkeypatch.setattr(main, "_redis_health", lambda: ("disabled", None))

    response = asyncio.run(main.metrics())
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "debate_database_up" in body
    assert "debate_redis_enabled" in body
    assert "debate_background_jobs" in body


def test_production_health_is_503_when_vector_alignment_mismatches(monkeypatch):
    original = KBVectorSchemaService.runtime_snapshot()

    async def ready_ai_runtime():
        return {"status": "ready", "services": {}}

    try:
        KBVectorSchemaService.set_runtime_snapshot(
            {
                "status": "mismatch",
                "error_code": "VECTOR_DIMENSION_MISMATCH",
                "configured_dimension": 1024,
                "database_dimension": 1536,
                "model_output_dimension": 1024,
            }
        )
        monkeypatch.setattr(main.settings, "IS_PRODUCTION", True)
        monkeypatch.setattr(main, "_database_health", lambda: (True, None))
        monkeypatch.setattr(main, "_redis_health", lambda: ("connected", None))
        monkeypatch.setattr(main, "_ai_runtime_health", ready_ai_runtime)

        response = asyncio.run(main.health_check())
        body = response.body.decode("utf-8")

        assert response.status_code == 503
        assert '"status":"unhealthy"' in body
        assert '"error_code":"VECTOR_DIMENSION_MISMATCH"' in body
    finally:
        KBVectorSchemaService.set_runtime_snapshot(original)


def test_multi_instance_health_is_503_when_redis_bridge_is_down(monkeypatch):
    from utils.websocket_manager import websocket_manager

    original = KBVectorSchemaService.runtime_snapshot()

    async def ready_ai_runtime():
        return {"status": "ready", "services": {}}

    try:
        KBVectorSchemaService.set_runtime_snapshot({"status": "ready", "error_code": None})
        monkeypatch.setattr(main, "_database_health", lambda: (True, None))
        monkeypatch.setattr(main, "_redis_health", lambda: ("disconnected", "redis down"))
        monkeypatch.setattr(main, "_ai_runtime_health", ready_ai_runtime)
        monkeypatch.setattr(
            websocket_manager,
            "bridge_status",
            lambda: {
                "mode": "multi_instance",
                "redis_bridge": "disconnected",
                "ready": False,
                "error": "redis down",
            },
        )

        response = asyncio.run(main.health_check())

        assert response.status_code == 503
        assert response.body.decode("utf-8").find('"realtime"') > 0
    finally:
        KBVectorSchemaService.set_runtime_snapshot(original)
