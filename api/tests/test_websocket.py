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

    async def _fake_sleep(_seconds):
        return None

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    class _FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

        def scalars(self):
            return self

        def all(self):
            return self.value

    class _FakeDB:
        def __init__(self):
            self.execute_calls = 0

        def execute(self, _stmt):
            self.execute_calls += 1
            if self.execute_calls == 1:
                return _FakeResult(SimpleNamespace(id=uuid.uuid4(), topic="测试辩题"))
            return _FakeResult([])

        def add(self, obj):
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

        def commit(self):
            return None

        def close(self):
            return None

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
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: _FakeDB())
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

    async def _fake_sleep(_seconds):
        return None

    async def _fake_broadcast_to_room(_room_id, message):
        broadcasted.append(message)

    async def _fake_update_room_state(_room_id, **kwargs):
        for key, value in kwargs.items():
            setattr(room_state, key, value)
        return True

    class _FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

        def scalars(self):
            return self

        def all(self):
            return self.value

    class _FakeDB:
        def __init__(self):
            self.execute_calls = 0

        def execute(self, _stmt):
            self.execute_calls += 1
            if self.execute_calls == 1:
                return _FakeResult(SimpleNamespace(id=uuid.uuid4(), topic="测试辩题"))
            return _FakeResult([])

        def add(self, obj):
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

        def commit(self):
            return None

        def close(self):
            return None

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
    monkeypatch.setattr(fc.db_module, "SessionLocal", lambda: _FakeDB())
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
