import asyncio
import json
import inspect
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Union
from urllib.parse import urlparse

import httpx


if TYPE_CHECKING:
    from cozepy import (
        COZE_CN_BASE_URL,
        Coze,
        TokenAuth,
        Message,
        ChatEventType,
        MessageRole,
        MessageType,
        MessageContentType,
    )
else:
    try:
        from cozepy import (
            COZE_CN_BASE_URL,
            Coze,
            TokenAuth,
            Message,
            ChatEventType,
            MessageRole,
            MessageType,
            MessageContentType,
        )
    except ModuleNotFoundError:
        from dataclasses import dataclass
        from enum import Enum

        COZE_CN_BASE_URL = "https://api.coze.cn"

        class MessageRole(str, Enum):
            USER = "user"
            ASSISTANT = "assistant"

        class MessageType(str, Enum):
            QUESTION = "question"
            ANSWER = "answer"

        class MessageContentType(str, Enum):
            TEXT = "text"

        @dataclass
        class Message:
            role: MessageRole
            type: MessageType
            content: str
            content_type: MessageContentType
            conversation_id: Optional[str] = None

        class ChatEventType(str, Enum):
            CONVERSATION_MESSAGE_DELTA = "conversation_message_delta"
            CONVERSATION_CHAT_COMPLETED = "conversation_chat_completed"

        class TokenAuth:
            def __init__(self, *, token: str):
                self.token = token

        class _DummyChat:
            def stream(self, *args, **kwargs):
                raise RuntimeError("cozepy is not installed")

        class Coze:
            def __init__(self, *args, **kwargs):
                self.chat = _DummyChat()


