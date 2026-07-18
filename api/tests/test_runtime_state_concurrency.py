import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.debate import Debate
from models.debate_runtime_state import DebateRuntimeState
from models.user import User
from services.runtime_state_store import RuntimeStateStore
from services.room_manager import DebateRoomManager


def test_runtime_state_compare_and_set_rejects_stale_version(db_session):
    teacher = User(
        id=uuid.uuid4(),
        account=f"teacher-{uuid.uuid4().hex[:8]}",
        password_hash="hashed",
        user_type="teacher",
        name="Teacher",
        email=f"{uuid.uuid4().hex}@example.test",
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="CAS",
        duration=30,
        invitation_code=uuid.uuid4().hex[:6],
        teacher_id=teacher.id,
    )
    db_session.add_all([teacher, debate])
    db_session.commit()
    store = RuntimeStateStore(db_session)
    initial = store.ensure(str(debate.id), str(debate.id), {"segment_id": "s1"})

    updated = store.compare_and_set(
        str(debate.id),
        initial.version,
        {"segment_id": "s2"},
    )

    assert updated is not None
    assert updated.version == initial.version + 1
    assert store.compare_and_set(
        str(debate.id),
        initial.version,
        {"segment_id": "stale"},
    ) is None
    assert store.load(str(debate.id)).state["segment_id"] == "s2"


def test_remote_runtime_state_updates_cache_and_rejects_stale_version():
    from services.room_manager import DebatePhase, RoomState

    manager = DebateRoomManager()
    state = RoomState(room_id="remote-room", debate_id="remote-debate")
    state._runtime_version = 2
    manager.rooms[state.room_id] = state

    assert manager.apply_remote_state(
        state.room_id,
        {
            "current_phase": DebatePhase.QUESTIONING.value,
            "segment_id": "segment-3",
            "participants": [{"user_id": "user-b", "online": True}],
            "waiting_checklists": {"user-b": {"ready": True}},
        },
        3,
    ) is True
    assert state.current_phase == DebatePhase.QUESTIONING
    assert state.segment_id == "segment-3"
    assert state.participants[0]["user_id"] == "user-b"
    assert state.waiting_checklists["user-b"]["ready"] is True
    assert state._runtime_version == 3

    assert manager.apply_remote_state(
        state.room_id,
        {"segment_id": "stale-segment"},
        2,
    ) is False
    assert state.segment_id == "segment-3"


def test_new_room_manager_recovers_persisted_deadline_and_segment(db_session):
    teacher = User(
        id=uuid.uuid4(),
        account=f"recover-teacher-{uuid.uuid4().hex[:8]}",
        password_hash="hashed",
        user_type="teacher",
        name="Recover Teacher",
        email=f"{uuid.uuid4().hex}@example.test",
    )
    debate = Debate(
        id=uuid.uuid4(),
        topic="Recover",
        duration=30,
        invitation_code=uuid.uuid4().hex[:6],
        teacher_id=teacher.id,
    )
    db_session.add_all([teacher, debate])
    db_session.commit()
    deadline = datetime.now(timezone.utc) + timedelta(seconds=45)

    async def scenario():
        first = DebateRoomManager()
        await first.create_room(str(debate.id), str(debate.id), db_session)
        assert await first.update_room_state(
            str(debate.id),
            segment_id="segment-2",
            mic_expires_at=deadline,
        )
        second = DebateRoomManager()
        recovered = await second.create_room(str(debate.id), str(debate.id), db_session)
        return recovered

    recovered = __import__("asyncio").run(scenario())

    assert recovered.segment_id == "segment-2"
    assert recovered.mic_expires_at == deadline
    assert recovered._runtime_version == 1


@pytest.mark.integration
def test_two_database_sessions_allow_only_one_concurrent_mic_claim():
    database_url = os.getenv("RUNTIME_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set RUNTIME_TEST_DATABASE_URL to an isolated migrated PostgreSQL database")
    engine = create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    setup = session_factory()
    try:
        teacher = User(
            id=uuid.uuid4(),
            account=f"runtime-teacher-{uuid.uuid4().hex[:8]}",
            password_hash="hashed",
            user_type="teacher",
            name="Runtime Teacher",
            email=f"{uuid.uuid4().hex}@example.test",
        )
        debate = Debate(
            id=uuid.uuid4(),
            topic="Concurrent microphone",
            duration=30,
            invitation_code=uuid.uuid4().hex[:6],
            teacher_id=teacher.id,
        )
        setup.add_all([teacher, debate])
        setup.commit()
        RuntimeStateStore(setup).ensure(
            str(debate.id),
            str(debate.id),
            {"mic_owner_user_id": None, "mic_owner_role": None, "mic_expires_at": None},
        )
        room_id = str(debate.id)
    finally:
        setup.close()

    def claim(user_number: int):
        db = session_factory()
        try:
            return RuntimeStateStore(db).claim_mic(
                room_id,
                user_id=f"user-{user_number}",
                user_role=f"debater_{user_number}",
                now=datetime.now(timezone.utc),
                ttl_seconds=30,
            )
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, (1, 2)))

    assert sum(1 for allowed, _, _ in results if allowed) == 1
    verify = session_factory()
    try:
        snapshot = RuntimeStateStore(verify).load(room_id)
        assert snapshot.version == 1
        assert snapshot.state["mic_owner_user_id"] in {"user-1", "user-2"}
        persisted_deadline = datetime.fromisoformat(snapshot.state["mic_expires_at"])
        assert persisted_deadline > datetime.now(timezone.utc)
        recovered = RuntimeStateStore(verify).patch(
            room_id,
            {
                "segment_id": "recovered-on-instance-b",
                "segment_start_time": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert recovered.version == 2
        assert recovered.state["segment_id"] == "recovered-on-instance-b"
        assert datetime.fromisoformat(recovered.state["mic_expires_at"]) == persisted_deadline
    finally:
        verify.query(DebateRuntimeState).filter(DebateRuntimeState.room_id == room_id).delete()
        verify.query(Debate).filter(Debate.id == uuid.UUID(room_id)).delete()
        verify.query(User).filter(User.account.like("runtime-teacher-%")).delete(synchronize_session=False)
        verify.commit()
        verify.close()
        engine.dispose()
