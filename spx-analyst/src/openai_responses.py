"""OpenAI Responses + Conversations API wrapper for chat."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterator, Protocol

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


class ResponsesError(Exception):
    """Hard failure talking to the OpenAI Responses / Conversations API."""


@dataclass(frozen=True)
class ChatMessageRecord:
    id: str
    role: str
    content: str
    created_at: int | None = None


class ResponsesClient(Protocol):
    def create_conversation(self) -> str: ...

    def delete_conversation(self, conversation_id: str) -> None: ...

    def list_messages(self, conversation_id: str) -> list[ChatMessageRecord]: ...

    def stream_reply(
        self,
        *,
        conversation_id: str,
        user_message: str,
        instructions: str,
    ) -> Iterator[str]: ...


def _item_attr(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _message_text_from_content(content_blocks: Any) -> str:
    parts: list[str] = []
    for block in content_blocks or []:
        block_type = _item_attr(block, "type")
        if block_type in ("input_text", "output_text", "text"):
            text = _item_attr(block, "text", "")
        elif block_type == "refusal":
            text = _item_attr(block, "refusal", "")
        else:
            text = ""
        if text:
            parts.append(text)
    return "".join(parts)


def iter_stream_text_deltas(events: Any) -> Iterator[str]:
    """Yield streamed assistant text from Responses API SSE events."""
    for event in events:
        if event.type in ("response.output_text.delta", "response.refusal.delta"):
            yield event.delta
        elif event.type in ("error", "response.failed"):
            raise ResponsesError(f"response stream failed: {event}")


def parse_message_item(item: Any) -> ChatMessageRecord | None:
    """Map a Conversations API item to ChatMessageRecord when it is a text message."""
    if _item_attr(item, "type") != "message":
        return None
    role = _item_attr(item, "role")
    if role not in ("user", "assistant"):
        return None
    content = _message_text_from_content(_item_attr(item, "content", []))
    if not content:
        return None
    return ChatMessageRecord(
        id=_item_attr(item, "id") or "",
        role=role,
        content=content,
        created_at=_item_attr(item, "created_at"),
    )


def parse_conversation_items(items: list[Any]) -> list[ChatMessageRecord]:
    """Parse conversation items, keeping only completed text messages in order."""
    messages: list[ChatMessageRecord] = []
    for item in items:
        record = parse_message_item(item)
        if record is not None:
            messages.append(record)
    return messages


def _require_chat_settings(settings: Settings) -> None:
    missing = [
        name
        for name, value in (
            ("OPENAI_API_KEY", settings.openai_api_key),
            ("OPENAI_CHAT_MODEL", settings.openai_chat_model),
            ("OPENAI_VECTOR_STORE_ID", settings.openai_vector_store_id),
        )
        if not value.strip()
    ]
    if missing:
        raise ResponsesError(f"missing required OpenAI env var(s): {', '.join(missing)}")


class LiveResponsesClient:
    """Production Responses client — conversations, items, streamed replies."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        _require_chat_settings(settings)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ResponsesError(
                "openai package not installed; add openai>=1.82.0 to dependencies"
            ) from exc
        self._settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key)

    def create_conversation(self) -> str:
        try:
            conversation = self._client.conversations.create()
            return conversation.id
        except Exception as exc:
            raise ResponsesError(f"failed to create conversation: {exc}") from exc

    def delete_conversation(self, conversation_id: str) -> None:
        try:
            self._client.conversations.delete(conversation_id)
        except Exception as exc:
            raise ResponsesError(
                f"failed to delete conversation {conversation_id}: {exc}"
            ) from exc

    def list_messages(self, conversation_id: str) -> list[ChatMessageRecord]:
        try:
            messages: list[ChatMessageRecord] = []
            after: str | None = None
            while True:
                page = self._client.conversations.items.list(
                    conversation_id,
                    order="asc",
                    **({"after": after} if after else {}),
                )
                messages.extend(parse_conversation_items(page.data))
                if not page.has_more:
                    break
                after = page.last_id
            return messages
        except ResponsesError:
            raise
        except Exception as exc:
            raise ResponsesError(
                f"failed to list messages for {conversation_id}: {exc}"
            ) from exc

    def stream_reply(
        self,
        *,
        conversation_id: str,
        user_message: str,
        instructions: str,
    ) -> Iterator[str]:
        try:
            with self._client.responses.stream(
                model=self._settings.openai_chat_model,
                conversation=conversation_id,
                input=[{"role": "user", "content": user_message}],
                instructions=instructions,
                store=True,
                tools=[
                    {
                        "type": "file_search",
                        "vector_store_ids": [self._settings.openai_vector_store_id],
                    }
                ],
            ) as stream:
                yield from iter_stream_text_deltas(stream)
        except ResponsesError:
            raise
        except Exception as exc:
            raise ResponsesError(
                f"response stream failed for {conversation_id}: {exc}"
            ) from exc


def get_responses_client(settings: Settings | None = None) -> LiveResponsesClient:
    return LiveResponsesClient(settings)
