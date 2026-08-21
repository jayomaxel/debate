import uuid
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from models.debate import Debate
import services.flow_controller as flow_controller_module
import services.room_manager as room_manager_module
from services.flow_controller import DebateFlowController
from services.room_manager import DebatePhase, DebateRoomManager, RoomState


def _debate() -> Debate:
    return Debate(
        id=uuid.uuid4(),
        topic="Runtime persistence test",
        duration=30,
        invitation_code=uuid.uuid4().hex[:6],
        status="in_progress",
        report={},
    )


@pytest.mark.asyncio
async def test_room_runtime_state_is_restored_after_manager_restart(db_session):
    debate = _debate()
    db_session.add(debate)
    db_session.commit()

    first_manager = DebateRoomManager()
    first = await first_manager.create_room(str(debate.id), str(debate.id), db_session)
    first.current_phase = DebatePhase.FREE_DEBATE
    first.match_state = "FREE_DEBATE"
    first.segment_id = "free_debate"
    first.current_speaker = "debater_2"
    assert first_manager._persist_runtime_state(first, db_session)

    second_manager = DebateRoomManager()
    restored = await second_manager.create_room(
        str(debate.id), str(debate.id), db_session
    )

    assert restored.current_phase == DebatePhase.FREE_DEBATE
    assert restored.match_state == "FREE_DEBATE"
    assert restored.segment_id == "free_debate"
    assert restored.current_speaker == "debater_2"


@pytest.mark.asyncio
async def test_persisted_mic_claim_blocks_fresh_manager(db_session):
    debate = _debate()
    db_session.add(debate)
    db_session.commit()
    room_id = str(debate.id)
    now = datetime.utcnow()

    first_manager = DebateRoomManager()
    await first_manager.create_room(room_id, room_id, db_session)
    first_claim = await first_manager.claim_mic(
        room_id,
        user_id="user-one",
        user_role="debater_1",
        now=now,
        db=db_session,
    )
    assert first_claim["allowed"] is True

    second_manager = DebateRoomManager()
    await second_manager.create_room(room_id, room_id, db_session)
    second_claim = await second_manager.claim_mic(
        room_id,
        user_id="user-two",
        user_role="debater_2",
        now=now,
        db=db_session,
    )

    assert second_claim["allowed"] is False
    assert second_claim["reason"] == "occupied"
    assert second_claim["mic_owner_user_id"] == "user-one"


@pytest.mark.asyncio
async def test_resume_flow_repairs_partial_opening_snapshot(db_session, monkeypatch):
    debate = _debate()
    db_session.add(debate)
    db_session.commit()
    room_id = str(debate.id)

    manager = DebateRoomManager()
    room_state = await manager.create_room(room_id, room_id, db_session)
    room_state.current_phase = DebatePhase.OPENING
    room_state.match_state = "OPENING_PRO"
    room_state.room_status = "ongoing"
    room_state.segment_index = 0
    room_state.segment_id = None
    room_state.segment_start_time = None
    room_state.segment_time_remaining = 0
    room_state.current_speaker = None
    room_state.speaker_mode = None
    room_state.speaker_options = []
    room_state.flow_segments = []
    assert manager._persist_runtime_state(room_state, db_session)

    restarted_manager = DebateRoomManager()
    restored = await restarted_manager.create_room(room_id, room_id, db_session)
    controller = DebateFlowController()
    monkeypatch.setattr(flow_controller_module, "room_manager", restarted_manager)
    monkeypatch.setattr(controller, "start_timer", AsyncMock())
    monkeypatch.setattr(
        controller,
        "_sync_upcoming_ai_prethinking",
        AsyncMock(),
    )

    assert await controller.resume_flow(room_id) is True

    assert controller.segment_index[room_id] == 0
    assert restored.segment_id == "opening_positive_1"
    assert restored.current_speaker == "debater_1"
    assert restored.segment_time_remaining == 180
    assert restored.speaker_mode == "fixed"
    assert restored.speaker_options == ["debater_1"]
    assert restored.flow_segments[0]["speaker_roles"] == ["debater_1"]
    controller.start_timer.assert_awaited_once_with(room_id)


