import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest

from models.debate import Debate
from models.user import User
from services.runtime_state_store import RuntimeStateStore
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


def test_crashed_state_owner_is_recovered_by_another_process(e2e_db):
    teacher = User(
        id=uuid.uuid4(),
        account=f"failover-teacher-{uuid.uuid4().hex[:8]}",
        password_hash="x",
        user_type="teacher",
        name="Failover Teacher",
        email=f"{uuid.uuid4().hex}@example.test",
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="Process failover",
        duration=10,
        invitation_code=uuid.uuid4().hex[:6],
        teacher_id=teacher.id,
    )
    e2e_db.add_all([teacher, debate])
    e2e_db.commit()
    room_id = str(debate.id)
    RuntimeStateStore(e2e_db).ensure(
        room_id,
        room_id,
        {"segment_id": "initial", "mic_expires_at": None},
    )

    child_code = """
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.runtime_state_store import RuntimeStateStore

engine = create_engine(os.environ['E2E_DATABASE_URL'], pool_pre_ping=True)
db = sessionmaker(bind=engine, expire_on_commit=False)()
store = RuntimeStateStore(db)
if not store.acquire_lease(
    os.environ['E2E_FAILOVER_ROOM_ID'],
    owner='instance-a-process',
    now=datetime.now(timezone.utc),
    ttl_seconds=1,
):
    os._exit(92)
snapshot = store.patch(
    os.environ['E2E_FAILOVER_ROOM_ID'],
    {'segment_id': 'written-by-instance-a'},
)
if snapshot.version != 1:
    os._exit(93)
os._exit(29)
"""
    child_env = {**os.environ, "E2E_FAILOVER_ROOM_ID": room_id}
    crashed = subprocess.run(
        [sys.executable, "-c", child_code],
        cwd=Path(__file__).resolve().parents[2],
        env=child_env,
        check=False,
        timeout=30,
    )
    assert crashed.returncode == 29

    e2e_db.expire_all()
    store = RuntimeStateStore(e2e_db)
    persisted = store.load(room_id)
    assert persisted.version == 1
    assert persisted.state["segment_id"] == "written-by-instance-a"

    from datetime import datetime, timezone

    assert store.acquire_lease(
        room_id,
        owner="instance-b-process",
        now=datetime.now(timezone.utc),
        ttl_seconds=30,
    ) is False
    time.sleep(1.2)
    assert store.acquire_lease(
        room_id,
        owner="instance-b-process",
        now=datetime.now(timezone.utc),
        ttl_seconds=30,
    ) is True
    recovered = store.patch(room_id, {"segment_id": "continued-by-instance-b"})
    assert recovered.version == 2
    assert recovered.state["segment_id"] == "continued-by-instance-b"
