import uuid
import asyncio
from types import SimpleNamespace

from agents.debater_agent import AIDebaterAgent
from services.room_manager import room_manager, DebatePhase, RoomState
from services.flow_controller import flow_controller
from utils.voice_processor import voice_processor
from utils.websocket_manager import websocket_manager


def test_flow_controller_segment_flow():
    room_id = "test_room_segment_001"
    debate_id = str(uuid.uuid4())

    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.WAITING,
    )
    room_manager.rooms[room_id] = room_state

    segments = [
        {
            "id": "s1",
            "title": "测试段1",
            "phase": DebatePhase.OPENING,
            "duration": 5,
            "mode": "fixed",
            "speaker_roles": ["debater_1"],
        },
        {
            "id": "s2",
            "title": "测试段2",
            "phase": DebatePhase.QUESTIONING,
            "duration": 5,
            "mode": "choice",
            "speaker_roles": ["debater_2", "debater_3"],
        },
    ]

    asyncio.run(flow_controller.start_flow(room_id, segments=segments))
    assert room_state.current_phase == DebatePhase.OPENING
    assert room_state.segment_id == "s1"
    assert room_state.current_speaker == "debater_1"
    assert room_state.speaker_mode == "fixed"

    asyncio.run(flow_controller.advance_segment(room_id))
    assert room_state.current_phase == DebatePhase.QUESTIONING
    assert room_state.segment_id == "s2"
    assert room_state.speaker_mode == "choice"
    assert room_state.current_speaker in room_state.speaker_options

    ok = asyncio.run(flow_controller.set_current_speaker(room_id, "debater_3"))
    assert ok is True
    assert room_state.current_speaker == "debater_3"

    asyncio.run(flow_controller.cleanup_room(room_id))
    room_manager.rooms.pop(room_id, None)


def test_websocket_manager_room_membership():
    room_id = "test_room_ws_mgr_001"
    websocket_manager.room_members[room_id] = {
        "user_001",
        "user_002",
        "user_003",
    }
    websocket_manager.user_rooms["user_001"] = room_id
    websocket_manager.user_rooms["user_002"] = room_id
    websocket_manager.user_rooms["user_003"] = room_id
    websocket_manager.active_connections["user_001"] = [_DummyWebSocket()]
    websocket_manager.active_connections["user_002"] = [_DummyWebSocket()]
    websocket_manager.active_connections["user_003"] = [_DummyWebSocket()]

    connections = websocket_manager.get_room_connections(room_id)
    assert len(connections) == 3
    assert websocket_manager.get_user_room("user_001") == room_id

    asyncio.run(websocket_manager.disconnect("user_001"))
    connections = websocket_manager.get_room_connections(room_id)
    assert len(connections) == 2
    assert "user_001" not in connections
    assert websocket_manager.get_user_room("user_001") is None

    asyncio.run(websocket_manager.disconnect("user_002"))
    asyncio.run(websocket_manager.disconnect("user_003"))
    websocket_manager.active_connections.pop("user_001", None)
    websocket_manager.active_connections.pop("user_002", None)
    websocket_manager.active_connections.pop("user_003", None)


class _DummyWebSocket:
    def __init__(self):
        self.client_state = type("ClientState", (), {"name": "CONNECTED"})()

    async def send_json(self, message):
        return None


class _FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class _FlowTestDB:
    def __init__(self, *, topic="测试辩题", speeches=None):
        self.execute_calls = 0
        self.topic = topic
        self.speeches = list(speeches or [])
        self.added = []
        self.commits = 0

    def execute(self, _stmt):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _FakeResult(SimpleNamespace(id=uuid.uuid4(), topic=self.topic))
        return _FakeResult(list(self.speeches))

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    def commit(self):
        self.commits += 1
        return None

    def rollback(self):
        return None

    def close(self):
        return None

    def get_bind(self):
        return None


async def _fake_get_coze_config(_self):
    return SimpleNamespace(parameters={})


async def _fake_get_tts_config(_self):
    return SimpleNamespace(parameters={"response_format": "mp3"})


async def _noop_notify_speech_committed(*args, **kwargs):
    return None


async def _noop_advance_segment(*args, **kwargs):
    return True


def _cleanup_flow_state(room_id):
    room_manager.rooms.pop(room_id, None)
    task = flow_controller.ai_tasks.pop(room_id, None)
    if task is not None:
        task.cancel()

    draft_tasks = flow_controller.ai_draft_tasks.pop(room_id, None) or {}
    for draft_task in draft_tasks.values():
        draft_task.cancel()

    flow_controller.ai_drafts.pop(room_id, None)
    flow_controller.segments.pop(room_id, None)
    flow_controller.segment_index.pop(room_id, None)
    flow_controller.free_debate_ai_last_speaker.pop(room_id, None)


def _make_flow_test_speech(role, content, *, phase="free_debate", speaker_type=None):
    normalized_role = str(role or "")
    if speaker_type is None:
        speaker_type = "ai" if normalized_role.startswith("ai_") else "human"
    return SimpleNamespace(
        id=uuid.uuid4(),
        speaker_role=normalized_role,
        speaker_type=speaker_type,
        phase=phase,
        content=content,
    )


def test_force_advance_waits_for_voice_processing():
    room_id = "test_room_turn_gate_001"
    debate_id = str(uuid.uuid4())

    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.WAITING,
    )
    room_manager.rooms[room_id] = room_state

    segments = [
        {
            "id": "s1",
            "title": "测试段1",
            "phase": DebatePhase.OPENING,
            "duration": 5,
            "mode": "fixed",
            "speaker_roles": ["debater_1"],
        },
        {
            "id": "s2",
            "title": "测试段2",
            "phase": DebatePhase.OPENING,
            "duration": 5,
            "mode": "fixed",
            "speaker_roles": ["debater_2"],
        },
    ]

    asyncio.run(flow_controller.start_flow(room_id, segments=segments))
    assert room_state.segment_id == "s1"

    room_state.turn_processing_status = "processing"
    room_state.turn_processing_kind = "asr"
    ok = asyncio.run(flow_controller.force_advance_segment(room_id, reason="end_turn"))
    assert ok is True
    assert room_state.segment_id == "s1"
    assert room_state.pending_advance_reason == "end_turn"

    room_state.turn_processing_status = "failed"
    room_state.turn_processing_kind = "asr"
    room_state.turn_processing_error = "ASR失败"
    ok = asyncio.run(flow_controller.force_advance_segment(room_id, reason="end_turn"))
    assert ok is False
    assert room_state.segment_id == "s1"

    ok = asyncio.run(
        flow_controller.force_advance_segment(room_id, reason="host_advance")
    )
    assert ok is True
    assert room_state.segment_id == "s2"

    asyncio.run(flow_controller.cleanup_room(room_id))
    room_manager.rooms.pop(room_id, None)


def test_ai_response_turn_without_question_is_skippable():
    turn_plan = {
        "speech_type": "response",
        "dependency_scope": "last_opponent_question",
    }

    assert flow_controller._should_skip_ai_turn_without_dependency(
        "questioning_2_neg_answer",
        turn_plan,
        [],
    )
    assert not flow_controller._should_skip_ai_turn_without_dependency(
        "questioning_2_neg_answer",
        turn_plan,
        [_make_flow_test_speech("debater_2", "这是一个有效提问")],
    )


def test_free_debate_ai_speaker_rotates_away_from_last_ai():
    room_id = "test_room_free_debate_rotation_001"
    room_state = RoomState(room_id=room_id, debate_id=str(uuid.uuid4()))
    room_state.ai_debaters = [
        {"id": "ai_1"},
        {"id": "ai_2"},
        {"id": "ai_3"},
        {"id": "ai_4"},
    ]

    selected = flow_controller._select_free_debate_ai_speaker(
        [
            _make_flow_test_speech("ai_1", "上一位 AI 发言"),
            _make_flow_test_speech("debater_1", "人类刚刚发言"),
        ],
        room_state,
    )

    assert selected in {"ai_2", "ai_3", "ai_4"}


