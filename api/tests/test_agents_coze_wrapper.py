import pytest

from services.coze_client import CozeClient, Message, MessageRole


@pytest.mark.parametrize("history_count", [0, 3, 5])
def test_chat_coze_message_truncates_and_role_is_assistant(monkeypatch, history_count: int):
    def fake_chat_coze(self, *, bot_id: str, user_id: str, messages: list, extra=None):
        return "字" * 300

    monkeypatch.setattr(CozeClient, "chat_coze", fake_chat_coze, raising=True)

    client = CozeClient(api_token="test", base_url="https://api.coze.cn")

    history = [
        {"role": ("user" if i % 2 == 0 else "assistant"), "content": f"m{i}", "conversation_id": None}
        for i in range(history_count)
    ]
    raw_messages = history + [{"role": "user", "content": "current", "conversation_id": None}]

    params = client.build_chat_coze_params(
        bot_id="bot",
        user_id="user",
        raw_messages=raw_messages,
        max_chars_hint=200,
    )

    assert isinstance(params["messages"], list)
    assert all(isinstance(m, Message) for m in params["messages"])
    if history_count:
        assert params["messages"][0].role == (MessageRole.USER if history[0]["role"] == "user" else MessageRole.ASSISTANT)

    reply_message = client.chat_coze_message(
        bot_id=params["bot_id"],
        user_id=params["user_id"],
        messages=params["messages"],
        max_output_chars=200,
    )

    assert reply_message.role == MessageRole.ASSISTANT
    assert len(reply_message.content) <= 200
