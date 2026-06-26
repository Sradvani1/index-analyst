"""Tests for local chat session index CRUD."""

from __future__ import annotations

import json

import pytest

from src.chat_sessions import (
    DEFAULT_TITLE,
    SessionNotFoundError,
    create_session,
    delete_session_record,
    get_session,
    list_sessions,
    load_index,
    save_index,
    touch_session,
    update_session_title,
)
from src.files import InputError
from src.schemas import ChatSessionIndex, ChatSessionRecord

from tests.conftest import make_settings


def test_create_and_list_sessions(tmp_path):
    settings = make_settings(tmp_path)
    a = create_session("thread_a", settings=settings)
    b = create_session("thread_b", title="Trim discussion", settings=settings)

    sessions = list_sessions(settings)
    assert len(sessions) == 2
    assert sessions[0].id in {a.id, b.id}
    assert {s.openai_thread_id for s in sessions} == {"thread_a", "thread_b"}


def test_get_session_not_found(tmp_path):
    settings = make_settings(tmp_path)
    with pytest.raises(SessionNotFoundError):
        get_session("missing", settings)


def test_update_session_title(tmp_path):
    settings = make_settings(tmp_path)
    record = create_session("thread_1", settings=settings)
    updated = update_session_title(record.id, "Posture check", settings=settings)
    assert updated.title == "Posture check"
    assert updated.updated_at >= record.updated_at


def test_update_session_title_rejects_empty(tmp_path):
    settings = make_settings(tmp_path)
    record = create_session("thread_1", settings=settings)
    with pytest.raises(InputError):
        update_session_title(record.id, "   ", settings=settings)


def test_touch_session_updates_timestamp(tmp_path):
    settings = make_settings(tmp_path)
    record = create_session("thread_1", settings=settings)
    touched = touch_session(record.id, settings=settings)
    assert touched.updated_at >= record.updated_at


def test_delete_session_record(tmp_path):
    settings = make_settings(tmp_path)
    record = create_session("thread_1", settings=settings)
    removed = delete_session_record(record.id, settings=settings)
    assert removed.id == record.id
    with pytest.raises(SessionNotFoundError):
        get_session(record.id, settings)


def test_save_index_atomic_roundtrip(tmp_path):
    settings = make_settings(tmp_path)
    index = ChatSessionIndex(
        sessions=[
            ChatSessionRecord(
                id="550e8400-e29b-41d4-a716-446655440000",
                openai_thread_id="thread_abc",
                title=DEFAULT_TITLE,
                created_at="2026-06-25T10:00:00+00:00",
                updated_at="2026-06-25T10:00:00+00:00",
            )
        ]
    )
    path = save_index(index, settings)
    assert path.is_file()
    loaded = load_index(settings)
    assert loaded.sessions[0].openai_thread_id == "thread_abc"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "sessions" in raw