def test_ai_turn_plan_prefers_eager_questions_and_fast_responses():
    room_state = RoomState(room_id="test_room_ai_plan_001", debate_id=str(uuid.uuid4()))

    opening_plan = flow_controller.resolve_ai_turn_plan(
        {
            "id": "opening_negative_1",
            "phase": DebatePhase.OPENING,
            "mode": "fixed",
            "speaker_roles": ["ai_1"],
        },
        room_state,
        coze_parameters={},
    )
    question_plan = flow_controller.resolve_ai_turn_plan(
        {
            "id": "questioning_3_ai3_ask",
            "phase": DebatePhase.QUESTIONING,
            "mode": "fixed",
            "speaker_roles": ["ai_3"],
        },
        room_state,
        coze_parameters={},
    )
    answer_plan = flow_controller.resolve_ai_turn_plan(
        {
            "id": "questioning_2_neg_answer",
            "phase": DebatePhase.QUESTIONING,
            "mode": "choice",
            "speaker_roles": ["ai_2", "ai_3"],
        },
        room_state,
        coze_parameters={},
    )

    assert opening_plan["prethinking_mode"] == "eager"
    assert opening_plan["response_delay_sec"] == 0
    assert question_plan["prethinking_mode"] == "eager"
    assert question_plan["response_delay_sec"] == 0
    assert answer_plan["prethinking_mode"] == "reactive"
    assert answer_plan["response_delay_sec"] == 0
    assert answer_plan["thinking_timeout_sec"] <= 8


def test_ai_question_without_opponent_arguments_uses_topic_based_prompt(monkeypatch):
    captured = {}

    async def _fake_call_agent(self, prompt, context=None, stream_callback=None):
        captured["prompt"] = prompt
        captured["context"] = context
        return "请问你方如何证明这个核心前提在现实中始终成立？"

    monkeypatch.setattr(AIDebaterAgent, "_call_agent", _fake_call_agent)

    agent = AIDebaterAgent(position=2, db=SimpleNamespace())
    result = asyncio.run(
        agent.generate_question(
            topic="人工智能是否应该全面进入课堂教学",
            stance="negative",
            context=[],
            opponent_arguments=[],
        )
    )

    assert result
    assert "不需要等待对方先发言" in captured["prompt"]
    assert "预判正方" in captured["prompt"]
    assert "引用不存在的上一轮发言" in captured["prompt"]
    assert "对方（正方）的主要论点" not in captured["prompt"]


def test_topic_only_ai_turn_has_local_fallback_when_model_is_slow():
    text = flow_controller._build_topic_only_fallback_text(
        topic="人工智能是否应该全面进入课堂教学",
        stance="negative",
        speech_type="opening",
        speaker_role="ai_1",
    )

    assert "人工智能是否应该全面进入课堂教学" in text
    assert "反方" in text
    assert len(text) <= AIDebaterAgent.MAX_REPLY_CHARS


def test_ai_turn_missing_dependency_waits_until_segment_timeout():
    room_id = "test_room_ai_missing_dependency_wait_001"
    debate_id = str(uuid.uuid4())

    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.QUESTIONING,
        current_speaker="ai_2",
        segment_index=0,
        segment_id="questioning_2_neg_answer",
        segment_title="AI回答",
        turn_processing_status="processing",
        turn_processing_kind="llm",
        ai_turn_status="thinking",
        ai_turn_segment_id="questioning_2_neg_answer",
        ai_turn_speaker_role="ai_2",
    )
    room_manager.rooms[room_id] = room_state
    flow_controller.segments[room_id] = [
        {
            "id": "questioning_2_neg_answer",
            "title": "AI回答",
            "phase": DebatePhase.QUESTIONING,
            "duration": 1,
            "mode": "fixed",
            "speaker_roles": ["ai_2"],
        },
        {
            "id": "questioning_3_ai3_ask",
            "title": "AI提问",
            "phase": DebatePhase.QUESTIONING,
            "duration": 1,
            "mode": "fixed",
            "speaker_roles": ["ai_3"],
        },
    ]
    flow_controller.segment_index[room_id] = 0

    async def _run_missing_dependency():
        try:
            await flow_controller._skip_ai_turn_due_to_missing_dependency(
                room_id,
                segment=flow_controller.segments[room_id][0],
                speaker_role="ai_2",
            )
            assert room_state.segment_id == "questioning_2_neg_answer"
            assert room_state.turn_processing_status == "processing"
            assert room_state.turn_processing_kind == "llm"
            assert room_state.ai_turn_status == "thinking"

            await flow_controller.handle_segment_timeout(room_id)
        finally:
            await flow_controller.cleanup_room(room_id)
            room_manager.rooms.pop(room_id, None)

    asyncio.run(_run_missing_dependency())

    assert room_state.segment_id == "questioning_3_ai3_ask"
    assert room_state.turn_processing_status == "idle"
    assert room_state.ai_turn_status == "idle"


def test_segment_timeout_forces_past_stuck_ai_thinking():
    room_id = "test_room_ai_timeout_force_advance_001"
    debate_id = str(uuid.uuid4())

    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.QUESTIONING,
        current_speaker="ai_2",
        segment_index=0,
        segment_id="questioning_2_neg_answer",
        segment_title="AI回答",
        turn_processing_status="processing",
        turn_processing_kind="llm",
        ai_turn_status="thinking",
        ai_turn_segment_id="questioning_2_neg_answer",
        ai_turn_speaker_role="ai_2",
    )
    room_manager.rooms[room_id] = room_state
    flow_controller.segments[room_id] = [
        {
            "id": "questioning_2_neg_answer",
            "title": "AI回答",
            "phase": DebatePhase.QUESTIONING,
            "duration": 1,
            "mode": "choice",
            "speaker_roles": ["ai_2", "ai_3"],
        },
        {
            "id": "questioning_3_ai3_ask",
            "title": "AI提问",
            "phase": DebatePhase.QUESTIONING,
            "duration": 1,
            "mode": "fixed",
            "speaker_roles": ["ai_3"],
        },
    ]
    flow_controller.segment_index[room_id] = 0

    async def _sleep_forever():
        await asyncio.Event().wait()

    async def _run_timeout():
        task = asyncio.create_task(_sleep_forever())
        flow_controller.ai_tasks[room_id] = task
        try:
            await flow_controller.handle_segment_timeout(room_id)
            return task
        finally:
            await flow_controller.cleanup_room(room_id)
            room_manager.rooms.pop(room_id, None)

    task = asyncio.run(_run_timeout())

    assert room_state.segment_id == "questioning_3_ai3_ask"
    assert room_state.turn_processing_status == "idle"
    assert task.cancelled()


def test_failed_ai_turn_waits_until_segment_timeout_before_advance():
    room_id = "test_room_ai_generation_failure_recover_001"
    debate_id = str(uuid.uuid4())

    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
        current_speaker="ai_1",
        segment_index=0,
        segment_id="opening_negative_1",
        segment_title="AI立论",
        turn_processing_status="processing",
        turn_processing_kind="llm",
        ai_turn_status="thinking",
        ai_turn_segment_id="opening_negative_1",
        ai_turn_speaker_role="ai_1",
    )
    room_manager.rooms[room_id] = room_state
    flow_controller.segments[room_id] = [
        {
            "id": "opening_negative_1",
            "title": "AI立论",
            "phase": DebatePhase.OPENING,
            "duration": 1,
            "mode": "fixed",
            "speaker_roles": ["ai_1"],
        },
        {
            "id": "opening_positive_2",
            "title": "正方二辩",
            "phase": DebatePhase.OPENING,
            "duration": 1,
            "mode": "fixed",
            "speaker_roles": ["debater_2"],
        },
    ]
    flow_controller.segment_index[room_id] = 0

    async def _run_recovery():
        try:
            await flow_controller._recover_failed_ai_turn(
                room_id,
                flow_controller.segments[room_id][0],
                speaker_role="ai_1",
                turn_processing_kind="llm",
                error=TimeoutError(),
            )
            assert room_state.segment_id == "opening_negative_1"
            assert room_state.turn_processing_status == "processing"
            assert room_state.turn_processing_kind == "llm"
            assert room_state.ai_turn_status == "thinking"

            await flow_controller.handle_segment_timeout(room_id)
        finally:
            await flow_controller.cleanup_room(room_id)
            room_manager.rooms.pop(room_id, None)

    asyncio.run(_run_recovery())

    assert room_state.segment_id == "opening_positive_2"
    assert room_state.turn_processing_status == "idle"
    assert room_state.ai_turn_status == "idle"