@pytest.mark.asyncio
async def test_resume_flow_preserves_complete_free_debate_snapshot(db_session, monkeypatch):
    debate = _debate()
    db_session.add(debate)
    db_session.commit()
    room_id = str(debate.id)
    segment_started_at = datetime.utcnow() + timedelta(hours=8)
    free_debate_segment = {
        "id": "free_debate",
        "title": "Free debate",
        "phase": DebatePhase.FREE_DEBATE,
        "duration": 480,
        "mode": "free",
        "speaker_roles": ["debater_1", "debater_2"],
    }

    manager = DebateRoomManager()
    room_state = await manager.create_room(room_id, room_id, db_session)
    room_state.current_phase = DebatePhase.FREE_DEBATE
    room_state.phase_start_time = segment_started_at
    room_state.match_state = "FREE_DEBATE"
    room_state.room_status = "ongoing"
    room_state.segment_index = 0
    room_state.segment_id = "free_debate"
    room_state.segment_title = "Free debate"
    room_state.segment_start_time = segment_started_at
    room_state.segment_time_remaining = 480
    room_state.speaker_mode = "free"
    room_state.speaker_options = ["debater_1", "debater_2"]
    room_state.flow_segments = [free_debate_segment]
    assert manager._persist_runtime_state(room_state, db_session)

    restarted_manager = DebateRoomManager()
    restored = await restarted_manager.create_room(room_id, room_id, db_session)
    controller = DebateFlowController()
    monkeypatch.setattr(flow_controller_module, "room_manager", restarted_manager)
    monkeypatch.setattr(controller, "start_timer", AsyncMock())
    monkeypatch.setattr(controller, "_sync_upcoming_ai_prethinking", AsyncMock())

    assert await controller.resume_flow(room_id) is True

    assert restored.current_phase == DebatePhase.FREE_DEBATE
    assert restored.segment_id == "free_debate"
    assert restored.speaker_mode == "free"
    assert restored.speaker_options == ["debater_1", "debater_2"]
    assert controller.segment_index[room_id] == 0
    controller.start_timer.assert_awaited_once_with(room_id)


@pytest.mark.asyncio
async def test_empty_room_grace_survives_navigation_reconnect(monkeypatch):
    manager = DebateRoomManager()
    room_id = str(uuid.uuid4())
    manager.rooms[room_id] = RoomState(
        room_id=room_id,
        debate_id=str(uuid.uuid4()),
        current_phase=DebatePhase.OPENING,
        room_status="ongoing",
        participants=[{"user_id": "student-one", "role": "debater_1"}],
    )
    cleanup_mock = AsyncMock()
    monkeypatch.setattr(room_manager_module, "EMPTY_ROOM_GRACE_SECONDS", 0.05)
    monkeypatch.setattr(
        flow_controller_module.flow_controller,
        "cleanup_room",
        cleanup_mock,
    )

    assert await manager.leave_room(room_id, "student-one") is True
    assert manager.get_room_state(room_id) is not None

    manager._cancel_empty_room_cleanup(room_id)
    manager.get_room_state(room_id).participants.append(
        {"user_id": "student-one", "role": "debater_1"}
    )
    await asyncio.sleep(0.08)

    assert manager.get_room_state(room_id) is not None
    cleanup_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_room_is_cleaned_after_grace(monkeypatch):
    manager = DebateRoomManager()
    room_id = str(uuid.uuid4())
    manager.rooms[room_id] = RoomState(
        room_id=room_id,
        debate_id=str(uuid.uuid4()),
        current_phase=DebatePhase.OPENING,
        room_status="ongoing",
        participants=[{"user_id": "student-one", "role": "debater_1"}],
    )
    cleanup_mock = AsyncMock()
    monkeypatch.setattr(room_manager_module, "EMPTY_ROOM_GRACE_SECONDS", 0.01)
    monkeypatch.setattr(
        flow_controller_module.flow_controller,
        "cleanup_room",
        cleanup_mock,
    )

    assert await manager.leave_room(room_id, "student-one") is True
    await asyncio.sleep(0.04)

    assert manager.get_room_state(room_id) is None
    cleanup_mock.assert_awaited_once_with(room_id)
