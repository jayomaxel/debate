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