def test_prepare_ai_draft_does_not_commit_speech_before_release(monkeypatch):
    from services import flow_controller as fc

    room_id = "test_room_prepare_draft_001"
    debate_id = str(uuid.uuid4())
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
        current_speaker="ai_1",
        segment_index=1,
        segment_id="opening_negative_1",
        segment_title="立论阶段：反方一辩",
        speaker_mode="fixed",
    )
    room_state.ai_debaters = [
        {"id": "ai_1", "name": "AI一辩", "stance": "negative"}
    ]
    room_manager.rooms[room_id] = room_state

    segment = {
        "id": "opening_negative_1",
        "title": "立论阶段：反方一辩",
        "phase": DebatePhase.OPENING,
        "duration": 180,
        "mode": "fixed",
        "speaker_roles": ["ai_1"],
    }
    fake_db = _FlowTestDB()

    async def _fake_generate_speech_with_audio(self, **kwargs):
        return {
            "text": "预思考草稿",
            "audio_data": None,
            "duration": 2,
            "voice_id": "Cherry",
        }

    monkeypatch.setattr(fc.ConfigService, "get_tts_config", _fake_get_tts_config)
    monkeypatch.setattr(
        AIDebaterAgent,
        "generate_speech_with_audio",
        _fake_generate_speech_with_audio,
    )

    turn_plan = fc.flow_controller.resolve_ai_turn_plan(
        segment,
        room_state,
        coze_parameters={},
    )

    try:
        draft = asyncio.run(
            fc.flow_controller.prepare_ai_draft(
                room_id=room_id,
                segment=segment,
                room_state=room_state,
                turn_plan=turn_plan,
                db=fake_db,
                debate=SimpleNamespace(topic="测试辩题"),
                recent_speeches=[],
            )
        )
        cached = fc.flow_controller._get_ai_draft(
            room_id,
            segment_id="opening_negative_1",
            speaker_role="ai_1",
        )

        assert draft["status"] == "ready"
        assert draft["draft_text"] == "预思考草稿"
        assert cached is not None
        assert cached["status"] == "ready"
        assert cached["speech_id"] is None
        assert fake_db.added == []
        assert fake_db.commits == 0
    finally:
        _cleanup_flow_state(room_id)


def test_sync_upcoming_ai_prethinking_prepares_eager_draft_without_broadcast(
    monkeypatch,
):
    from services import flow_controller as fc

    room_id = "test_room_eager_prethinking_001"
    debate_id = str(uuid.uuid4())
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
        current_speaker="debater_1",
        segment_index=0,
        segment_id="opening_positive_1",
        segment_title="立论阶段：正方一辩",
        speaker_mode="fixed",
    )
    room_state.ai_debaters = [
        {"id": "ai_1", "name": "AI一辩", "stance": "negative"}
    ]
    room_manager.rooms[room_id] = room_state

    segments = [
        {
            "id": "opening_positive_1",
            "title": "立论阶段：正方一辩",
            "phase": DebatePhase.OPENING,
            "duration": 180,
            "mode": "fixed",
            "speaker_roles": ["debater_1"],
        },
        {
            "id": "opening_negative_1",
            "title": "立论阶段：反方一辩",
            "phase": DebatePhase.OPENING,
            "duration": 180,
            "mode": "fixed",
            "speaker_roles": ["ai_1"],
        },
    ]
    fake_db = _FlowTestDB()
    broadcasted = []

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    async def _fake_generate_speech_with_audio(self, **kwargs):
        return {
            "text": "提前准备好的开篇陈词",
            "audio_data": None,
            "duration": 2,
            "voice_id": "Cherry",
        }

    monkeypatch.setattr(fc.websocket_manager, "broadcast_to_room", _fake_broadcast_to_room)
    monkeypatch.setattr(fc.room_manager, "update_room_state", _fake_update_room_state)
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(fc.ConfigService, "get_coze_config", _fake_get_coze_config)
    monkeypatch.setattr(fc.ConfigService, "get_tts_config", _fake_get_tts_config)
    monkeypatch.setattr(
        AIDebaterAgent,
        "generate_speech_with_audio",
        _fake_generate_speech_with_audio,
    )

    fc.flow_controller.segments[room_id] = segments
    fc.flow_controller.segment_index[room_id] = 0

    async def _run_prethinking():
        await fc.flow_controller._sync_upcoming_ai_prethinking(room_id)
        pending_tasks = list(
            (fc.flow_controller.ai_draft_tasks.get(room_id) or {}).values()
        )
        if pending_tasks:
            await asyncio.gather(*pending_tasks)

    try:
        asyncio.run(_run_prethinking())
        cached = fc.flow_controller._get_ai_draft(
            room_id,
            segment_id="opening_negative_1",
            speaker_role="ai_1",
        )

        assert room_state.ai_turn_status == "ready"
        assert room_state.ai_turn_segment_id == "opening_negative_1"
        assert room_state.ai_turn_speaker_role == "ai_1"
        assert cached is not None
        assert cached["status"] == "ready"
        assert cached["draft_text"] == "提前准备好的开篇陈词"
        assert fake_db.added == []
        assert broadcasted == []
    finally:
        _cleanup_flow_state(room_id)


