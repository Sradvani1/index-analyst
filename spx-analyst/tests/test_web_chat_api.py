"""Tests for FastAPI chat routes with mocked OpenAI assistant."""

from __future__ import annotations

import json
import uuid
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from src.chat_service import ChatService, get_chat_service
from src.config import Settings
from src.openai_assistant import AssistantError, ThreadMessage
from src.web.app import app
from src.web.chat_api import clear_chat_service_cache

from tests.conftest import make_settings, write_state


class FakeAssistantClient:
    def __init__(self, *, fail_stream: bool = False) -> None:
        self.threads: dict[str, list[ThreadMessage]] = {}
        self.deleted: list[str] = []
        self.fail_stream = fail_stream

    def create_thread(self) -> str:
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        self.threads[thread_id] = []
        return thread_id

    def delete_thread(self, thread_id: str) -> None:
        self.deleted.append(thread_id)
        self.threads.pop(thread_id, None)

    def list_messages(self, thread_id: str) -> list[ThreadMessage]:
        return list(self.threads.get(thread_id, []))

    def stream_assistant_reply(
        self,
        *,
        thread_id: str,
        user_message: str,
        additional_instructions: str,
    ) -> Iterator[str]:
        if self.fail_stream:
            raise AssistantError("simulated stream failure")
        self.threads.setdefault(thread_id, []).append(
            ThreadMessage(id=f"msg_{len(self.threads[thread_id])}", role="user", content=user_message)
        )
        assert "latest_run_date" in additional_instructions
        reply = (
            f"As of preload context, recommended action is available "
            f"for: {user_message[:40]}"
        )
        self.threads[thread_id].append(
            ThreadMessage(
                id=f"msg_{len(self.threads[thread_id])}",
                role="assistant",
                content=reply,
            )
        )
        for word in reply.split():
            yield word + " "


@pytest.fixture
def chat_client(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    instructions = tmp_path / "framework" / "chat-assistant-instructions.md"
    instructions.write_text("# Assistant\n\nUse preload.\n", encoding="utf-8")
    settings = settings.model_copy(
        update={
            "chat_assistant_instructions_path_raw": str(instructions),
            "openai_api_key": "test-key",
            "openai_assistant_id": "asst_test",
        }
    )
    write_state(settings, "2026-06-12")

    fake = FakeAssistantClient()
    service = ChatService(settings=settings, assistant=fake)

    clear_chat_service_cache()
    monkeypatch.setattr("src.chat_service.get_chat_service", lambda: service)
    monkeypatch.setattr("src.web.chat_api.get_chat_service", lambda: service)

    client = TestClient(app)
    return client, service, fake


def test_list_sessions_empty(chat_client):
    client, _, _ = chat_client
    response = client.get("/api/chat/sessions")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_list_session(chat_client):
    client, _, _ = chat_client
    response = client.post("/api/chat/sessions", json={"title": "Posture chat"})
    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "Posture chat"
    assert created["id"]

    listed = client.get("/api/chat/sessions").json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]


def test_rename_and_delete_session(chat_client):
    client, _, fake = chat_client
    created = client.post("/api/chat/sessions", json={}).json()

    renamed = client.patch(
        f"/api/chat/sessions/{created['id']}",
        json={"title": "Renamed"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed"

    deleted = client.delete(f"/api/chat/sessions/{created['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/chat/sessions").json() == []
    assert fake.deleted


def test_post_message_streams_sse(chat_client):
    client, service, fake = chat_client
    created = client.post("/api/chat/sessions", json={}).json()

    with client.stream(
        "POST",
        f"/api/chat/sessions/{created['id']}/messages",
        json={"content": "what is posture now?"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "data:" in body
    assert "[DONE]" in body
    parsed = [
        line
        for line in body.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    assert parsed
    payload = json.loads(parsed[0].removeprefix("data: "))
    assert "text" in payload

    record = service.list_sessions()[0]
    roles = [m.role for m in fake.threads[record.openai_thread_id]]
    assert roles == ["user", "assistant"]


def test_get_messages(chat_client):
    client, _, _ = chat_client
    created = client.post("/api/chat/sessions", json={}).json()
    client.post(
        f"/api/chat/sessions/{created['id']}/messages",
        json={"content": "hello"},
    )

    messages = client.get(f"/api/chat/sessions/{created['id']}/messages")
    assert messages.status_code == 200
    data = messages.json()
    assert len(data) == 2
    assert data[0]["role"] == "user"
    assert data[1]["role"] == "assistant"


def test_post_message_unknown_session_404(chat_client):
    client, _, _ = chat_client
    response = client.post(
        "/api/chat/sessions/00000000-0000-0000-0000-000000000000/messages",
        json={"content": "hello"},
    )
    assert response.status_code == 404


def test_post_message_stream_failure_does_not_touch_updated_at(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    instructions = tmp_path / "framework" / "chat-assistant-instructions.md"
    instructions.write_text("# Assistant\n\nUse preload.\n", encoding="utf-8")
    settings = settings.model_copy(
        update={
            "chat_assistant_instructions_path_raw": str(instructions),
            "openai_api_key": "test-key",
            "openai_assistant_id": "asst_test",
        }
    )
    write_state(settings, "2026-06-12")

    fake = FakeAssistantClient(fail_stream=True)
    service = ChatService(settings=settings, assistant=fake)

    clear_chat_service_cache()
    monkeypatch.setattr("src.chat_service.get_chat_service", lambda: service)
    monkeypatch.setattr("src.web.chat_api.get_chat_service", lambda: service)

    client = TestClient(app)
    created = client.post("/api/chat/sessions", json={}).json()
    before = service.list_sessions()[0].updated_at

    with client.stream(
        "POST",
        f"/api/chat/sessions/{created['id']}/messages",
        json={"content": "what is posture now?"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert '"error"' in body
    after = service.list_sessions()[0].updated_at
    assert after == before


def test_chat_service_stream_auto_title(tmp_path):
    settings = make_settings(tmp_path)
    instructions = tmp_path / "framework" / "chat-assistant-instructions.md"
    instructions.write_text("# Assistant\n", encoding="utf-8")
    settings = settings.model_copy(
        update={"chat_assistant_instructions_path_raw": str(instructions)}
    )
    write_state(settings, "2026-06-12")

    fake = FakeAssistantClient()
    service = ChatService(settings=settings, assistant=fake)
    record = service.create_session()
    list(service.stream_reply(record.id, "What is posture now?"))

    updated = service.list_sessions()[0]
    assert updated.title == "What is posture now?"
