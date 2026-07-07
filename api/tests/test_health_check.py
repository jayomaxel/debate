import asyncio

import main


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
