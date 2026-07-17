import uuid
from datetime import datetime

import pytest

from models.debate import Debate
from services.room_manager import DebatePhase, DebateRoomManager


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