def test_run_ai_turn_releases_cached_draft_after_response_delay(monkeypatch):
    from services import flow_controller as fc

    room_id = "test_room_cached_release_001"
    debate_id = str(uuid.uuid4())
    segment = {
        "id": "opening_negative_1",
        "title": "立论阶段：反方一辩",
        "phase": DebatePhase.OPENING,
        "duration": 180,
        "mode": "fixed",
        "speaker_roles": ["ai_1"],
    }
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
        current_speaker="ai_1",
        segment_index=1,
        segment_id="opening_negative_1",
        segment_title="立论阶段：反方一辩",
        segment_start_time=fc.flow_controller._now(),
        speaker_mode="fixed",
    )
    room_state.ai_debaters = [
        {"id": "ai_1", "name": "AI一辩", "stance": "negative"}
    ]
    room_manager.rooms[room_id] = room_state

    fc.flow_controller.segments[room_id] = [
        {
            "id": "opening_positive_1",
            "title": "立论阶段：正方一辩",
            "phase": DebatePhase.OPENING,
            "duration": 180,
            "mode": "fixed",
            "speaker_roles": ["debater_1"],
        },
        segment,
    ]
    fc.flow_controller.segment_index[room_id] = 1

    fake_db = _FlowTestDB()
    broadcasted = []
    sleep_calls = []

    turn_plan = fc.flow_controller.resolve_ai_turn_plan(
        segment,
        room_state,
        coze_parameters={},
    )
    dependency_signature = fc.flow_controller._build_turn_dependency_signature(
        turn_plan,
        [],
        "ai_1",
        segment_id="opening_negative_1",
    )
    cached_draft = fc.flow_controller._build_empty_ai_draft(
        room_id=room_id,
        segment_id="opening_negative_1",
        segment_title="立论阶段：反方一辩",
        speaker_role="ai_1",
        speech_type=str(turn_plan.get("speech_type") or "opening"),
        dependency_scope=str(turn_plan.get("dependency_scope") or "topic_and_knowledge"),
    )
    cached_draft.update(
        {
            "status": "ready",
            "dependency_signature": dependency_signature,
            "draft_text": "缓存草稿",
            "voice_id": "Cherry",
            "configured_audio_format": "mp3",
            "ready_at": fc.flow_controller._now(),
            "release_not_before": fc.flow_controller._now(),
            "error": None,
        }
    )
    fc.flow_controller._store_ai_draft(room_id, cached_draft)

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)
        return None

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    async def _unexpected_generate_speech_with_audio(self, **kwargs):
        raise AssertionError("run_ai_turn should reuse the cached draft")

    async def _fake_synthesize_speech_live(*args, **kwargs):
        text_source = kwargs["text_source"]
        collected = []
        async for text_chunk in text_source:
            collected.append(text_chunk)
        return {
            "audio_data": b"fake-audio",
            "audio_format": "wav",
            "chunk_count": len(collected),
            "used_streaming": True,
            "sample_rate": 24000,
            "channels": 1,
            "sample_width": 2,
        }

    async def _fake_save_audio_file(*args, **kwargs):
        return "uploads/audio/cached-draft.wav"

    monkeypatch.setattr(fc.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(fc.websocket_manager, "broadcast_to_room", _fake_broadcast_to_room)
    monkeypatch.setattr(fc.room_manager, "update_room_state", _fake_update_room_state)
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(fc.ConfigService, "get_coze_config", _fake_get_coze_config)
    monkeypatch.setattr(fc.ConfigService, "get_tts_config", _fake_get_tts_config)
    monkeypatch.setattr(
        fc.flow_controller,
        "notify_speech_committed",
        _noop_notify_speech_committed,
    )
    monkeypatch.setattr(fc.flow_controller, "advance_segment", _noop_advance_segment)
    monkeypatch.setattr(
        AIDebaterAgent,
        "generate_speech_with_audio",
        _unexpected_generate_speech_with_audio,
    )
    monkeypatch.setattr(
        fc.voice_processor,
        "synthesize_speech_stream_live",
        _fake_synthesize_speech_live,
    )
    monkeypatch.setattr(
        fc.voice_processor,
        "save_audio_file",
        _fake_save_audio_file,
    )
    monkeypatch.setattr(
        fc.voice_processor,
        "build_audio_url",
        lambda _path: "/uploads/audio/cached-draft.wav",
    )

    try:
        asyncio.run(fc.flow_controller._run_ai_turn(room_id, segment))
        speech_messages = [m for m in broadcasted if m.get("type") == "speech"]
        cached = fc.flow_controller._get_ai_draft(
            room_id,
            segment_id="opening_negative_1",
            speaker_role="ai_1",
        )

        assert sleep_calls[0] == 0.3
        assert any(delay >= 2.5 for delay in sleep_calls[1:])
        assert len(speech_messages) == 2
        assert speech_messages[0]["data"]["content"] == "缓存草稿"
        assert speech_messages[0]["data"]["audio_url"] is None
        assert speech_messages[1]["data"]["audio_url"] == "/uploads/audio/cached-draft.wav"
        assert speech_messages[1]["data"]["audio_format"] == "wav"
        assert speech_messages[0]["data"]["speech_id"] == speech_messages[1]["data"]["speech_id"]
        assert cached is not None
        assert cached["status"] == "released"
        assert cached["speech_id"] == speech_messages[0]["data"]["speech_id"]
        assert len(fake_db.added) == 1
        assert fake_db.added[0].content == "缓存草稿"
    finally:
        _cleanup_flow_state(room_id)


def test_trigger_free_debate_ai_turn_waits_for_draft_before_grabbing_mic(monkeypatch):
    from services import flow_controller as fc

    room_id = "test_room_free_debate_ai_001"
    debate_id = str(uuid.uuid4())
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.FREE_DEBATE,
        current_speaker=None,
        segment_index=12,
        segment_id="free_debate",
        segment_title="自由辩论",
        speaker_mode="free",
        free_debate_next_side="ai",
    )
    room_state.ai_debaters = [
        {"id": "ai_1", "name": "AI一辩", "stance": "negative"},
        {"id": "ai_2", "name": "AI二辩", "stance": "negative"},
    ]
    room_manager.rooms[room_id] = room_state

    fake_db = _FlowTestDB(
        speeches=[
            _make_flow_test_speech("debater_1", "这是刚刚结束的人类发言"),
            _make_flow_test_speech("debater_2", "更早一点的人类补充"),
            _make_flow_test_speech("ai_1", "我方上一轮 AI 回应"),
        ]
    )
    broadcasted = []
    events = []
    captured_recent_speeches = []

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)
        events.append(message.get("type"))

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    async def _fake_generate_speech_with_audio(self, **kwargs):
        events.append("llm_generation")
        assert room_state.current_speaker is None
        assert room_state.mic_owner_user_id is None
        assert room_state.mic_owner_role is None
        assert room_state.ai_turn_status == "thinking"
        captured_recent_speeches.extend(kwargs.get("recent_speeches") or [])
        return {
            "text": "这是自由辩 AI 回应",
            "audio_data": None,
            "duration": 2,
            "voice_id": "Cherry",
        }

    async def _fake_synthesize_speech_stream_live(*args, **kwargs):
        text_source = kwargs["text_source"]
        collected = []
        async for text_chunk in text_source:
            collected.append(text_chunk)
        return {
            "audio_data": b"fake-audio",
            "audio_format": "wav",
            "chunk_count": len(collected),
            "used_streaming": True,
            "sample_rate": 24000,
            "channels": 1,
            "sample_width": 2,
        }

    async def _fake_save_audio_file(*args, **kwargs):
        return "uploads/audio/free-debate-ai.wav"

    monkeypatch.setattr(fc.websocket_manager, "broadcast_to_room", _fake_broadcast_to_room)
    monkeypatch.setattr(fc.room_manager, "update_room_state", _fake_update_room_state)
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(fc.ConfigService, "get_coze_config", _fake_get_coze_config)
    monkeypatch.setattr(fc.ConfigService, "get_tts_config", _fake_get_tts_config)
    monkeypatch.setattr(
        fc.flow_controller,
        "notify_speech_committed",
        _noop_notify_speech_committed,
    )
    monkeypatch.setattr(
        AIDebaterAgent,
        "generate_speech_with_audio",
        _fake_generate_speech_with_audio,
    )
    monkeypatch.setattr(
        fc.voice_processor,
        "synthesize_speech_stream_live",
        _fake_synthesize_speech_stream_live,
    )
    monkeypatch.setattr(fc.voice_processor, "save_audio_file", _fake_save_audio_file)
    monkeypatch.setattr(
        fc.voice_processor,
        "build_audio_url",
        lambda _path: "/uploads/audio/free-debate-ai.wav",
    )

    try:
        asyncio.run(fc.flow_controller.trigger_free_debate_ai_turn(room_id))
        speech_messages = [m for m in broadcasted if m.get("type") == "speech"]

        assert "llm_generation" in events
        assert "mic_grabbed" in events
        assert events.index("llm_generation") < events.index("mic_grabbed")
        assert any(item.get("speaker") == "debater_1" for item in captured_recent_speeches)
        assert any(item.get("speaker") == "ai_1" for item in captured_recent_speeches)
        assert len(speech_messages) == 2
        assert speech_messages[0]["data"]["content"] == "这是自由辩 AI 回应"
        assert room_state.free_debate_next_side == "ai"
        assert room_state.mic_owner_user_id == "__ai__"
        assert str(room_state.current_speaker or "").startswith("ai_")
        assert room_state.ai_turn_status == "speaking"
        assert room_state.playback_gate_status == "waiting"
    finally:
        _cleanup_flow_state(room_id)


