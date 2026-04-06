from services.coze_client import CozeClient


def test_to_additional_messages_maps_roles_and_types():
    additional = CozeClient._to_additional_messages(
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
    )
    assert additional == [
        {"content": "hello", "content_type": "text", "role": "user", "type": "question"},
        {"content": "world", "content_type": "text", "role": "assistant", "type": "answer"},
    ]


def test_extract_reply_text_prefers_data_messages_last_item():
    payload = {
        "data": {
            "messages": [
                {"role": "assistant", "content": "first"},
                {"role": "assistant", "content": "last"},
            ]
        }
    }
    assert CozeClient._extract_reply_text(payload) == "last"


def test_extract_reply_text_falls_back_to_root_messages():
    payload = {"messages": [{"content": "ok"}]}
    assert CozeClient._extract_reply_text(payload) == "ok"


def test_collect_stream_text_from_sse_lines_concatenates_deltas():
    lines = [
        "event: message",
        'data: {"data": {"delta": {"content": "你"}}}',
        'data: {"data": {"delta": {"content": "好"}}}',
        "data: [DONE]",
    ]
    assert CozeClient._collect_stream_text_from_sse_lines(lines) == "你好"
