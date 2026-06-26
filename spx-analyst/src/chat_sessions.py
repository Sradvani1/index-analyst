"""Local chat session index — maps session ids to OpenAI thread ids."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

from .config import Settings, get_settings
from .files import InputError, read_json
from .schemas import ChatSessionIndex, ChatSessionRecord

SESSIONS_FILENAME = "sessions.json"
DEFAULT_TITLE = "New conversation"


class SessionNotFoundError(Exception):
    """Raised when a session id is not in the local index."""


def _sessions_path(settings: Settings) -> Path:
    return settings.chat_dir / SESSIONS_FILENAME


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_index(settings: Settings | None = None) -> ChatSessionIndex:
    settings = settings or get_settings()
    path = _sessions_path(settings)
    if not path.is_file():
        return ChatSessionIndex()
    return ChatSessionIndex.model_validate(read_json(path))


def save_index(index: ChatSessionIndex, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    path = _sessions_path(settings)
    _atomic_write_json(path, index.model_dump(mode="json"))
    return path


def list_sessions(settings: Settings | None = None) -> list[ChatSessionRecord]:
    index = load_index(settings)
    return sorted(index.sessions, key=lambda s: s.updated_at, reverse=True)


def get_session(session_id: str, settings: Settings | None = None) -> ChatSessionRecord:
    for session in load_index(settings).sessions:
        if session.id == session_id:
            return session
    raise SessionNotFoundError(f"chat session not found: {session_id}")


def create_session(
    openai_thread_id: str,
    *,
    title: str = DEFAULT_TITLE,
    settings: Settings | None = None,
) -> ChatSessionRecord:
    settings = settings or get_settings()
    now = _utc_now()
    record = ChatSessionRecord(
        id=str(uuid.uuid4()),
        openai_thread_id=openai_thread_id,
        title=title,
        created_at=now,
        updated_at=now,
    )
    index = load_index(settings)
    index.sessions.append(record)
    save_index(index, settings)
    return record


def update_session_title(
    session_id: str,
    title: str,
    settings: Settings | None = None,
    *,
    touch_updated_at: bool = True,
) -> ChatSessionRecord:
    settings = settings or get_settings()
    trimmed = title.strip()
    if not trimmed:
        raise InputError("session title must not be empty")

    index = load_index(settings)
    for idx, session in enumerate(index.sessions):
        if session.id != session_id:
            continue
        updates: dict[str, str] = {"title": trimmed}
        if touch_updated_at:
            updates["updated_at"] = _utc_now()
        updated = session.model_copy(update=updates)
        index.sessions[idx] = updated
        save_index(index, settings)
        return updated
    raise SessionNotFoundError(f"chat session not found: {session_id}")


def touch_session(session_id: str, settings: Settings | None = None) -> ChatSessionRecord:
    settings = settings or get_settings()
    index = load_index(settings)
    for idx, session in enumerate(index.sessions):
        if session.id != session_id:
            continue
        updated = session.model_copy(update={"updated_at": _utc_now()})
        index.sessions[idx] = updated
        save_index(index, settings)
        return updated
    raise SessionNotFoundError(f"chat session not found: {session_id}")


def delete_session_record(session_id: str, settings: Settings | None = None) -> ChatSessionRecord:
    settings = settings or get_settings()
    index = load_index(settings)
    for idx, session in enumerate(index.sessions):
        if session.id != session_id:
            continue
        removed = index.sessions.pop(idx)
        save_index(index, settings)
        return removed
    raise SessionNotFoundError(f"chat session not found: {session_id}")