class CozeClient:
    def __init__(
            self,
            *,
            api_token: str,
            base_url: str,
            timeout_seconds: float = 30.0,
    ):
        self.api_token = (api_token or "").strip()
        self.base_url = (base_url or "").strip()
        self.timeout_seconds = float(timeout_seconds)

        self.coze_client = Coze(auth=TokenAuth(token=self.api_token), base_url=self.base_url)

    @staticmethod
    def _to_additional_messages(messages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        additional: List[Dict[str, Any]] = []
        for msg in messages or []:
            role = (msg.get("role") or "user").strip().lower()
            if role not in ("user", "assistant"):
                role = "user"
            msg_type = "question" if role == "user" else "answer"
            additional.append(
                {
                    "content": (msg.get("content") or ""),
                    "content_type": "text",
                    "role": role,
                    "type": msg_type,
                }
            )
        return additional

    @staticmethod
    def _extract_reply_text(payload: Dict[str, Any]) -> str:
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            msgs = data.get("messages")
            if isinstance(msgs, list) and msgs:
                last = msgs[-1] if isinstance(msgs[-1], dict) else {}
                return (last.get("content") or "").strip()
        msgs = payload.get("messages") if isinstance(payload, dict) else None
        if isinstance(msgs, list) and msgs:
            last = msgs[-1] if isinstance(msgs[-1], dict) else {}
            return (last.get("content") or "").strip()
        return ""

    @staticmethod
    def _collect_stream_text_from_sse_lines(lines: Iterable[str]) -> str:
        parts: List[str] = []
        for line in lines or []:
            if not line:
                continue
            text = line.strip()
            if not text.startswith("data:"):
                continue
            data_text = text[len("data:") :].strip()
            if data_text == "[DONE]":
                break
            try:
                obj = json.loads(data_text)
            except Exception:
                continue
            delta = (((obj.get("data") or {}).get("delta") or {}) if isinstance(obj, dict) else {})
            content = (delta.get("content") or "") if isinstance(delta, dict) else ""
            if content:
                parts.append(content)
        return "".join(parts)

    @staticmethod
    @lru_cache(maxsize=1)
    def _cozepy_message_param_names() -> frozenset:
        try:
            sig = inspect.signature(Message)
        except Exception:
            try:
                sig = inspect.signature(Message.__init__)
            except Exception:
                return frozenset()
        return frozenset(sig.parameters.keys())

    @staticmethod
    def _map_role(role: str) -> MessageRole:
        role_norm = (role or "").strip().lower()
        if role_norm in ("assistant", "bot"):
            return MessageRole.ASSISTANT
        return MessageRole.USER

    @classmethod
    def to_cozepy_messages(cls, raw_messages: Sequence[Union[Dict[str, Any], Message]]) -> List[Message]:
        messages: List[Message] = []
        param_names = cls._cozepy_message_param_names()
        for raw in raw_messages or []:
            if isinstance(raw, Message):
                messages.append(raw)
                continue
            if not isinstance(raw, dict):
                continue

            role = cls._map_role(raw.get("role") or "user")
            content = raw.get("content") or ""
            conversation_id = raw.get("conversation_id", None)

            kwargs: Dict[str, Any] = {
                "role": role,
                "type": (MessageType.QUESTION if role == MessageRole.USER else MessageType.ANSWER),
                "content": content,
                "content_type": MessageContentType.TEXT,
            }
            if conversation_id is not None and "conversation_id" in param_names:
                kwargs["conversation_id"] = conversation_id

            filtered = {k: v for k, v in kwargs.items() if (not param_names) or (k in param_names)}
            messages.append(Message(**filtered))
        return messages

    @staticmethod
    def _apply_length_hint_to_last_user_message(
        raw_messages: Sequence[Union[Dict[str, Any], Message]],
        *,
        max_chars_hint: int,
    ) -> List[Union[Dict[str, Any], Message]]:
        if not max_chars_hint or max_chars_hint <= 0:
            return list(raw_messages or [])

        hint = f"要求言简意赅，不超过{int(max_chars_hint)}字"
        copied: List[Union[Dict[str, Any], Message]] = list(raw_messages or [])

        for i in range(len(copied) - 1, -1, -1):
            msg = copied[i]
            if isinstance(msg, Message):
                if getattr(msg, "role", None) == MessageRole.USER:
                    content = getattr(msg, "content", "") or ""
                    if hint not in content:
                        setattr(msg, "content", f"{content}\n{hint}".strip())
                    break
                continue
            if isinstance(msg, dict):
                role = (msg.get("role") or "user").strip().lower()
                if role == "user":
                    content = (msg.get("content") or "").strip()
                    if hint not in content:
                        msg = dict(msg)
                        msg["content"] = f"{content}\n{hint}".strip()
                        copied[i] = msg
                    break
        return copied

    def build_chat_coze_params(
        self,
        *,
        bot_id: str,
        user_id: str,
        raw_messages: Sequence[Union[Dict[str, Any], Message]],
        extra: Optional[Dict[str, Any]] = None,
        max_chars_hint: Optional[int] = None,
    ) -> Dict[str, Any]:
        normalized_raw = list(raw_messages or [])
        if max_chars_hint:
            normalized_raw = self._apply_length_hint_to_last_user_message(
                normalized_raw,
                max_chars_hint=int(max_chars_hint),
            )

        messages = self.to_cozepy_messages(normalized_raw)
        return {
            "bot_id": bot_id,
            "user_id": user_id,
            "messages": messages,
            "extra": extra,
        }

    def _chat_url(self) -> str:
        base_url = (self.base_url or "").strip()
        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            return f"{base_url.rstrip('/')}/v3/chat"

        root = f"{parsed.scheme}://{parsed.netloc}"
        path = (parsed.path or "").rstrip("/")

        if path.endswith("/v3/chat"):
            return f"{root}{path}"
        if path.endswith("/v3"):
            return f"{root}{path}/chat"

        return f"{root}/v3/chat"

    def chat_coze_stream(
            self,
            *,
            bot_id: str,
            user_id: str,
            messages: List[Message],
            extra: Optional[Dict[str, Any]] = None,
    ):


        for event in self.coze_client.chat.stream(
                bot_id=bot_id,
                user_id=user_id,
                additional_messages=messages,
        ):
            if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                # print(event.message.content, end="", flush=True)
                yield event.message.content

            if event.event == ChatEventType.CONVERSATION_CHAT_COMPLETED:
                # print()
                print("token usage:", event.chat.usage.token_count)
                # yield event.chat.usage.token_count

    def chat_coze(
            self,
            *,
            bot_id: str,
            user_id: str,
            messages: List[Message],
            extra: Optional[Dict[str, Any]] = None,
    ):
        answer=''
        for event in self.coze_client.chat.stream(
                bot_id=bot_id,
                user_id=user_id,
                additional_messages=messages,
        ):
            if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                # print(event.message.content, end="", flush=True)
                answer+=event.message.content

            if event.event == ChatEventType.CONVERSATION_CHAT_COMPLETED:
                # print()
                print("token usage:", event.chat.usage.token_count)
                # yield event.chat.usage.token_count
        return answer

    async def chat_coze_async(
        self,
        *,
        bot_id: str,
        user_id: str,
        messages: List[Message],
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await asyncio.to_thread(
            self.chat_coze,
            bot_id=bot_id,
            user_id=user_id,
            messages=messages,
            extra=extra,
        )

    def chat_coze_message(
        self,
        *,
        bot_id: str,
        user_id: str,
        messages: List[Message],
        extra: Optional[Dict[str, Any]] = None,
        max_output_chars: Optional[int] = None,
    ) -> Message:
        text = self.chat_coze(bot_id=bot_id, user_id=user_id, messages=messages, extra=extra)
        if max_output_chars and max_output_chars > 0:
            text = (text or "")[: int(max_output_chars)]
        return Message(
            role=MessageRole.ASSISTANT,
            type=MessageType.ANSWER,
            content=(text or ""),
            content_type=MessageContentType.TEXT,
        )

    async def chat_coze_message_async(
        self,
        *,
        bot_id: str,
        user_id: str,
        messages: List[Message],
        extra: Optional[Dict[str, Any]] = None,
        max_output_chars: Optional[int] = None,
    ) -> Message:
        return await asyncio.to_thread(
            self.chat_coze_message,
            bot_id=bot_id,
            user_id=user_id,
            messages=messages,
            extra=extra,
            max_output_chars=max_output_chars,
        )


async def call_coze():
    client=CozeClient(
        api_token="YOUR_COZE_API_TOKEN",
        base_url="https://api.coze.cn"
    )

    assistant_message = Message(
        role=MessageRole.ASSISTANT,
        type=MessageType.ANSWER,
        content="",
        content_type=MessageContentType.TEXT,
    )
    user_message=Message(
        role=MessageRole.USER,
        type=MessageType.QUESTION,
        content="请陈述你的观点，要求言简意赅，不超过100字",
        content_type=MessageContentType.TEXT,
    )

    result= client.chat_coze_stream(
        bot_id="7602097016784879631",
        user_id="111",
        messages=[
            user_message,
        ],
        stream=True,
    )
    for chunk in result:
        print(chunk,end="", flush=True)

if __name__=="__main__":
    asyncio.run(call_coze())