def test_run_ai_turn_waits_for_playback_finished_before_advancing(monkeypatch):
    from services import flow_controller as fc

    room_id = "test_room_playback_gate_fixed_001"
    debate_id = str(uuid.uuid4())
    segment = {
        "id": "opening_negative_1",
        "title": "立论阶段：反方一辩",
        "phase": DebatePhase.OPENING,
        "duration": 180,
        "mode": "fixed",
        "speaker_roles": ["ai_1"],
    }
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
        current_speaker="ai_1",
        segment_index=1,
        segment_id="opening_negative_1",
        segment_title="立论阶段：反方一辩",
        segment_start_time=fc.flow_controller._now(),
        speaker_mode="fixed",
    )
    room_state.participants = [
        {
            "user_id": "controller-001",
            "role": "debater_1",
            "name": "主持人",
        }
    ]
    room_state.ai_debaters = [
        {"id": "ai_1", "name": "AI一辩", "stance": "negative"}
    ]
    room_manager.rooms[room_id] = room_state

    fc.flow_controller.segments[room_id] = [
        {
            "id": "opening_positive_1",
            "title": "立论阶段：正方一辩",
            "phase": DebatePhase.OPENING,
            "duration": 180,
            "mode": "fixed",
            "speaker_roles": ["debater_1"],
        },
        segment,
    ]
    fc.flow_controller.segment_index[room_id] = 1

    fake_db = _FlowTestDB()
    broadcasted = []
    advance_calls = []

    async def _fake_sleep(_seconds):
        return None

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    async def _fake_advance_segment(_room_id):
        advance_calls.append(_room_id)
        return True

    async def _fake_generate_speech_with_audio(self, **kwargs):
        return {
            "text": "这是需要等待播放结束的 AI 发言",
            "audio_data": None,
            "duration": 2,
            "voice_id": "Cherry",
        }

    async def _fake_synthesize_speech_stream_live(*args, **kwargs):
        text_source = kwargs["text_source"]
        async for _ in text_source:
            pass
        return {
            "audio_data": b"fake-audio",
            "audio_format": "wav",
            "chunk_count": 1,
            "used_streaming": True,
            "sample_rate": 24000,
            "channels": 1,
            "sample_width": 2,
        }

    async def _fake_save_audio_file(*args, **kwargs):
        return "uploads/audio/playback-gate.wav"

    monkeypatch.setattr(fc.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(fc.websocket_manager, "broadcast_to_room", _fake_broadcast_to_room)
    monkeypatch.setattr(fc.room_manager, "update_room_state", _fake_update_room_state)
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(fc.ConfigService, "get_coze_config", _fake_get_coze_config)
    monkeypatch.setattr(fc.ConfigService, "get_tts_config", _fake_get_tts_config)
    monkeypatch.setattr(fc.flow_controller, "notify_speech_committed", _noop_notify_speech_committed)
    monkeypatch.setattr(fc.flow_controller, "advance_segment", _fake_advance_segment)
    monkeypatch.setattr(AIDebaterAgent, "generate_speech_with_audio", _fake_generate_speech_with_audio)
    monkeypatch.setattr(fc.voice_processor, "synthesize_speech_stream_live", _fake_synthesize_speech_stream_live)
    monkeypatch.setattr(fc.voice_processor, "save_audio_file", _fake_save_audio_file)
    monkeypatch.setattr(fc.voice_processor, "build_audio_url", lambda _path: "/uploads/audio/playback-gate.wav")

    try:
        asyncio.run(fc.flow_controller._run_ai_turn(room_id, segment))
        speech_messages = [m for m in broadcasted if m.get("type") == "speech"]
        speech_id = speech_messages[0]["data"]["speech_id"]

        assert advance_calls == []
        assert room_state.segment_id == "opening_negative_1"
        assert room_state.playback_gate_status == "waiting"
        assert room_state.playback_gate_speech_id == speech_id
        assert room_state.playback_gate_controller_user_id == "controller-001"

        asyncio.run(
            fc.flow_controller.handle_speech_playback_started(
                room_id,
                "controller-001",
                {"speech_id": speech_id, "segment_id": "opening_negative_1", "speaker_role": "ai_1"},
            )
        )
        assert room_state.playback_gate_status == "playing"

        asyncio.run(
            fc.flow_controller.handle_speech_playback_finished(
                room_id,
                "controller-001",
                {"speech_id": speech_id},
            )
        )

        assert advance_calls == [room_id]
        assert room_state.playback_gate_status == "idle"
        assert room_state.playback_gate_speech_id is None
    finally:
        _cleanup_flow_state(room_id)


def test_free_debate_ai_releases_mic_after_playback_finished(monkeypatch):
    from services import flow_controller as fc

    room_id = "test_room_playback_gate_free_001"
    debate_id = str(uuid.uuid4())
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.FREE_DEBATE,
        current_speaker=None,
        segment_index=12,
        segment_id="free_debate",
        segment_title="自由辩论",
        segment_start_time=fc.flow_controller._now(),
        speaker_mode="free",
        free_debate_next_side="ai",
    )
    room_state.participants = [
        {
            "user_id": "controller-001",
            "role": "debater_1",
            "name": "主持人",
        }
    ]
    room_state.ai_debaters = [
        {"id": "ai_1", "name": "AI一辩", "stance": "negative"},
        {"id": "ai_2", "name": "AI二辩", "stance": "negative"},
    ]
    room_manager.rooms[room_id] = room_state

    fake_db = _FlowTestDB(
        speeches=[
            _make_flow_test_speech("debater_1", "这是刚刚结束的人类发言"),
            _make_flow_test_speech("ai_1", "我方上一轮 AI 回应"),
        ]
    )
    broadcasted = []

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    async def _fake_generate_speech_with_audio(self, **kwargs):
        return {
            "text": "这是自由辩 AI 回应",
            "audio_data": None,
            "duration": 2,
            "voice_id": "Cherry",
        }

    async def _fake_synthesize_speech_stream_live(*args, **kwargs):
        text_source = kwargs["text_source"]
        async for _ in text_source:
            pass
        return {
            "audio_data": b"fake-audio",
            "audio_format": "wav",
            "chunk_count": 1,
            "used_streaming": True,
            "sample_rate": 24000,
            "channels": 1,
            "sample_width": 2,
        }

    async def _fake_save_audio_file(*args, **kwargs):
        return "uploads/audio/free-playback-gate.wav"

    monkeypatch.setattr(fc.websocket_manager, "broadcast_to_room", _fake_broadcast_to_room)
    monkeypatch.setattr(fc.room_manager, "update_room_state", _fake_update_room_state)
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(fc.ConfigService, "get_coze_config", _fake_get_coze_config)
    monkeypatch.setattr(fc.ConfigService, "get_tts_config", _fake_get_tts_config)
    monkeypatch.setattr(fc.flow_controller, "notify_speech_committed", _noop_notify_speech_committed)
    monkeypatch.setattr(AIDebaterAgent, "generate_speech_with_audio", _fake_generate_speech_with_audio)
    monkeypatch.setattr(fc.voice_processor, "synthesize_speech_stream_live", _fake_synthesize_speech_stream_live)
    monkeypatch.setattr(fc.voice_processor, "save_audio_file", _fake_save_audio_file)
    monkeypatch.setattr(fc.voice_processor, "build_audio_url", lambda _path: "/uploads/audio/free-playback-gate.wav")

    try:
        asyncio.run(fc.flow_controller.trigger_free_debate_ai_turn(room_id))
        speech_messages = [m for m in broadcasted if m.get("type") == "speech"]
        speech_id = speech_messages[0]["data"]["speech_id"]

        assert room_state.mic_owner_user_id == "__ai__"
        assert room_state.playback_gate_status == "waiting"
        assert room_state.free_debate_next_side == "ai"

        asyncio.run(
            fc.flow_controller.handle_speech_playback_finished(
                room_id,
                "controller-001",
                {"speech_id": speech_id},
            )
        )

        assert room_state.playback_gate_status == "idle"
        assert room_state.mic_owner_user_id is None
        assert room_state.current_speaker is None
        assert room_state.free_debate_next_side == "human"
        assert room_state.ai_turn_status == "idle"
    finally:
        _cleanup_flow_state(room_id)


def test_invalidate_context_reactive_draft_updates_recomputing_state(monkeypatch):
    from services import flow_controller as fc

    room_id = "test_room_reactive_invalidation_001"
    debate_id = str(uuid.uuid4())
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.QUESTIONING,
        current_speaker="debater_2",
        segment_index=4,
        segment_id="questioning_2_pos2_ask",
        segment_title="盘问第2轮：正方二辩提问",
        speaker_mode="fixed",
        ai_turn_status="ready",
        ai_turn_segment_id="questioning_2_neg_answer",
        ai_turn_segment_title="盘问第2轮：反方回答",
        ai_turn_speaker_role="ai_2",
    )
    room_manager.rooms[room_id] = room_state
    room_draft = {
        "room_id": room_id,
        "segment_id": "questioning_2_neg_answer",
        "segment_title": "盘问第2轮：反方回答",
        "speaker_role": "ai_2",
        "speech_type": "response",
        "dependency_scope": "last_opponent_question",
        "status": "ready",
        "dependency_signature": "stale-signature",
        "source_speech_ids": [],
        "draft_text": "旧草稿",
        "voice_id": "Cherry",
        "configured_audio_format": "mp3",
        "ready_at": fc.flow_controller._now(),
        "release_not_before": None,
        "released_at": None,
        "speech_id": None,
        "error": None,
    }
    fc.flow_controller._store_ai_draft(room_id, room_draft)

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    monkeypatch.setattr(fc.room_manager, "update_room_state", _fake_update_room_state)

    try:
        asyncio.run(
            fc.flow_controller._invalidate_context_reactive_drafts(
                room_id,
                room_state,
                [
                    _make_flow_test_speech(
                        "debater_2",
                        "最新追问已经提交",
                        phase=str(DebatePhase.QUESTIONING.value),
                    )
                ],
                coze_parameters={},
            )
        )
        cached = fc.flow_controller._get_ai_draft(
            room_id,
            segment_id="questioning_2_neg_answer",
            speaker_role="ai_2",
        )

        assert cached is not None
        assert cached["status"] == "invalidated"
        assert cached["error"] == "dependency_changed"
        assert room_state.ai_turn_status == "recomputing"
        assert room_state.ai_turn_speaker_role == "ai_2"
    finally:
        _cleanup_flow_state(room_id)


