import pytest

from tests.test_runtime_state_concurrency import (
    test_two_database_sessions_allow_only_one_concurrent_mic_claim as _database_concurrency_proof,
)
from tests.test_websocket_multi_instance import (
    test_two_websocket_instances_forward_events_and_presence_via_redis as _redis_cross_instance_proof,
)


pytestmark = [pytest.mark.e2e, pytest.mark.integration]


def test_real_database_concurrency_gate():
    _database_concurrency_proof()


def test_real_redis_cross_instance_gate(monkeypatch):
    _redis_cross_instance_proof(monkeypatch)
