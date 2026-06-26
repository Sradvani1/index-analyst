"""OpenAI Assistants API wrapper for chat threads and streaming runs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator, Protocol

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


class AssistantError(Exception):
    """Hard failure talking to the OpenAI Assistants API."""


@dataclass(frozen=True)
class ThreadMessage:
    id: str
    role: str
    content: str
    created_at: int | None = None


class AssistantClient(Protocol):
    def create_thread(self) -> str: ...

    def delete_thread(self, thread_id: str) -> None: ...

    def list_messages(self, thread_id: str) -> list[ThreadMessage]: ...

    def stream_assistant_reply(
        self,
        *,
        thread_id: str,
        user_message: str,
        additional_instructions: str,
    ) -> Iterator[str]: ...


def _require_chat_settings(settings: Settings) -> None:
    missing = [
        name
        for name, value in (
            ("OPENAI_API_KEY", settings.openai_api_key),
            ("OPENAI_ASSISTANT_ID", settings.openai_assistant_id),
        )
        if not value.strip()
    ]
    if missing:
        raise AssistantError(f"missing required OpenAI env var(s): {', '.join(missing)}")


def _message_text(content_blocks) -> str:
    parts: list[str] = []
    for block in content_blocks:
        if getattr(block, "type", None) == "text" and block.text is not None:
            parts.append(block.text.value)
    return "".join(parts)


class LiveAssistantClient:
    """Production Assistants client — threads, messages, streamed runs."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        _require_chat_settings(settings)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AssistantError(
                "openai package not installed; add openai>=1.40.0 to dependencies"
            ) from exc
        self._settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._assistant_id = settings.openai_assistant_id

    def create_thread(self) -> str:
        try:
            thread = self._client.beta.threads.create()
            return thread.id
        except Exception as exc:
            raise AssistantError(f"failed to create thread: {exc}") from exc

    def delete_thread(self, thread_id: str) -> None:
        try:
            self._client.beta.threads.delete(thread_id)
        except Exception as exc:
            raise AssistantError(f"failed to delete thread {thread_id}: {exc}") from exc

    def list_messages(self, thread_id: str) -> list[ThreadMessage]:
        try:
            page = self._client.beta.threads.messages.list(
                thread_id=thread_id,
                order="asc",
            )
        except Exception as exc:
            raise AssistantError(f"failed to list messages for {thread_id}: {exc}") from exc

        messages: list[ThreadMessage] = []
        for msg in page.data:
            messages.append(
                ThreadMessage(
                    id=msg.id,
                    role=msg.role,
                    content=_message_text(msg.content),
                    created_at=msg.created_at,
                )
            )
        return messages

    def stream_assistant_reply(
        self,
        *,
        thread_id: str,
        user_message: str,
        additional_instructions: str,
    ) -> Iterator[str]:
        try:
            self._client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_message,
            )
            with self._client.beta.threads.runs.stream(
                thread_id=thread_id,
                assistant_id=self._assistant_id,
                additional_instructions=additional_instructions,
            ) as stream:
                yield from stream.text_deltas
        except AssistantError:
            raise
        except Exception as exc:
            raise AssistantError(f"assistant run failed for {thread_id}: {exc}") from exc


def get_assistant_client(settings: Settings | None = None) -> LiveAssistantClient:
    return LiveAssistantClient(settings)