def test_cleanup_room_cancels_pending_ai_tasks():
    room_id = "test_room_cleanup_ai_tasks_001"
    debate_id = str(uuid.uuid4())
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
    )
    room_manager.rooms[room_id] = room_state

    async def _sleep_forever():
        await asyncio.Event().wait()

    async def _run_cleanup():
        ai_task = asyncio.create_task(_sleep_forever())
        draft_task = asyncio.create_task(_sleep_forever())
        flow_controller.ai_tasks[room_id] = ai_task
        flow_controller.ai_draft_tasks[room_id] = {
            "opening_negative_1:ai_1": draft_task
        }
        flow_controller.ai_drafts[room_id] = {
            "opening_negative_1:ai_1": {"status": "preparing"}
        }
        await flow_controller.cleanup_room(room_id)
        return ai_task, draft_task

    ai_task, draft_task = asyncio.run(_run_cleanup())

    assert ai_task.cancelled() is True
    assert draft_task.cancelled() is True
    assert room_id not in flow_controller.ai_tasks
    assert room_id not in flow_controller.ai_draft_tasks
    assert room_id not in flow_controller.ai_drafts
    room_manager.rooms.pop(room_id, None)


def test_handle_segment_timeout_cancels_pending_draft_tasks(monkeypatch):
    from services import flow_controller as fc

    room_id = "test_room_timeout_cancel_draft_001"
    debate_id = str(uuid.uuid4())
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
        current_speaker="debater_1",
        segment_index=0,
        segment_id="opening_positive_1",
        segment_title="立论阶段：正方一辩",
        segment_start_time=fc.flow_controller._now(),
        speaker_mode="fixed",
        time_remaining=0,
        segment_time_remaining=0,
    )
    room_manager.rooms[room_id] = room_state

    fc.flow_controller.segments[room_id] = [
        {
            "id": "opening_positive_1",
            "title": "立论阶段：正方一辩",
            "phase": DebatePhase.OPENING,
            "duration": 5,
            "mode": "fixed",
            "speaker_roles": ["debater_1"],
        },
        {
            "id": "opening_positive_2",
            "title": "立论阶段：正方二辩",
            "phase": DebatePhase.OPENING,
            "duration": 5,
            "mode": "fixed",
            "speaker_roles": ["debater_2"],
        },
    ]
    fc.flow_controller.segment_index[room_id] = 0

    async def _fake_broadcast_to_room(_room_id, _message):
        return None

    monkeypatch.setattr(fc.websocket_manager, "broadcast_to_room", _fake_broadcast_to_room)
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: _FlowTestDB())
    monkeypatch.setattr(fc.ConfigService, "get_coze_config", _fake_get_coze_config)

    async def _sleep_forever():
        await asyncio.Event().wait()

    async def _run_timeout():
        draft_task = asyncio.create_task(_sleep_forever())
        fc.flow_controller.ai_draft_tasks[room_id] = {
            "opening_negative_1:ai_1": draft_task
        }
        fc.flow_controller.ai_drafts[room_id] = {
            "opening_negative_1:ai_1": {"status": "preparing"}
        }
        await fc.flow_controller.handle_segment_timeout(room_id)
        return draft_task

    try:
        draft_task = asyncio.run(_run_timeout())

        assert draft_task.cancelled() is True
        assert room_state.segment_id == "opening_positive_2"
        assert room_state.current_speaker == "debater_2"
        assert room_id not in fc.flow_controller.ai_draft_tasks
    finally:
        _cleanup_flow_state(room_id)


def test_audio_transcription_list_normalized_to_string():
    from routers import websocket as ws

    room_id = "test_room_audio_list_001"
    debate_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
    )
    room_state.participants = [
        {
            "user_id": user_id,
            "role": "debater_1",
            "name": "u1",
            "stance": "pro",
        }
    ]
    room_state.current_speaker = "debater_1"
    room_manager.rooms[room_id] = room_state

    class _DummyDB:
        def add(self, obj):
            self._last_added = obj

        def commit(self):
            return None

        def rollback(self):
            return None

    broadcasted = []
    sent = []

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_send_to_user(_user_id, message):
        sent.append(message)

    def _fake_decode_audio_base64(_b64):
        return b"\x00\x01"

    async def _fake_save_audio_file(_data, _filename):
        return None

    async def _fake_transcribe_audio(_data, **kwargs):
        return [
            {
                "sentence_id": 1,
                "begin_time": 2170,
                "end_time": 7810,
                "text": "我方认为未来币的监管与发展是值非常值得肯定的。",
                "channel_id": 0,
                "speaker_id": None,
                "sentence_end": True,
                "words": [],
            }
        ]

    orig_broadcast = ws.websocket_manager.broadcast_to_room
    orig_send = ws.websocket_manager.send_to_user
    orig_decode = ws.voice_processor.decode_audio_base64
    orig_save = ws.voice_processor.save_audio_file
    orig_transcribe = ws.voice_processor.transcribe_audio
    try:
        ws.websocket_manager.broadcast_to_room = _fake_broadcast_to_room
        ws.websocket_manager.send_to_user = _fake_send_to_user
        ws.voice_processor.decode_audio_base64 = _fake_decode_audio_base64
        ws.voice_processor.save_audio_file = _fake_save_audio_file
        ws.voice_processor.transcribe_audio = _fake_transcribe_audio

        asyncio.run(
            ws.handle_audio_message(
                room_id=room_id,
                user_id=user_id,
                data={"audio_data": "xx", "audio_format": "webm"},
                db=_DummyDB(),
            )
        )
    finally:
        ws.websocket_manager.broadcast_to_room = orig_broadcast
        ws.websocket_manager.send_to_user = orig_send
        ws.voice_processor.decode_audio_base64 = orig_decode
        ws.voice_processor.save_audio_file = orig_save
        ws.voice_processor.transcribe_audio = orig_transcribe
        room_manager.rooms.pop(room_id, None)

    speech_messages = [m for m in broadcasted if m.get("type") == "speech"]
    assert len(speech_messages) == 2
    assert speech_messages[0]["data"]["content"] == ""
    assert speech_messages[0]["data"]["audio_url"] is None
    assert isinstance(speech_messages[1]["data"]["content"], str)
    assert "未来币" in speech_messages[1]["data"]["content"]
    assert speech_messages[0]["data"]["speech_id"] == speech_messages[1]["data"]["speech_id"]

    processed = [m for m in sent if m.get("type") == "audio_processed"]
    assert len(processed) == 1
    assert isinstance(processed[0]["data"]["text"], str)
    assert processed[0]["data"]["speech_id"] == speech_messages[1]["data"]["speech_id"]


def test_audio_transcription_dict_text_list_normalized_to_string():
    from routers import websocket as ws

    room_id = "test_room_audio_dict_list_001"
    debate_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
    )
    room_state.participants = [
        {
            "user_id": user_id,
            "role": "debater_1",
            "name": "u1",
            "stance": "pro",
        }
    ]
    room_state.current_speaker = "debater_1"
    room_manager.rooms[room_id] = room_state

    class _DummyDB:
        def add(self, obj):
            self._last_added = obj

        def commit(self):
            return None

        def rollback(self):
            return None

    broadcasted = []
    sent = []

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_send_to_user(_user_id, message):
        sent.append(message)

    def _fake_decode_audio_base64(_b64):
        return b"\x00\x01"

    async def _fake_save_audio_file(_data, _filename):
        return None

    async def _fake_transcribe_audio(_data, **kwargs):
        return {
            "text": [
                {
                    "sentence_id": 1,
                    "begin_time": 2170,
                    "end_time": 7810,
                    "text": "我方认为未来币的监管与发展是非常值得肯定的。",
                }
            ],
            "duration": 0,
            "confidence": 1.0,
        }

    orig_broadcast = ws.websocket_manager.broadcast_to_room
    orig_send = ws.websocket_manager.send_to_user
    orig_decode = ws.voice_processor.decode_audio_base64
    orig_save = ws.voice_processor.save_audio_file
    orig_transcribe = ws.voice_processor.transcribe_audio
    try:
        ws.websocket_manager.broadcast_to_room = _fake_broadcast_to_room
        ws.websocket_manager.send_to_user = _fake_send_to_user
        ws.voice_processor.decode_audio_base64 = _fake_decode_audio_base64
        ws.voice_processor.save_audio_file = _fake_save_audio_file
        ws.voice_processor.transcribe_audio = _fake_transcribe_audio

        asyncio.run(
            ws.handle_audio_message(
                room_id=room_id,
                user_id=user_id,
                data={"audio_data": "xx", "audio_format": "webm"},
                db=_DummyDB(),
            )
        )
    finally:
        ws.websocket_manager.broadcast_to_room = orig_broadcast
        ws.websocket_manager.send_to_user = orig_send
        ws.voice_processor.decode_audio_base64 = orig_decode
        ws.voice_processor.save_audio_file = orig_save
        ws.voice_processor.transcribe_audio = orig_transcribe
        room_manager.rooms.pop(room_id, None)

    speech_messages = [m for m in broadcasted if m.get("type") == "speech"]
    assert len(speech_messages) == 2
    assert speech_messages[0]["data"]["content"] == ""
    assert isinstance(speech_messages[1]["data"]["content"], str)
    assert "未来币" in speech_messages[1]["data"]["content"]
    assert speech_messages[0]["data"]["speech_id"] == speech_messages[1]["data"]["speech_id"]

    processed = [m for m in sent if m.get("type") == "audio_processed"]
    assert len(processed) == 1
    assert isinstance(processed[0]["data"]["text"], str)
    assert processed[0]["data"]["speech_id"] == speech_messages[1]["data"]["speech_id"]


