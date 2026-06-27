"""Tests for OpenAI Responses conversation item parsing."""

from __future__ import annotations

from types import SimpleNamespace

from src.openai_responses import (
    ChatMessageRecord,
    ResponsesError,
    iter_stream_text_deltas,
    parse_conversation_items,
    parse_message_item,
)

USER_MESSAGE_ITEM = {
    "type": "message",
    "id": "msg_user_1",
    "status": "completed",
    "role": "user",
    "content": [{"type": "input_text", "text": "What is posture now?"}],
    "created_at": 1741900001,
}

ASSISTANT_MESSAGE_ITEM = {
    "type": "message",
    "id": "msg_asst_1",
    "status": "completed",
    "role": "assistant",
    "content": [
        {
            "type": "output_text",
            "text": "As of 2026-06-12, recommended action is Hold.",
            "annotations": [],
        }
    ],
    "created_at": 1741900002,
}

FILE_SEARCH_CALL_ITEM = {
    "type": "file_search_call",
    "id": "fs_1",
    "status": "completed",
}

EMPTY_MESSAGE_ITEM = {
    "type": "message",
    "id": "msg_empty",
    "role": "user",
    "content": [],
}

SYSTEM_MESSAGE_ITEM = {
    "type": "message",
    "id": "msg_sys",
    "role": "system",
    "content": [{"type": "input_text", "text": "hidden"}],
}

ASSISTANT_REFUSAL_MESSAGE_ITEM = {
    "type": "message",
    "id": "msg_refusal",
    "status": "completed",
    "role": "assistant",
    "content": [
        {
            "type": "refusal",
            "refusal": "I cannot override the published recommended action.",
        }
    ],
    "created_at": 1741900003,
}


def test_parse_user_message_item():
    record = parse_message_item(USER_MESSAGE_ITEM)
    assert record == ChatMessageRecord(
        id="msg_user_1",
        role="user",
        content="What is posture now?",
        created_at=1741900001,
    )


def test_parse_assistant_message_item():
    record = parse_message_item(ASSISTANT_MESSAGE_ITEM)
    assert record == ChatMessageRecord(
        id="msg_asst_1",
        role="assistant",
        content="As of 2026-06-12, recommended action is Hold.",
        created_at=1741900002,
    )


def test_parse_non_message_item_returns_none():
    assert parse_message_item(FILE_SEARCH_CALL_ITEM) is None


def test_parse_empty_message_returns_none():
    assert parse_message_item(EMPTY_MESSAGE_ITEM) is None


def test_parse_system_role_returns_none():
    assert parse_message_item(SYSTEM_MESSAGE_ITEM) is None


def test_parse_assistant_refusal_message_item():
    record = parse_message_item(ASSISTANT_REFUSAL_MESSAGE_ITEM)
    assert record == ChatMessageRecord(
        id="msg_refusal",
        role="assistant",
        content="I cannot override the published recommended action.",
        created_at=1741900003,
    )


def test_iter_stream_text_deltas_includes_refusal_and_output_text():
    events = [
        SimpleNamespace(type="response.refusal.delta", delta="I cannot "),
        SimpleNamespace(type="response.refusal.delta", delta="override that."),
    ]
    assert list(iter_stream_text_deltas(events)) == ["I cannot ", "override that."]

    events = [
        SimpleNamespace(type="response.output_text.delta", delta="Hello "),
        SimpleNamespace(type="response.output_text.delta", delta="world."),
    ]
    assert list(iter_stream_text_deltas(events)) == ["Hello ", "world."]


def test_iter_stream_text_deltas_raises_on_failed_event():
    events = [SimpleNamespace(type="response.failed", delta="")]
    try:
        list(iter_stream_text_deltas(events))
    except ResponsesError as exc:
        assert "response stream failed" in str(exc)
    else:
        raise AssertionError("expected ResponsesError")


def test_parse_conversation_items_filters_and_preserves_order():
    items = [
        USER_MESSAGE_ITEM,
        FILE_SEARCH_CALL_ITEM,
        ASSISTANT_MESSAGE_ITEM,
        EMPTY_MESSAGE_ITEM,
    ]
    records = parse_conversation_items(items)
    assert [r.role for r in records] == ["user", "assistant"]
    assert records[0].content == "What is posture now?"
    assert "recommended action" in records[1].content
