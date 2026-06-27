"""Chat orchestration: local session index + OpenAI Responses + preload."""

from __future__ import annotations

import functools
import logging
from typing import Iterator

from .chat_preload import build_additional_instructions
from .chat_sessions import (
    DEFAULT_TITLE,
    SessionNotFoundError,
    create_session,
    delete_session_record,
    get_session,
    list_sessions,
    touch_session,
    update_session_title,
)
from .config import Settings, get_settings
from .files import InputError
from .openai_responses import (
    ChatMessageRecord,
    LiveResponsesClient,
    ResponsesClient,
    ResponsesError,
)
from .schemas import ChatSessionRecord

logger = logging.getLogger(__name__)

__all__ = [
    "ChatService",
    "ChatServiceError",
    "SessionNotFoundError",
    "get_chat_service",
]


class ChatServiceError(Exception):
    """Chat operation failed."""


class ChatService:
    def __init__(
        self,
        settings: Settings | None = None,
        responses: ResponsesClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._responses = responses or LiveResponsesClient(self.settings)

    def list_sessions(self) -> list[ChatSessionRecord]:
        return list_sessions(self.settings)

    def create_session(self, *, title: str = DEFAULT_TITLE) -> ChatSessionRecord:
        try:
            conversation_id = self._responses.create_conversation()
        except ResponsesError as exc:
            raise ChatServiceError(str(exc)) from exc
        return create_session(conversation_id, title=title, settings=self.settings)

    def rename_session(self, session_id: str, title: str) -> ChatSessionRecord:
        try:
            return update_session_title(session_id, title, settings=self.settings)
        except SessionNotFoundError as exc:
            raise
        except InputError as exc:
            raise ChatServiceError(str(exc)) from exc

    def delete_session(self, session_id: str) -> None:
        try:
            record = delete_session_record(session_id, settings=self.settings)
        except SessionNotFoundError:
            raise
        try:
            self._responses.delete_conversation(record.openai_conversation_id)
        except ResponsesError as exc:
            logger.warning(
                "deleted local session %s but OpenAI conversation delete failed: %s",
                session_id,
                exc,
            )

    def get_messages(self, session_id: str) -> list[ChatMessageRecord]:
        record = get_session(session_id, self.settings)
        try:
            return self._responses.list_messages(record.openai_conversation_id)
        except ResponsesError as exc:
            raise ChatServiceError(str(exc)) from exc

    def stream_reply(self, session_id: str, user_message: str) -> Iterator[str]:
        content = user_message.strip()
        if not content:
            raise ChatServiceError("message must not be empty")

        record = get_session(session_id, self.settings)
        try:
            preload = build_additional_instructions(self.settings)
        except InputError as exc:
            raise ChatServiceError(str(exc)) from exc

        if record.title == DEFAULT_TITLE:
            auto_title = _auto_title(content)
            if auto_title:
                record = update_session_title(
                    session_id,
                    auto_title,
                    settings=self.settings,
                    touch_updated_at=False,
                )

        try:
            yield from self._responses.stream_reply(
                conversation_id=record.openai_conversation_id,
                user_message=content,
                instructions=preload.additional_instructions,
            )
        except ResponsesError as exc:
            raise ChatServiceError(str(exc)) from exc
        else:
            touch_session(session_id, self.settings)


def _auto_title(first_message: str, *, max_len: int = 60) -> str:
    text = " ".join(first_message.split())
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


@functools.lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    return ChatService()