def test_audio_transcription_error_marks_turn_failed():
    from routers import websocket as ws

    room_id = "test_room_audio_error_001"
    debate_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
    )
    room_state.participants = [
        {
            "user_id": user_id,
            "role": "debater_1",
            "name": "u1",
            "stance": "pro",
        }
    ]
    room_state.current_speaker = "debater_1"
    room_manager.rooms[room_id] = room_state

    class _DummyDB:
        def add(self, obj):
            self._last_added = obj

        def commit(self):
            return None

        def rollback(self):
            return None

    broadcasted = []
    sent = []

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_send_to_user(_user_id, message):
        sent.append(message)

    def _fake_decode_audio_base64(_b64):
        return b"\x00\x01"

    async def _fake_save_audio_file(_data, _filename):
        return None

    async def _fake_transcribe_audio(_data, **kwargs):
        return {"error": "ASR service unavailable"}

    orig_broadcast = ws.websocket_manager.broadcast_to_room
    orig_send = ws.websocket_manager.send_to_user
    orig_decode = ws.voice_processor.decode_audio_base64
    orig_save = ws.voice_processor.save_audio_file
    orig_transcribe = ws.voice_processor.transcribe_audio
    try:
        ws.websocket_manager.broadcast_to_room = _fake_broadcast_to_room
        ws.websocket_manager.send_to_user = _fake_send_to_user
        ws.voice_processor.decode_audio_base64 = _fake_decode_audio_base64
        ws.voice_processor.save_audio_file = _fake_save_audio_file
        ws.voice_processor.transcribe_audio = _fake_transcribe_audio

        asyncio.run(
            ws.handle_audio_message(
                room_id=room_id,
                user_id=user_id,
                data={"audio_data": "xx", "audio_format": "webm"},
                db=_DummyDB(),
            )
        )
    finally:
        ws.websocket_manager.broadcast_to_room = orig_broadcast
        ws.websocket_manager.send_to_user = orig_send
        ws.voice_processor.decode_audio_base64 = orig_decode
        ws.voice_processor.save_audio_file = orig_save
        ws.voice_processor.transcribe_audio = orig_transcribe
        room_manager.rooms.pop(room_id, None)

    speech_messages = [m for m in broadcasted if m.get("type") == "speech"]
    assert len(speech_messages) == 1
    assert speech_messages[0]["data"]["content"] == ""
    assert room_state.turn_processing_status == "failed"
    assert room_state.turn_processing_kind == "asr"
    assert room_state.turn_processing_error == "ASR service unavailable"

    error_messages = [m for m in sent if m.get("type") == "error"]
    assert len(error_messages) == 1
    assert "语音识别失败" in error_messages[0]["data"]["message"]
    assert sent[-1]["type"] == "error"


def test_ai_debater_text_is_hard_limited_to_400_chars(monkeypatch):
    """
    验证AI辩手最终输出会被硬限制在400字以内。

    这里直接走 generate_speech_with_audio 主链路，确保限长逻辑不只停留在提示词层。
    """

    class _DummyDB:
        pass

    async def _fake_generate_free_debate_speech(
        self,
        topic,
        stance,
        context,
        recent_speeches,
        stream_callback=None,
    ):
        # 故意返回明显超长文本，模拟模型失控输出。
        return "超长回复" * 150

    async def _fake_synthesize_speech(*args, **kwargs):
        assert kwargs["speed"] is None
        return b"fake-audio"

    monkeypatch.setattr(
        AIDebaterAgent,
        "generate_free_debate_speech",
        _fake_generate_free_debate_speech,
    )
    monkeypatch.setattr(
        "utils.voice_processor.voice_processor.synthesize_speech",
        _fake_synthesize_speech,
    )

    agent = AIDebaterAgent(position=1, db=_DummyDB())
    result = asyncio.run(
        agent.generate_speech_with_audio(
            speech_type="free_debate",
            topic="测试辩题",
            stance="negative",
            context=[],
            recent_speeches=[],
        )
    )

    assert isinstance(result["text"], str)
    assert len(result["text"]) <= AIDebaterAgent.MAX_REPLY_CHARS
    assert result["audio_data"] == b"fake-audio"


