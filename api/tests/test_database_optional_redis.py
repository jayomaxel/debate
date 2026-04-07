import database


def test_get_redis_returns_none_when_dependency_is_missing(monkeypatch):
    monkeypatch.setattr(database, "redis", None)
    monkeypatch.setattr(database, "redis_client", None)
    monkeypatch.setattr(database, "_redis_missing_dependency_logged", False)

    assert database.get_redis() is None
