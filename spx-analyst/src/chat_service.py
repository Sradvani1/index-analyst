"""Phase 2 chat service (stub).

Defines the interface a future conversational layer will implement. Daily-state
memory (canonical research memory) stays separate from chat-session memory
(ephemeral reasoning memory) to preserve analytical integrity.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .chat_context import load_chat_context
from .config import Settings, get_settings
from .schemas import ChatSessionContext


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class ChatSession:
    context: ChatSessionContext
    messages: list[ChatMessage] = field(default_factory=list)


class ChatService:
    """Skeleton for Phase 2. The reply path is intentionally not implemented."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def start_session(self, date: str) -> ChatSession:
        return ChatSession(context=load_chat_context(date, self.settings))

    def reply(self, session: ChatSession, user_message: str) -> str:
        raise NotImplementedError(
            "Phase 2: wire the chat context into a Claude conversation here. "
            "Chat-session memory must remain separate from canonical daily-state memory."
        )