def test_ai_turn_broadcasts_text_before_audio(monkeypatch):
    """
    验证AI回合会先广播文本，再使用同一speech_id补发音频更新。
    """
    from services import flow_controller as fc

    room_id = "test_room_ai_turn_realtime_001"
    debate_id = str(uuid.uuid4())
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
        current_speaker="ai_1",
        segment_index=1,
        segment_id="opening_negative_1",
        segment_title="立论阶段：反方一辩",
    )
    room_state.ai_debaters = [{"id": "ai_1", "name": "AI一辩"}]
    room_manager.rooms[room_id] = room_state

    segment = {
        "id": "opening_negative_1",
        "title": "立论阶段：反方一辩",
        "phase": DebatePhase.OPENING,
        "duration": 180,
        "mode": "fixed",
        "speaker_roles": ["ai_1"],
    }

    broadcasted = []
    fake_db = _FlowTestDB()

    async def _fake_sleep(_seconds):
        return None

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    async def _fake_generate_speech_with_audio(self, **kwargs):
        return {
            "text": "这是先到的AI文本",
            "audio_data": None,
            "duration": 2,
            "voice_id": "Cherry",
        }

    async def _fake_synthesize_speech_live(*args, **kwargs):
        assert kwargs["speed"] is None
        text_source = kwargs["text_source"]
        collected = []
        async for text_chunk in text_source:
            collected.append(text_chunk)
        return {
            "audio_data": b"fake-audio",
            "audio_format": "wav",
            "chunk_count": len(collected),
            "used_streaming": True,
            "sample_rate": 24000,
            "channels": 1,
            "sample_width": 2,
        }

    async def _fake_synthesize_speech(*args, **kwargs):
        return b"fake-audio"

    async def _fake_save_audio_file(*args, **kwargs):
        return "uploads/audio/test-ai.mp3"

    monkeypatch.setattr(fc.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(fc.websocket_manager, "broadcast_to_room", _fake_broadcast_to_room)
    monkeypatch.setattr(fc.room_manager, "update_room_state", _fake_update_room_state)
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(fc.ConfigService, "get_coze_config", _fake_get_coze_config)
    monkeypatch.setattr(fc.ConfigService, "get_tts_config", _fake_get_tts_config)
    monkeypatch.setattr(
        fc.flow_controller,
        "notify_speech_committed",
        _noop_notify_speech_committed,
    )
    monkeypatch.setattr(fc.flow_controller, "advance_segment", _noop_advance_segment)
    monkeypatch.setattr(AIDebaterAgent, "generate_speech_with_audio", _fake_generate_speech_with_audio)
    monkeypatch.setattr(fc.voice_processor, "synthesize_speech_stream_live", _fake_synthesize_speech_live)
    monkeypatch.setattr(fc.voice_processor, "synthesize_speech", _fake_synthesize_speech)
    monkeypatch.setattr(fc.voice_processor, "save_audio_file", _fake_save_audio_file)
    monkeypatch.setattr(fc.voice_processor, "build_audio_url", lambda _path: "/uploads/audio/test-ai.mp3")

    try:
        asyncio.run(fc.flow_controller._run_ai_turn(room_id, segment))
    finally:
        room_manager.rooms.pop(room_id, None)

    speech_messages = [m for m in broadcasted if m.get("type") == "speech"]
    assert len(speech_messages) == 2
    assert speech_messages[0]["data"]["content"] == "这是先到的AI文本"
    assert speech_messages[0]["data"]["audio_url"] is None
    assert speech_messages[1]["data"]["content"] == "这是先到的AI文本"
    assert speech_messages[1]["data"]["audio_url"] == "/uploads/audio/test-ai.mp3"
    assert speech_messages[0]["data"]["speech_id"] == speech_messages[1]["data"]["speech_id"]


def test_ai_turn_broadcasts_realtime_tts_chunks(monkeypatch):
    from services import flow_controller as fc

    room_id = "test_room_ai_turn_stream_chunks_001"
    debate_id = str(uuid.uuid4())
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
        current_speaker="ai_1",
        segment_index=1,
        segment_id="opening_negative_1",
        segment_title="测试段落",
    )
    room_state.ai_debaters = [{"id": "ai_1", "name": "AI一辩"}]
    room_manager.rooms[room_id] = room_state

    segment = {
        "id": "opening_negative_1",
        "title": "测试段落",
        "phase": DebatePhase.OPENING,
        "duration": 180,
        "mode": "fixed",
        "speaker_roles": ["ai_1"],
    }

    broadcasted = []
    fake_db = _FlowTestDB()

    async def _fake_sleep(_seconds):
        return None

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    async def _fake_generate_speech_with_audio(self, **kwargs):
        return {
            "text": "这是先到的AI文本",
            "audio_data": None,
            "duration": 2,
            "voice_id": "Cherry",
        }

    async def _fake_synthesize_speech_stream_live(*args, **kwargs):
        assert kwargs["speed"] is None
        text_source = kwargs["text_source"]
        collected = []
        async for text_chunk in text_source:
            collected.append(text_chunk)
        on_chunk = kwargs.get("on_chunk")
        if on_chunk:
            await on_chunk(b"\x01\x02")
            await on_chunk(b"\x03\x04")
        return {
            "audio_data": b"fake-wav-audio",
            "audio_format": "wav",
            "chunk_count": max(2, len(collected)),
            "used_streaming": True,
            "sample_rate": 24000,
            "channels": 1,
            "sample_width": 2,
        }

    async def _fake_synthesize_speech(*args, **kwargs):
        raise AssertionError("streaming TTS succeeded, should not fallback")

    async def _fake_save_audio_file(*args, **kwargs):
        return "uploads/audio/test-ai.wav"

    monkeypatch.setattr(fc.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(fc.websocket_manager, "broadcast_to_room", _fake_broadcast_to_room)
    monkeypatch.setattr(fc.room_manager, "update_room_state", _fake_update_room_state)
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(fc.ConfigService, "get_coze_config", _fake_get_coze_config)
    monkeypatch.setattr(fc.ConfigService, "get_tts_config", _fake_get_tts_config)
    monkeypatch.setattr(
        fc.flow_controller,
        "notify_speech_committed",
        _noop_notify_speech_committed,
    )
    monkeypatch.setattr(fc.flow_controller, "advance_segment", _noop_advance_segment)
    monkeypatch.setattr(AIDebaterAgent, "generate_speech_with_audio", _fake_generate_speech_with_audio)
    monkeypatch.setattr(fc.voice_processor, "synthesize_speech_stream_live", _fake_synthesize_speech_stream_live)
    monkeypatch.setattr(fc.voice_processor, "synthesize_speech", _fake_synthesize_speech)
    monkeypatch.setattr(fc.voice_processor, "save_audio_file", _fake_save_audio_file)
    monkeypatch.setattr(fc.voice_processor, "build_audio_url", lambda _path: "/uploads/audio/test-ai.wav")

    try:
        asyncio.run(fc.flow_controller._run_ai_turn(room_id, segment))
    finally:
        room_manager.rooms.pop(room_id, None)

    speech_messages = [m for m in broadcasted if m.get("type") == "speech"]
    stream_start_messages = [m for m in broadcasted if m.get("type") == "tts_stream_start"]
    stream_chunk_messages = [m for m in broadcasted if m.get("type") == "tts_stream_chunk"]
    stream_end_messages = [m for m in broadcasted if m.get("type") == "tts_stream_end"]

    assert len(speech_messages) == 2
    assert speech_messages[0]["data"]["content"] == "这是先到的AI文本"
    assert speech_messages[0]["data"]["audio_url"] is None
    assert speech_messages[1]["data"]["audio_url"] == "/uploads/audio/test-ai.wav"
    assert speech_messages[1]["data"]["audio_format"] == "wav"
    assert speech_messages[0]["data"]["speech_id"] == speech_messages[1]["data"]["speech_id"]

    assert len(stream_start_messages) == 1
    assert len(stream_chunk_messages) == 2
    assert len(stream_end_messages) == 1
    assert stream_start_messages[0]["data"]["speech_id"] == speech_messages[0]["data"]["speech_id"]
    assert stream_chunk_messages[0]["data"]["chunk_index"] == 1
    assert stream_chunk_messages[1]["data"]["chunk_index"] == 2
    assert stream_end_messages[0]["data"]["audio_url"] == "/uploads/audio/test-ai.wav"


def test_ai_turn_falls_back_to_non_streaming_tts(monkeypatch):
    from services import flow_controller as fc

    room_id = "test_room_ai_turn_tts_fallback_001"
    debate_id = str(uuid.uuid4())
    room_state = RoomState(
        room_id=room_id,
        debate_id=debate_id,
        current_phase=DebatePhase.OPENING,
        current_speaker="ai_1",
        segment_index=1,
        segment_id="opening_negative_1",
        segment_title="立论阶段：反方一辩",
    )
    room_state.ai_debaters = [{"id": "ai_1", "name": "AI一辩"}]
    room_manager.rooms[room_id] = room_state

    segment = {
        "id": "opening_negative_1",
        "title": "立论阶段：反方一辩",
        "phase": DebatePhase.OPENING,
        "duration": 180,
        "mode": "fixed",
        "speaker_roles": ["ai_1"],
    }

    broadcasted = []
    fake_db = _FlowTestDB()
    stream_attempted = {"value": False}
    fallback_called = {"value": False}

    async def _fake_sleep(_seconds):
        return None

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    async def _fake_generate_speech_with_audio(self, **kwargs):
        return {
            "text": "这是兜底语音的AI文本",
            "audio_data": None,
            "duration": 2,
            "voice_id": "Cherry",
        }

    async def _fake_synthesize_speech_stream_live(*args, **kwargs):
        stream_attempted["value"] = True
        raise RuntimeError("stream unavailable")

    async def _fake_synthesize_speech(*args, **kwargs):
        fallback_called["value"] = True
        assert kwargs["speed"] is None
        return b"fallback-audio"

    async def _fake_save_audio_file(*args, **kwargs):
        return "uploads/audio/test-ai-fallback.mp3"

    monkeypatch.setattr(fc.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(fc.websocket_manager, "broadcast_to_room", _fake_broadcast_to_room)
    monkeypatch.setattr(fc.room_manager, "update_room_state", _fake_update_room_state)
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(fc.ConfigService, "get_coze_config", _fake_get_coze_config)
    monkeypatch.setattr(fc.ConfigService, "get_tts_config", _fake_get_tts_config)
    monkeypatch.setattr(
        fc.flow_controller,
        "notify_speech_committed",
        _noop_notify_speech_committed,
    )
    monkeypatch.setattr(fc.flow_controller, "advance_segment", _noop_advance_segment)
    monkeypatch.setattr(AIDebaterAgent, "generate_speech_with_audio", _fake_generate_speech_with_audio)
    monkeypatch.setattr(fc.voice_processor, "synthesize_speech_stream_live", _fake_synthesize_speech_stream_live)
    monkeypatch.setattr(fc.voice_processor, "synthesize_speech", _fake_synthesize_speech)
    monkeypatch.setattr(fc.voice_processor, "save_audio_file", _fake_save_audio_file)
    monkeypatch.setattr(
        fc.voice_processor,
        "build_audio_url",
        lambda _path: "/uploads/audio/test-ai-fallback.mp3",
    )

    try:
        asyncio.run(fc.flow_controller._run_ai_turn(room_id, segment))
    finally:
        room_manager.rooms.pop(room_id, None)

    speech_messages = [m for m in broadcasted if m.get("type") == "speech"]

    assert stream_attempted["value"] is True
    assert fallback_called["value"] is True
    assert len(speech_messages) == 2
    assert speech_messages[0]["data"]["content"] == "这是兜底语音的AI文本"
    assert speech_messages[0]["data"]["audio_url"] is None
    assert speech_messages[1]["data"]["audio_url"] == "/uploads/audio/test-ai-fallback.mp3"
    assert speech_messages[1]["data"]["audio_format"] == "mp3"
    assert speech_messages[0]["data"]["speech_id"] == speech_messages[1]["data"]["speech_id"]
